<div align="center">
  <img src="https://img.shields.io/badge/Status-MVP-brightgreen?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/MediaPipe-FF3366?style=for-the-badge&logo=google" alt="MediaPipe" />
  <img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV" />

  <h1>🧠 NeuroGaze AI - Personal Focus Monitor</h1>
  <p><b>Smart Real-Time Video Analytics System (SRVAS)</b></p>
  <p>An AI-powered operating system module for personalized education, learning assistance, and behavior tracking.</p>
</div>

<hr />

## 📖 Table of Contents
- [About The Project](#-about-the-project)
- [Key Features](#-key-features)
- [Architecture & Tech Stack](#-architecture--tech-stack)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage Guide](#-usage-guide)
  - [Quick Start (Recommended)](#quick-start-recommended)
  - [Manual Execution](#manual-execution)
  - [Docker Setup](#docker-setup)
- [Simulation Deck](#-simulation-deck)
- [Testing](#-testing)
- [Contributing](#-contributing)
- [Acknowledgments](#-acknowledgments)

---

## 🚀 About The Project

**EduMind OS (SRVAS Module)** is a minimalist, real-time focus monitoring system designed to help users track their attention span and learning behaviors. 

By integrating **OpenCV** and **Google MediaPipe**, the system tracks facial landmarks, eye aspect ratios (EAR), and head poses via your webcam. The data is processed locally, aggregated by a **FastAPI backend**, and visualized on a stunning **Glassmorphism Dark-Mode Dashboard** through WebSockets.

---

## ✨ Key Features

* **Real-time Attention Tracking:** Detects states like *Focused*, *Attention Drop*, *Idle*, and *Sleeping (Eyes Closed)*.
* **Privacy-First (No Cloud Processing):** All AI inference (MediaPipe) runs locally on your machine. Raw video frames are **never** saved to disk.
* **Live Dashboard:** Beautiful, responsive UI displaying live video feed, real-time event logs, and dynamic focus score charts using Chart.js.
* **Simulation Mode:** Built-in "Simulation Deck" allows testing and development without a webcam.
* **Adaptive AI Models:** Fallbacks to Haar Cascades if MediaPipe is unavailable or hardware is limited.

---

## 🏗 Architecture & Tech Stack

- **Computer Vision Module:** Python, OpenCV, MediaPipe (FaceMesh & Pose).
- **Backend Server:** FastAPI, Uvicorn, SQLAlchemy (SQLite), WebSockets.
- **Frontend Dashboard:** Vanilla HTML/CSS/JS, Chart.js, Glassmorphism UI.

### 📁 Project Structure

```text
neurogaze-ai/
├── backend/                  # FastAPI server, WebSockets, & Aggregation logic
│   ├── main.py               # API entry point & WebSocket handlers
│   ├── aggregator.py         # AI Event Aggregator & Analyzer
│   ├── database.py           # SQLAlchemy setup
│   └── models.py             # SQLite Database Models
├── cv/                       # Computer Vision & MediaPipe Pipeline
│   ├── main.py               # Webcam capture & CV loop
│   ├── detector.py           # Pose & FaceMesh detection logic
│   └── event_generator.py    # Formatting CV results into JSON events
├── dashboard/                # Frontend UI
│   ├── index.html            # Main UI layout
│   ├── style.css             # Glassmorphism styling
│   └── script.js             # WebSocket connection & Chart.js logic
├── docker-compose.yml        # Docker composition file
├── Dockerfile                # Docker image build instructions
├── requirements.txt          # Python dependencies
└── run.sh                    # All-in-one startup script
```

---

## 🛠 Getting Started

### Prerequisites
- Python 3.10 or higher
- Git
- Webcam (Optional, can use Simulator)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/neurogaze-ai.git
   cd neurogaze-ai
   ```

2. **Create a Python Virtual Environment:**
   * **macOS/Linux**:
     ```bash
     python3 -m venv venv
     ```
   * **Windows**:
     ```cmd
     python -m venv venv
     ```

3. **Activate the Environment:**
   * **macOS/Linux**: `source venv/bin/activate`
   * **Windows**: `venv\Scripts\activate`

4. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🎮 Usage Guide

### Quick Start (Recommended for macOS/Linux)
We provide a convenient bash script that automatically activates the environment, boots up the backend, opens your browser, and starts the AI vision module.

```bash
chmod +x run.sh
./run.sh
```
*To stop the entire system, simply press `Ctrl+C` in the terminal.*

### Manual Execution (Step-by-Step)
If you prefer running services individually (ideal for debugging or Windows users):

1. **Start the Backend Server (Terminal 1):**
   * **macOS/Linux**:
     ```bash
     source venv/bin/activate
     PYTHONPATH=backend uvicorn main:app --host 0.0.0.0 --port 8000 --reload
     ```
   * **Windows**:
     ```cmd
     venv\Scripts\activate
     set PYTHONPATH=backend
     uvicorn main:app --host 0.0.0.0 --port 8000 --reload
     ```

2. **Start the Computer Vision Module (Terminal 2):**
   * **macOS/Linux**:
     ```bash
     source venv/bin/activate
     python3 cv/main.py
     ```
   * **Windows**:
     ```cmd
     venv\Scripts\activate
     python cv/main.py
     ```

3. **Access Dashboard:** Open your browser and navigate to `http://localhost:8000/`.

### Docker Setup
To spin up the backend and dashboard in an isolated container:
```bash
docker-compose up --build
```
*(Note: Docker setup currently runs the backend/dashboard. Running the webcam CV module inside Docker requires additional hardware passthrough configurations).*

---

## 🧪 Simulation Deck

Don't have a webcam or want to test the UI metrics quickly? Use the built-in **Simulation Deck**:
1. Open the Dashboard (`http://localhost:8000/`).
2. Locate the **CV Simulation Deck** panel.
3. Click **Simulate Focus** to mimic an attentive user (`PERSON_DETECTED`).
4. Click **Simulate Distracted** to mimic an inattentive user (`NO_PERSON`).
5. Watch the Focus Score, Chart, and Event Logs update in real-time (within ~5 seconds aggregation cycles).

---

## 🛠 Automated Tests

To verify backend API and WebSocket stability:
```bash
source venv/bin/activate
PYTHONPATH=backend pytest backend/test_backend.py
```
*Tests are executed safely on a temporary SQLite database (`test_srvas.db`) which is automatically cleaned up afterward.*

---

## 🤝 Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


## 🙏 Acknowledgments

* [FastAPI](https://fastapi.tiangolo.com/)
* [MediaPipe](https://google.github.io/mediapipe/)
* [OpenCV](https://opencv.org/)
* [Chart.js](https://www.chartjs.org/)

