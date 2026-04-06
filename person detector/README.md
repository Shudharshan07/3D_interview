# AI-Powered Interview Monitoring System

This project is an automated AI system for detecting malpractice during a virtual interview. It uses a webcam, computer vision, and real-time inference to monitor the candidate's behavior.

## Features

1. **Camera Permission Handling**: The system prompts for the candidate's consent before using their camera feed, immediately terminating if denied.
2. **Real-Time Single Person Detection**: Uses Google's MediaPipe model to aggressively detect faces with low latency.
3. **Malpractice Warnings**:
   - Throws a warning and takes a screenshot if **no face** is detected.
   - Throws a warning and takes a screenshot if **multiple people** are detected in the frame.
4. **Auto-Termination**: If the warning count exceeds 3, the session is forcefully terminated due to potential cheating.
5. **Robust GUI**: Built with PyQt5. Displays face tracking percentage bounds, FPS counter, detection status, and warning counts visually.
6. **Detailed Logging**: Logs violations continuously with a `violations.log` text file alongside the captured snapshot image.

## Directory Structure

```text
├── main.py        - The entry point. Handles the PyQt5 Application and video thread rendering.
├── detector.py    - Abstraction layer on MediaPipe. Provides simple face detection lists.
├── logger.py      - Stores violation events incrementally along with snapshot tracking.
├── requirements.txt - Required pip packages.
└── logs/          - Directory auto-created on run. Stores screenshots and logs.
```

## How to Run

1. **Install python** (Ideally 3.8+).
2. **Navigate** into this directory and **install** the required dependencies.
   ```bash
   pip install -r requirements.txt
   ```
3. Run the **Application script**:
   ```bash
   python main.py
   ```

## Workflow Demonstration
- Wait for GUI load and tap "Ask Camera Permission & Start"
- Accept the security popup to allow hardware webcam polling.
- Make sure multiple faces exist to trigger a warning, or hide your face to trigger a warning.
- Check the `./logs` directory for full traceability of snapshots and log records.
