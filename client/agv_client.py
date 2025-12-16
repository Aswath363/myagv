import asyncio
import websockets
import cv2
import json
import base64
import time
import os
from dotenv import load_dotenv
from motor_controller import MotorController

load_dotenv()

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "ws://localhost:8000/ws")
# Try to parse CAMERA_ID as int if possible, else string
_cam_id = os.getenv("CAMERA_ID", "0")
try:
    CAMERA_ID = int(_cam_id)
except ValueError:
    # It's a string, likely a file path or URL
    if _cam_id.startswith("http") or _cam_id.startswith("rtsp"):
         CAMERA_ID = _cam_id
    elif any(char.isdigit() for char in _cam_id) and "." in _cam_id:
        # Heuristic: looks like an IP/URL but missing protocol
        print(f"Assuming HTTP for camera URL: {_cam_id}")
        CAMERA_ID = f"http://{_cam_id}"
    else:
        CAMERA_ID = _cam_id

async def run_agv_client():
    # Initialize Motor Controller
    motor = MotorController()
    
    # Initialize Camera
    cap = cv2.VideoCapture(CAMERA_ID)
    # Reduce resolution for lower latency and bandwidth
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: Could not open video device.")
        return

    print(f"Connecting to {BACKEND_URL}...")
    
    async with websockets.connect(BACKEND_URL) as websocket:
        print("Connected to Backend.")
        
        try:
            while True:
                print("\n[State]: Recording video clip...")
                # Capture 30 frames (~1-2 seconds)
                frames = []
                for _ in range(30):
                    ret, frame = cap.read()
                    if ret:
                        frames.append(frame)
                    # asyncio.sleep isn't blocking the read here, which is fine for capturing
                
                if not frames:
                    print("No frames captured")
                    continue

                # Write to MP4 file
                temp_file = "temp_capture.mp4"
                height, width, _ = frames[0].shape
                # mp4v is widely supported in opencv headless
                fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
                out = cv2.VideoWriter(temp_file, fourcc, 15.0, (width, height))
                
                for f in frames:
                    out.write(f)
                out.release()

                # Read bytes
                with open(temp_file, "rb") as f:
                    video_bytes = f.read()

                # Send video to backend
                print(f"[State]: Sending {len(video_bytes)/1024:.1f} KB video to Brain...")
                await websocket.send(video_bytes)

                # Receive command
                response = await websocket.recv()
                command_data = json.loads(response)
                
                print(f"Received: {command_data}")
                
                # Execute command
                motor.execute_command(command_data)

                # Optional: display the frame locally (might fail if headless)
                # cv2.imshow('MyAGV View', frame)
                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break
                
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by server")
        except KeyboardInterrupt:
            print("Client stopped by user")
        finally:
            motor.stop()
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        asyncio.run(run_agv_client())
    except KeyboardInterrupt:
        pass
