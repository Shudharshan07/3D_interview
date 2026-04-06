import os
import cv2
from datetime import datetime

class ViolationLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.screenshot_dir = os.path.join(self.log_dir, "screenshots")
        self.log_file = os.path.join(self.log_dir, "violations.log")
        
        # Create directories if they don't exist
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    def log_violation(self, frame, message):
        """Logs a violation message and saves a screenshot of the frame."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Save screenshot if frame is provided
        filename = f"violation_{timestamp}.jpg"
        filepath = os.path.join(self.screenshot_dir, filename)
        if frame is not None:
            # Save the frame
            cv2.imwrite(filepath, frame)
        
        # Write to log file
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message} - Screenshot: {filename}\n"
        with open(self.log_file, "a") as f:
            f.write(log_entry)
            
        return filepath
