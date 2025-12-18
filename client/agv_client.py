import asyncio
import websockets
import cv2
import numpy as np
import json
import time
import os
import platform
import threading
from dotenv import load_dotenv
from motor_controller import MotorController

load_dotenv()

# Detect platform for camera backend selection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "ws://localhost:8000/ws")


def parse_camera_id(cam_id_str):
    """Parse camera ID from string - could be int, device path, or URL."""
    if not cam_id_str or cam_id_str.lower() == "none":
        return None
    try:
        return int(cam_id_str)
    except ValueError:
        if cam_id_str.startswith(("http", "rtsp", "tcp", "/dev/")):
            return cam_id_str
        return cam_id_str


# RGB Camera
CAMERA_ID = parse_camera_id(os.getenv("CAMERA_ID", "0"))


def get_platform_backend():
    """Get the appropriate camera backend for the current OS."""
    if IS_WINDOWS:
        return cv2.CAP_DSHOW
    elif IS_LINUX:
        return cv2.CAP_V4L2
    else:
        return cv2.CAP_ANY


class BufferlessVideoCapture:
    """
    A wrapper around cv2.VideoCapture that continuously reads frames in a
    background thread, ensuring only the latest frame is ever returned.
    This provides stable RGB streaming.
    """
    def __init__(self, name, backend=None):
        if backend is not None:
            self.cap = cv2.VideoCapture(name, backend)
        elif isinstance(name, int):
            platform_backend = get_platform_backend()
            print(f"Using camera index {name} with backend: {'DSHOW' if IS_WINDOWS else 'V4L2' if IS_LINUX else 'ANY'}")
            self.cap = cv2.VideoCapture(name, platform_backend)
        elif isinstance(name, str) and name.startswith("/dev/video"):
            print(f"Using device path {name} with V4L2 backend")
            self.cap = cv2.VideoCapture(name, cv2.CAP_V4L2)
        else:
            self.cap = cv2.VideoCapture(name)
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.lock = threading.Lock()
        self.latest_frame = None
        self.running = True
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.latest_frame = frame
            time.sleep(0.01)

    def read(self):
        with self.lock:
            if self.latest_frame is not None:
                return True, self.latest_frame.copy()
            return False, None

    def isOpened(self):
        return self.cap.isOpened()

    def release(self):
        self.running = False
        self.thread.join(timeout=1.0)
        self.cap.release()


async def run_agv_client():
    motor = MotorController()
    
    print(f"Initializing RGB Camera: {CAMERA_ID}")
    cap = BufferlessVideoCapture(CAMERA_ID)
    time.sleep(1.0) # Allow camera to warm up
    
    if not cap.isOpened():
        print("Error: Could not open RGB camera.")
        return

    print(f"Connecting to {BACKEND_URL}...")
    
    async with websockets.connect(BACKEND_URL) as websocket:
        print("Connected to Backend.")
        
        try:
            while True:
                print("\n[State]: Getting frame...")
                
                # Get RGB frame
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("Failed to grab frame")
                    await asyncio.sleep(0.1)
                    continue
                
                # Encode to JPEG
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                image_bytes = buffer.tobytes()

                print(f"[State]: Sending {len(image_bytes)/1024:.1f} KB RGB image...")
                await websocket.send(image_bytes)

                # Receive command
                response = await websocket.recv()
                command_data = json.loads(response)
                
                print(f"Received: {command_data}")
                motor.execute_command(command_data)
                
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
