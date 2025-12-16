# MyAGV 2023 JN + Gemini 2.5 Flash Vision-Based Control System

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              MyAGV 2023 JN (Jetson Nano)                │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Video Capture (USB Camera / Jetson CSI Camera)   │   │
│  └───────┬──────────────────────────────────────────┘   │
│          │ H.264/MJPEG stream                           │
│          ▼                                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │ MyAGV Client (Python)                            │   │
│  │ - WebSocket connection to backend                │   │
│  │ - Send video frames in real-time                 │   │
│  │ - Receive movement commands                      │   │
│  │ - Execute motor control via pymycobot/ROS        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────┘
                  │ WebSocket (video frames + commands)
                  │
                  ▼
      ┌───────────────────────────┐
      │  FastAPI Backend Service  │
      │  (Google Cloud Run/Render)│
      │  ┌─────────────────────┐  │
      │  │ Gemini 2.5 Flash    │  │
      │  │ Video Processing    │  │
      │  │ - Receive frames    │  │
      │  │ - Analyze with AI   │  │
      │  │ - Generate commands │  │
      │  └─────────────────────┘  │
      │                           │
      │  Command Queue/Buffer     │
      └───────────────────────────┘
```

## Key Components

### MyAGV Side (Client)
- **Video Streaming**: Capture from camera → encode → send to backend
- **Command Execution**: Receive movement commands → control motors
- **Connection Management**: Reconnect handling, frame dropping if network slow
- **Safety**: Timeout-based stop if connection lost

### Backend Side (Processing)
- **Video Reception**: WebSocket stream handler
- **AI Processing**: Send to Gemini 2.5 Flash with context
- **Command Generation**: Parse AI response → movement commands
- **State Management**: Track AGV state, frame buffer, command history

## Installation & Deployment

### Frontend (MyAGV)
```bash
pip install pymycobot websockets opencv-python numpy
```

### Backend
```bash
pip install fastapi uvicorn python-multipart websockets google-genai
```

## Supported Movements

- **Navigation**: Forward, backward, turn left/right, stop
- **Speed Control**: 0-100% velocity
- **Precision**: Fine-tuned movements based on vision feedback
- **Safety**: Automatic stop on obstacles

## Deployment Options

1. **Backend**: Google Cloud Run, Railway, Render, local server
2. **MyAGV**: Runs on Jetson Nano Ubuntu 20.04 (onboard)
3. **Communication**: Public internet or local network WebSocket

## Key Benefits

✅ Distributed processing (backend heavy lifting)
✅ Real-time vision-based navigation
✅ Low latency commands to motors
✅ Scalable backend independent of robot hardware
✅ Easy to iterate on vision logic without touching robot code
