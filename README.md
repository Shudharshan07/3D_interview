# team19
# CrackAI - 3D AI Interviewer System

An advanced, AI-driven recruitment platform designed to automate and enhance the interview process using 3D avatars, real-time response analysis, and multi-modal interaction.

---

## Introduction

The CrackAI system addresses the time-consuming nature of traditional recruitment by providing an automated interviewer that can:
- Generate contextually relevant interview questions based on job descriptions and candidate resumes.
- Conduct live interviews through a 3D-rendered character (React Three Fiber).
- Real-time transcription and parsing of candidate responses.
- Automated evaluation and performance scoring using fine-tuned Llama models.
- Generate structured interview reports for HR review.

---

## Core Features

### 1. Interactive 3D Interviewing Experience
A realistic 3D interviewer character that interacts with candidates in real-time, providing a more engaging and immersive experience than traditional text-based interfaces.

### 2. Intelligent Question Generation
The system utilizes AI to analyze candidate resumes and job descriptions (JDs) to generate personalized, context-aware interview questions.

### 3. Voice and Text Multi-modal Interaction
Full support for voice-based interviews with real-time speech-to-text (STT) and text-to-speech (TTS) capabilities, allowing candidates to communicate naturally.

### 4. Technical Skills Evaluation
Automated scoring and qualitative feedback for candidate responses, powered by state-of-the-art Large Language Models (LLMs).

### 5. Collaborative Whiteboard Integration
An integrated whiteboard for technical interviews, allowing candidates to illustrate concepts and architectural designs during the session.

### 6. Real-time Monitoring and Presence Detection
Computer vision-based monitoring to detect candidate presence and ensure the integrity of the interview process.

### 7. Automated Performance Reporting
Instant generation of structured candidate assessment reports with detailed scoring and qualitative feedback.

---

## Technology Stack

### Frontend
- **Framework**: React.js with Vite
- **Language**: TypeScript
- **3D Rendering**: Three.js, React Three Fiber (R3F), React Three Drei
- **Integration**: WebSockets for real-time synchronization

### Backend
- **Framework**: Django, Django REST Framework
- **Language**: Python
- **Database**: MySQL
- **Task Queue**: Celery with Redis as the message broker
- **Reporting**: ReportLab for PDF generation

### Real-time Communication
- **Engine**: Golang-based WebSocket server
- **Protocol**: Custom WebSocket protocol for session management

### AI and Machine Learning
- **Inference**: Groq API (LLAMA 3.3 70B), Llama 3.2 3B (fine-tuned)
- **Voice Engine**: Sarvam API for high-quality TTS and STT

---

## System Architecture

The project follows a distributed service architecture designed for low latency and high scalability:
1. **Frontend (Candidate Portal)**: Manages 3D rendering, user interaction, and data submission.
2. **Backend (API Service)**: Provides core business logic, user authentication, data persistence, and task orchestration.
3. **WebSocket Hub**: Enables low-latency communication between the candidate and the assessment logic.
4. **Celery Infrastructure**: Handles compute-intensive operations like evaluation and report generation outside the main request-response cycle.
5. **Computer Vision Module**: A standalone module for monitoring candidate presence during the interview.

---

## Installation and Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Go 1.20+
- MySQL Server
- Redis Server
- Windows Terminal (recommended for using the `run.py` script)

### Step 1: Environment Configuration
Create a `.env` file in the `backend/` directory with the following variables:
```env
# API Keys
GROQ_API_KEY=your_groq_api_key
SARVAM_API_KEY=your_sarvam_api_key

# Configuration
GROQ_MODEL=llama-3.3-70b-versatile
DATABASE_URL=mysql://user:password@127.0.0.1:3306/interview
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
```

### Step 2: Database Setup
```bash
python backend/manage.py migrate
```

### Step 3: Run the System
The project includes a standard runner script `run.py` that initializes all services simultaneously. Open a terminal and execute:
```bash
python run.py
```
This script will start:
- **Frontend Development Server** (Port 5173)
- **Django Backend Server** (Port 8000)
- **Go WebSocket Server** (Port 8080)
- **Celery Workers** (General and Inference)

---

## Project Structure

```text
team19/
├── admin/            # Administrative dashboard (Vite/React)
├── backend/          # Core API service (Django)
├── finetunning/      # AI model training and localized inference
├── frontend/         # Main candidate interface (3D/React)
├── websocket/        # Real-time synchronization hub (Go)
├── person detector/  # CV components for candidate presence detection
├── docker-compose.yml# Containerization configuration
└── run.py            # Master orchestration script
```

---

## Future Roadmap
- Implementation of sentiment and emotion analysis to track candidate confidence.
- Multi-lingual support for interviewed candidates in various regions.
- Integration with popular Applicant Tracking Systems (ATS) for seamless recruitment workflows.
- Enhanced 3D character animations and lip-syncing for better realism.