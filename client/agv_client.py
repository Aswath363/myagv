import asyncio
import websockets
import cv2
import json
import time
import os
import sys
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
# Try to parse CAMERA_ID as int if possible, else string
_cam_id = os.getenv("CAMERA_ID", "0")
try:
    CAMERA_ID = int(_cam_id)
except ValueError:
    # It's a string, likely a file path or URL
    if _cam_id.startswith("http") or _cam_id.startswith("rtsp") or _cam_id.startswith("tcp"):
         CAMERA_ID = _cam_id
    elif any(char.isdigit() for char in _cam_id) and "." in _cam_id:
        # Heuristic: looks like an IP/URL but missing protocol
        print(f"Assuming HTTP for camera URL: {_cam_id}")
        CAMERA_ID = f"http://{_cam_id}"
    else:
        CAMERA_ID = _cam_id


def get_platform_backend():
    """Get the appropriate camera backend for the current OS."""
    if IS_WINDOWS:
        return cv2.CAP_DSHOW  # DirectShow for Windows
    elif IS_LINUX:
        return cv2.CAP_V4L2   # Video4Linux2 for Linux
    else:
        return cv2.CAP_ANY    # Default for other platforms


class BufferlessVideoCapture:
    """
    A wrapper around cv2.VideoCapture that continuously reads frames in a
    background thread, ensuring only the latest frame is ever returned.
    This solves the stale buffer problem when processing is slow.
    
    For Orbbec Astra Pro 2:
    - Windows: Uses DirectShow (CAP_DSHOW), RGB camera typically at index 2
    - Linux: Uses V4L2 (CAP_V4L2), RGB camera typically at /dev/video4 or index 4
    """
    def __init__(self, name, backend=None):
        # Use platform-specific backend for Orbbec Astra Pro 2 RGB camera
        # This is required because the camera exposes multiple interfaces (RGB, IR, Depth)
        # and the default backend may pick the wrong one
        if backend is not None:
            self.cap = cv2.VideoCapture(name, backend)
        elif isinstance(name, int):
            # For integer indices, use platform-specific backend
            platform_backend = get_platform_backend()
            print(f"Using camera index {name} with backend: {'DSHOW' if IS_WINDOWS else 'V4L2' if IS_LINUX else 'ANY'}")
            self.cap = cv2.VideoCapture(name, platform_backend)
        elif isinstance(name, str) and name.startswith("/dev/video"):
            # For Linux device paths like /dev/video4, use V4L2 backend
            print(f"Using device path {name} with V4L2 backend")
            self.cap = cv2.VideoCapture(name, cv2.CAP_V4L2)
        else:
            # For URLs or other paths, use default backend
            self.cap = cv2.VideoCapture(name)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.lock = threading.Lock()
        self.latest_frame = None
        self.running = True
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        """Continuously reads frames, keeping only the latest one."""
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.latest_frame = frame
            # Small sleep to prevent CPU spinning if camera is slow
            time.sleep(0.01)

    def read(self):
        """Returns the most recent frame."""
        with self.lock:
            return self.latest_frame is not None, self.latest_frame.copy() if self.latest_frame is not None else None

    def isOpened(self):
        return self.cap.isOpened()

    def release(self):
        self.running = False
        self.thread.join(timeout=1.0)
        self.cap.release()


async def run_agv_client():
    # Initialize Motor Controller
    motor = MotorController()
    
    # Initialize Camera with Bufferless wrapper
    print("Initializing Bufferless Camera...")
    cap = BufferlessVideoCapture(CAMERA_ID)
    
    # Give the reader thread a moment to get the first frame
    time.sleep(0.5)

    if not cap.isOpened():
        print("Error: Could not open video device.")
        return

    print(f"Connecting to {BACKEND_URL}...")
    
    async with websockets.connect(BACKEND_URL) as websocket:
        print("Connected to Backend.")
        
        try:
            while True:
                print("\n[State]: Getting latest frame...")
                
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("Failed to grab frame")
                    await asyncio.sleep(0.1)
                    continue

                # Encode frame to JPEG
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                image_bytes = buffer.tobytes()

                # Send frame to backend
                print(f"[State]: Sending {len(image_bytes)/1024:.1f} KB image to Brain...")
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
