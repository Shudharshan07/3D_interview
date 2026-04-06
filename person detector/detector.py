import os
import urllib.request
import cv2
import numpy as np

# ── Paths for YOLOv4-tiny model files ────────────────────────────────────────
MODEL_DIR    = os.path.join(os.path.dirname(__file__), "models")
CFG_PATH     = os.path.join(MODEL_DIR, "yolov4-tiny.cfg")
WEIGHTS_PATH = os.path.join(MODEL_DIR, "yolov4-tiny.weights")
NAMES_PATH   = os.path.join(MODEL_DIR, "coco.names")

CFG_URL     = "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg"
WEIGHTS_URL = "https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights"
NAMES_URL   = "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/coco.names"

# COCO 'cell phone' class is at index 67 (0-indexed)
PHONE_LIKE_IDX = 67

def _download_if_missing(filepath, url, description):
    """Download a file from *url* to *filepath* if it does not already exist."""
    if os.path.exists(filepath):
        return
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    print(f"[INFO] Downloading {description}…  ({url})")
    urllib.request.urlretrieve(url, filepath)
    print(f"[INFO] Saved → {filepath}")

def _ensure_yolo_model():
    """Download cfg and weights once, then load the DNN network."""
    _download_if_missing(CFG_PATH, CFG_URL, "YOLOv4-tiny cfg")
    _download_if_missing(WEIGHTS_PATH, WEIGHTS_URL, "YOLOv4-tiny weights")
    _download_if_missing(NAMES_PATH, NAMES_URL, "COCO names")
    
    net = cv2.dnn.readNetFromDarknet(CFG_PATH, WEIGHTS_PATH)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    return net

# ── Face detector (Haar Cascade) ──────────────────────────────────────────────
class FaceDetector:
    """Fast frontal-face detection using OpenCV's pre-trained Haar Cascade."""

    def __init__(self):
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def process_frame(self, frame):
        """Return list of ((x,y,w,h), score) tuples for each detected face."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rects = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=7, minSize=(40, 40)
        )
        return [((x, y, w, h), 1.0) for (x, y, w, h) in rects]


# ── Object detector (YOLOv4-tiny via OpenCV DNN) ────────────────────
class ObjectDetector:
    """
    Detects people and phones using OpenCV's DNN module with YOLOv4-tiny.
    YOLOv4 natively detects 'person' (class 0) and 'cell phone' (class 67),
    so this avoids false positives like hand movements being detected as faces.
    """

    def __init__(self, confidence_threshold=0.55):
        self.net = _ensure_yolo_model()
        self.confidence_threshold = confidence_threshold
        
        # Get YOLO output layer names
        layer_names = self.net.getLayerNames()
        try:
            # OpenCV 4.6+ returns a flat array or simple list for unconn
            unconnected = self.net.getUnconnectedOutLayers()
            if isinstance(unconnected[0], list) or isinstance(unconnected[0], np.ndarray):
                self.output_layers = [layer_names[i[0] - 1] for i in unconnected]
            else:
                self.output_layers = [layer_names[i - 1] for i in unconnected]
        except Exception:
            # Fallback for older OpenCV
            self.output_layers = [layer_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]


    def process_frame(self, frame):
        """
        Return (people, phones) where each is a list of ((x,y,w,h), confidence).
        """
        h, w = frame.shape[:2]

        # Use 320x320 for faster CPU inference (can bump to 416x416 for accuracy)
        blob = cv2.dnn.blobFromImage(
            frame, 1/255.0, (320, 320), swapRB=True, crop=False
        )
        self.net.setInput(blob)
        outputs = self.net.forward(self.output_layers)

        boxes_phone = []
        conf_phone = []
        boxes_person = []
        conf_person = []

        # Parse YOLO outputs
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]

                if confidence > self.confidence_threshold:
                    if class_id == PHONE_LIKE_IDX:
                        box = detection[0:4] * np.array([w, h, w, h])
                        (center_x, center_y, width, height) = box.astype("int")
                        x = int(center_x - (width / 2))
                        y = int(center_y - (height / 2))
                        boxes_phone.append([x, y, int(width), int(height)])
                        conf_phone.append(float(confidence))
                    elif class_id == 0:  # PERSON is class 0 in COCO
                        box = detection[0:4] * np.array([w, h, w, h])
                        (center_x, center_y, width, height) = box.astype("int")
                        x = int(center_x - (width / 2))
                        y = int(center_y - (height / 2))
                        boxes_person.append([x, y, int(width), int(height)])
                        conf_person.append(float(confidence))

        phones = []
        if len(boxes_phone) > 0:
            indices = cv2.dnn.NMSBoxes(boxes_phone, conf_phone, self.confidence_threshold, 0.4)
            if len(indices) > 0:
                for i in indices.flatten():
                    x, y, bw, bh = boxes_phone[i]
                    phones.append(((x, y, bw, bh), conf_phone[i]))

        people = []
        if len(boxes_person) > 0:
            indices = cv2.dnn.NMSBoxes(boxes_person, conf_person, self.confidence_threshold, 0.4)
            if len(indices) > 0:
                for i in indices.flatten():
                    x, y, bw, bh = boxes_person[i]
                    people.append(((x, y, bw, bh), conf_person[i]))

        return people, phones
