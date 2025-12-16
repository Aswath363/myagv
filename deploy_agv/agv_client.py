import asyncio
import websockets
import cv2
import json
import base64
import time
import os
import argparse
from motor_controller import MotorController

# Default settings that can be overridden by env vars or args
DEFAULT_BACKEND_URL = "ws://192.168.2.100:8000/ws" # REPLACE with your PC's IP address
DEFAULT_CAMERA_ID = "0" # 0 for onboard USB camera

async def run_agv_client(backend_url, camera_id):
    # Initialize Motor Controller
    motor = MotorController()
    
    # Initialize Camera
    print(f"Opening camera: {camera_id} ...")
    # Convert camera_id to int if it's a digit
    try:
        cam_source = int(camera_id)
    except ValueError:
        cam_source = camera_id
        
    cap = cv2.VideoCapture(cam_source)
    
    # Optimize for latency on Jetson
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 10) # Limit FPS to reduce load/network

    if not cap.isOpened():
        print(f"Error: Could not open video device {cam_source}.")
        return

    print(f"Connecting to Backend: {backend_url} ...")
    
    while True:
        try:
            async with websockets.connect(backend_url) as websocket:
                print("Connected to Vision Backend.")
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        print("Failed to grab frame")
                        time.sleep(0.1)
                        continue

                    # Encode frame to JPEG with lower quality for speed
                    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
                    image_bytes = buffer.tobytes()

                    # Send frame to backend
                    try:
                        await websocket.send(image_bytes)

                        # Receive command (wait for response before sending next frame)
                        response = await websocket.recv()
                        command_data = json.loads(response)
                        
                        # Execute command
                        motor.execute_command(command_data)
                        
                    except websockets.exceptions.ConnectionClosed:
                        print("Connection lost. Reconnecting...")
                        break
                        
        except (OSError, ConnectionRefusedError) as e:
            print(f"Connection failed: {e}. Retrying in 3 seconds...")
            motor.stop()
            time.sleep(3)
        except KeyboardInterrupt:
            print("Stopping AGV Client...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(1)
            
    # Cleanup
    motor.stop()
    cap.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MyAGV Vision Client')
    parser.add_argument('--url', type=str, default=os.environ.get('BACKEND_URL', DEFAULT_BACKEND_URL), 
                        help='WebSocket URL of the backend (e.g., ws://192.168.1.5:8000/ws)')
    parser.add_argument('--camera', type=str, default=os.environ.get('CAMERA_ID', DEFAULT_CAMERA_ID),
                        help='Camera ID (0) or URL')
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_agv_client(args.url, args.camera))
    except KeyboardInterrupt:
        pass
