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
                print("\n[State]: Capturing fresh view...")
                # Flush buffer to get latest frame
                for _ in range(5):
                    cap.grab()
                
                ret, frame = cap.read()
                if not ret:
                    print("Failed to grab frame")
                    time.sleep(0.1)
                    continue

                # Encode frame to JPEG
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                image_bytes = buffer.tobytes()

                # Send frame to backend
                print("[State]: Sending to Brain (Gemini)...")
                await websocket.send(image_bytes)

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
