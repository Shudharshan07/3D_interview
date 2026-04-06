import sys
import cv2
import time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QFrame, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread, QTimer
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor

from detector import ObjectDetector
from logger import ViolationLogger

# ── Colour palette ─────────────────────────────────────────────────────────────
BG_DARK    = "#121212"
PANEL_DARK = "#1e1e1e"
BORDER     = "#2e2e2e"
TEXT_PRI   = "#e0e0e0"
TEXT_SEC   = "#888888"
ACCENT_G   = "#00c896"
ACCENT_R   = "#ff4c4c"
ACCENT_O   = "#ff8c00"
ACCENT_B   = "#4a9eff"

# ── Thresholds ──────────────────────────────────────────────────────────────────
MIN_OCCUPANCY_PCT  = 60      # person must fill ≥60% of frame height
# Number of CONSECUTIVE frames a violation must persist before it counts as real.
# At ~30fps: 15 frames ≈ 0.5 s.  Hand flickers last 1-3 frames → ignored.
PHONE_CONFIRM_FRAMES   = 15   # must see phone for 15 frames straight
MULTI_CONFIRM_FRAMES   = 12   # must see 2nd person for 12 frames straight
OCCUP_CONFIRM_FRAMES   = 20   # must be too far for 20 frames straight (~0.67 s)

# ── Popup helper ───────────────────────────────────────────────────────────────
class WarningPopup(QFrame):
    def __init__(self, parent=None, timeout_ms=3500):
        super().__init__(parent)
        self.setFixedSize(390, 75)
        self._timeout_ms = timeout_ms

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self.icon_lbl = QLabel("⚠️")
        self.icon_lbl.setFont(QFont("Segoe UI", 22))
        self.icon_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.icon_lbl)

        self.txt_lbl = QLabel("")
        self.txt_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.txt_lbl.setStyleSheet("color: white; border: none; background: transparent;")
        self.txt_lbl.setWordWrap(True)
        layout.addWidget(self.txt_lbl)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def show_message(self, icon, text, color_hex):
        self.icon_lbl.setText(icon)
        self.txt_lbl.setText(text)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color_hex};
                border-radius: 10px;
                border: 2px solid rgba(255,255,255,0.2);
            }}
        """)
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setColor(QColor(color_hex))
        self.show()
        self.raise_()
        QTimer.singleShot(self._timeout_ms, self.hide)


# ── Video thread ───────────────────────────────────────────────────────────────
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray, list, list, float)
    camera_error_signal  = pyqtSignal(str)

    def __init__(self, detector):
        super().__init__()
        self._run_flag = True
        self.detector  = detector

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.camera_error_signal.emit(
                "Failed to open webcam. Ensure it is connected and not used by another app."
            )
            return

        prev_time = time.time()
        while self._run_flag:
            ret, frame = cap.read()
            if not ret:
                self.camera_error_signal.emit("Webcam feed interrupted.")
                break

            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if curr_time - prev_time > 0 else 0
            prev_time = curr_time

            display_frame = frame.copy()
            try:
                people, phones = self.detector.process_frame(frame)

                # Draw person boxes
                p_color = (60, 220, 60) if len(people) == 1 else (60, 80, 255)
                for (x, y, w, h), conf in people:
                    x, y = max(0, x), max(0, y)
                    cv2.rectangle(display_frame, (x, y), (x+w, y+h), p_color, 2)
                    cv2.putText(display_frame, f"Person {int(conf*100)}%",
                                (x, max(0, y-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, p_color, 2)

                # Draw phone boxes
                for (x, y, w, h), conf in phones:
                    x, y = max(0, x), max(0, y)
                    cv2.rectangle(display_frame, (x, y), (x+w, y+h), (40, 60, 255), 2)
                    cv2.putText(display_frame, f"Phone {int(conf*100)}%",
                                (x, max(0, y-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 60, 255), 2)

                self.change_pixmap_signal.emit(display_frame, people, phones, fps)
            except Exception as e:
                print(f"Frame error: {e}")

        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()


# ── Main window ────────────────────────────────────────────────────────────────
class InterviewMonitorApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.detector = ObjectDetector(confidence_threshold=0.55)
        self.logger   = ViolationLogger()

        self.warnings         = 0
        self.max_warnings     = 5
        self.interview_active = False

        # Cooldown prevents repeat warnings for the same event
        self.person_cooldown  = 0
        self.phone_cooldown   = 0

        # ── Temporal consistency counters ──────────────────────────────────
        # These count how many consecutive frames the condition has been true.
        # A warning only fires once the counter reaches the required threshold.
        self._phone_frames   = 0   # consecutive frames with phone
        self._multi_frames   = 0   # consecutive frames with >1 person
        self._occup_frames   = 0   # consecutive frames with low occupancy

        self.initUI()

    # ── UI ─────────────────────────────────────────────────────────────────
    def initUI(self):
        self.setWindowTitle("AI Interview Monitoring System")
        self.setFixedSize(980, 780)
        self.setStyleSheet(f"background-color: {BG_DARK};")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 10, 20, 20)
        root.setSpacing(12)

        # Title
        title = QLabel("🎥  AI Interview Monitoring System")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {TEXT_PRI}; letter-spacing: 1px;")
        root.addWidget(title)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {BORDER};")
        root.addWidget(divider)

        # Content row
        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        # Feed card
        feed_card = self._make_card(650, 490)
        feed_layout = QVBoxLayout(feed_card)
        feed_layout.setContentsMargins(4, 4, 4, 4)

        self.video_label = QLabel("Camera Feed Off")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet(f"color: {TEXT_SEC}; font-size: 16px; border: none;")
        feed_layout.addWidget(self.video_label)

        self.warning_popup = WarningPopup(feed_card)
        self.warning_popup.move(10, 10)
        self.warning_popup.hide()

        content_row.addWidget(feed_card)

        # Stats panel
        stats_frame = self._make_card(260, 490)
        stats_frame.setFixedWidth(260)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setAlignment(Qt.AlignTop)
        stats_layout.setSpacing(10)
        stats_layout.setContentsMargins(16, 20, 16, 20)

        self.status_badge = QLabel("● IDLE")
        self.status_badge.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFixedHeight(40)
        self.status_badge.setStyleSheet(
            f"color: {TEXT_SEC}; background: {PANEL_DARK}; border-radius: 6px;"
            f" border: 1px solid {BORDER};"
        )
        stats_layout.addWidget(self.status_badge)
        stats_layout.addSpacing(10)

        stats_layout.addWidget(self._stat_title("Detection"))
        self.people_label = self._stat_value("People", "0")
        self.occupy_label = self._stat_value("Occupancy", "–")
        self.phones_label = self._stat_value("Phones", "0")
        stats_layout.addWidget(self.people_label)
        stats_layout.addWidget(self.occupy_label)
        stats_layout.addWidget(self.phones_label)
        stats_layout.addSpacing(10)

        stats_layout.addWidget(self._stat_title("Session"))
        self.warnings_label = self._stat_value("Warnings", f"0 / {self.max_warnings}")
        self.fps_label      = self._stat_value("FPS", "0.0")
        stats_layout.addWidget(self.warnings_label)
        stats_layout.addWidget(self.fps_label)
        stats_layout.addStretch()

        content_row.addWidget(stats_frame)
        root.addLayout(content_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        self.start_btn = self._make_button("▶  Start Interview", ACCENT_G, "#009e74")
        self.start_btn.clicked.connect(self.start_interview)
        self.stop_btn = self._make_button("■  Stop Interview", ACCENT_R, "#cc2222")
        self.stop_btn.clicked.connect(self.stop_interview)
        self.stop_btn.setEnabled(False)
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _make_card(self, w=None, h=None):
        card = QFrame()
        if w: card.setFixedWidth(w)
        if h: card.setFixedHeight(h)
        card.setStyleSheet(
            f"QFrame {{ background-color: {PANEL_DARK}; border: 1px solid {BORDER};"
            f" border-radius: 10px; }}"
        )
        return card

    def _stat_title(self, text):
        lbl = QLabel(text.upper())
        lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        lbl.setStyleSheet(f"color: {TEXT_SEC}; letter-spacing: 2px; border: none;")
        return lbl

    def _stat_value(self, key, val):
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background: {BG_DARK}; border-radius: 6px; border: 1px solid {BORDER}; }}"
        )
        hl = QHBoxLayout(row)
        hl.setContentsMargins(10, 6, 10, 6)
        k = QLabel(key)
        k.setFont(QFont("Segoe UI", 10))
        k.setStyleSheet(f"color: {TEXT_SEC}; border: none; background: transparent;")
        v = QLabel(val)
        v.setFont(QFont("Segoe UI", 10, QFont.Bold))
        v.setStyleSheet(f"color: {TEXT_PRI}; border: none; background: transparent;")
        v.setAlignment(Qt.AlignRight)
        hl.addWidget(k)
        hl.addWidget(v)
        row._value_lbl = v
        return row

    def _make_button(self, text, bg, bg_hover):
        btn = QPushButton(text)
        btn.setFixedSize(240, 48)
        btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton          {{ background-color: {bg}; color: #ffffff;
                                   border-radius: 8px; border: none; }}
            QPushButton:hover    {{ background-color: {bg_hover}; }}
            QPushButton:disabled {{ background-color: #333333; color: #555555; }}
        """)
        return btn

    def _set_badge(self, text, color):
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"color: {color}; background: {PANEL_DARK}; border-radius: 6px;"
            f" border: 1px solid {color}; font-weight: bold; font-size: 13px;"
        )

    def _update_stats(self, ppl, occ_pct, phones, fps):
        self.people_label._value_lbl.setText(str(ppl))
        self.phones_label._value_lbl.setText(str(phones))
        self.fps_label._value_lbl.setText(f"{fps:.1f}")
        self.warnings_label._value_lbl.setText(f"{self.warnings} / {self.max_warnings}")

        if occ_pct is None:
            self.occupy_label._value_lbl.setText("–")
            self.occupy_label._value_lbl.setStyleSheet(
                f"color: {TEXT_PRI}; border: none; background: transparent; font-weight: bold;"
            )
        else:
            occ_color = ACCENT_G if occ_pct >= MIN_OCCUPANCY_PCT else ACCENT_R
            self.occupy_label._value_lbl.setText(f"{occ_pct:.0f}%")
            self.occupy_label._value_lbl.setStyleSheet(
                f"color: {occ_color}; border: none; background: transparent; font-weight: bold;"
            )

        warn_color = ACCENT_R if self.warnings >= self.max_warnings else \
                     ACCENT_O if self.warnings > 0 else TEXT_PRI
        self.warnings_label._value_lbl.setStyleSheet(
            f"color: {warn_color}; border: none; background: transparent; font-weight: bold;"
        )

    def _fire_warning(self, message, frame, cooldown_attr, icon, popup_text, popup_color):
        """Log a violation and show a popup, respecting cooldown."""
        if getattr(self, cooldown_attr) == 0:
            self.warnings += 1
            self.logger.log_violation(frame, message)
            setattr(self, cooldown_attr, 120)   # 120 frames ≈ 4 s cooldown
            self.warning_popup.show_message(icon, popup_text, popup_color)

    # ── Main update slot ────────────────────────────────────────────────────
    @pyqtSlot(np.ndarray, list, list, float)
    def update_image(self, cv_img, people, phones, fps):
        if not self.interview_active:
            return

        person_count = len(people)
        phone_count  = len(phones)
        frame_h      = cv_img.shape[0]

        # Tick down cooldowns
        if self.person_cooldown > 0: self.person_cooldown -= 1
        if self.phone_cooldown  > 0: self.phone_cooldown  -= 1

        # Compute occupancy of the largest detected person (% of frame height)
        occupancy_pct = None
        if person_count >= 1:
            largest = max(people, key=lambda p: p[0][3])   # tallest box
            (_, _, _, ph), _ = largest
            occupancy_pct = (ph / frame_h) * 100.0

        # ── TEMPORAL CONSISTENCY LOGIC ──────────────────────────────────────
        # Each counter increments when the condition is TRUE for this frame
        # and resets to 0 when the condition is FALSE.
        # A violation only counts once the counter hits its threshold.

        # Phone check
        if phone_count > 0:
            self._phone_frames += 1
        else:
            self._phone_frames = 0   # condition broke → reset, no warning

        # Multiple person check
        if person_count > 1:
            self._multi_frames += 1
        else:
            self._multi_frames = 0

        # Low occupancy check (only when exactly 1 person visible)
        if person_count == 1 and occupancy_pct is not None and occupancy_pct < MIN_OCCUPANCY_PCT:
            self._occup_frames += 1
        else:
            self._occup_frames = 0

        # ── Decision (highest priority first) ──────────────────────────────
        if self._phone_frames >= PHONE_CONFIRM_FRAMES:
            self._set_badge("📵  PHONE DETECTED", ACCENT_R)
            self._fire_warning(
                "Mobile phone detected", cv_img, "phone_cooldown",
                "📵", "Mobile Phone Detected!\nPlease remove all devices.", ACCENT_R
            )
            # Keep counter capped so it doesn't overflow; re-triggers after cooldown expires
            self._phone_frames = PHONE_CONFIRM_FRAMES

        elif self._multi_frames >= MULTI_CONFIRM_FRAMES:
            self._set_badge("⚠  MULTIPLE PEOPLE", ACCENT_R)
            self._fire_warning(
                "Multiple people detected", cv_img, "person_cooldown",
                "⚠️", "Multiple People Detected!\nOnly one person is allowed.", ACCENT_R
            )
            self._multi_frames = MULTI_CONFIRM_FRAMES

        elif self._occup_frames >= OCCUP_CONFIRM_FRAMES:
            self._set_badge("⚠  TOO FAR", ACCENT_O)
            self._fire_warning(
                f"Person occupancy too low ({occupancy_pct:.0f}%)", cv_img, "person_cooldown",
                "🔍",
                f"Please move closer to the camera.\nOccupancy: {occupancy_pct:.0f}% (need ≥{MIN_OCCUPANCY_PCT}%)",
                ACCENT_O
            )
            self._occup_frames = OCCUP_CONFIRM_FRAMES

        elif person_count == 1:
            self._set_badge("✔  SAFE", ACCENT_G)

        else:
            # No person — not a violation, just informational
            self._set_badge("⚠  NO PERSON", ACCENT_O)

        self._update_stats(person_count, occupancy_pct, phone_count, fps)

        if self.warnings >= self.max_warnings:
            self.terminate_interview()
            return

        # Display frame
        h, w, ch = cv_img.shape
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.video_label.setPixmap(
            QPixmap.fromImage(qt_img.scaled(640, 480, Qt.KeepAspectRatio))
        )

    # ── Interview control ────────────────────────────────────────────────────
    def _reset_counters(self):
        self.warnings        = 0
        self.person_cooldown = 0
        self.phone_cooldown  = 0
        self._phone_frames   = 0
        self._multi_frames   = 0
        self._occup_frames   = 0

    def start_interview(self):
        reply = QMessageBox.question(
            self, "Camera Permission",
            "This app needs webcam access to monitor the interview.\n\nGrant permission?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply == QMessageBox.No:
            QMessageBox.warning(self, "Denied", "Webcam access required. Closing.")
            sys.exit()

        self._reset_counters()
        self.interview_active = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_badge("◉  MONITORING", ACCENT_B)
        self._update_stats(0, None, 0, 0)

        self.thread = VideoThread(self.detector)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.camera_error_signal.connect(self.handle_camera_error)
        self.thread.start()

    def stop_interview(self):
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.stop()
        self.interview_active = False
        self.video_label.clear()
        self.video_label.setText("Camera Feed Off")
        self.warning_popup.hide()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_badge("● IDLE", TEXT_SEC)
        self._update_stats(0, None, 0, 0)
        self.fps_label._value_lbl.setText("0.0")

    def terminate_interview(self):
        self.stop_interview()
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Critical)
        mb.setWindowTitle("Interview Terminated")
        mb.setText("Interview terminated due to malpractice.")
        mb.setInformativeText(
            f"Warning limit ({self.max_warnings}) exceeded.\n"
            "Check the logs/ folder for screenshots and details."
        )
        mb.setStyleSheet(f"""
            QMessageBox {{ background-color: {PANEL_DARK}; color: {TEXT_PRI}; }}
            QLabel       {{ color: {TEXT_PRI}; }}
            QPushButton  {{ background: {ACCENT_R}; color: white; border-radius: 5px;
                           padding: 6px 20px; }}
        """)
        mb.exec_()

    @pyqtSlot(str)
    def handle_camera_error(self, message):
        QMessageBox.critical(self, "Camera Error", message)
        self.stop_interview()

    def closeEvent(self, event):
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.stop()
        event.accept()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = InterviewMonitorApp()
    window.show()
    sys.exit(app.exec_())
