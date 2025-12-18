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

# Depth Camera (optional)
DEPTH_CAMERA_ID = parse_camera_id(os.getenv("DEPTH_CAMERA_ID", "none"))


def get_platform_backend():
    """Get the appropriate camera backend for the current OS."""
    if IS_WINDOWS:
        return cv2.CAP_DSHOW
    elif IS_LINUX:
        return cv2.CAP_V4L2
    else:
        return cv2.CAP_ANY


def colorize_depth(depth_frame):
    """
    Convert depth frame to colorized visualization.
    Blue = far, Red = close (like thermal imaging for distance)
    """
    if depth_frame is None:
        return None
    
    # Convert to grayscale if needed
    if len(depth_frame.shape) == 3:
        gray = cv2.cvtColor(depth_frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = depth_frame
    
    # Normalize to 0-255 range
    normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    normalized = np.uint8(normalized)
    
    # Apply colormap (COLORMAP_JET: blue=far, red=close)
    # Invert so that close objects are red (high values become low)
    inverted = 255 - normalized
    colorized = cv2.applyColorMap(inverted, cv2.COLORMAP_JET)
    
    return colorized


def create_side_by_side(rgb_frame, depth_frame):
    """
    Create a side-by-side composite of RGB and colorized depth.
    Returns a single image with RGB on left, depth on right.
    """
    if depth_frame is None:
        # No depth camera, just return RGB
        return rgb_frame
    
    # Ensure both frames are same height
    h, w = rgb_frame.shape[:2]
    
    # Colorize depth
    depth_colored = colorize_depth(depth_frame)
    
    if depth_colored is None:
        return rgb_frame
    
    # Resize depth to match RGB dimensions
    depth_resized = cv2.resize(depth_colored, (w, h))
    
    # Create side-by-side composite
    composite = np.hstack((rgb_frame, depth_resized))
    
    # Add labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(composite, "RGB", (10, 30), font, 0.8, (255, 255, 255), 2)
    cv2.putText(composite, "DEPTH (Red=Close, Blue=Far)", (w + 10, 30), font, 0.6, (255, 255, 255), 2)
    
    return composite


class BufferlessVideoCapture:
    """
    A wrapper around cv2.VideoCapture that continuously reads frames in a
    background thread, ensuring only the latest frame is ever returned.
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
    
    # Initialize RGB Camera first
    print(f"Initializing RGB Camera: {CAMERA_ID}")
    rgb_cap = BufferlessVideoCapture(CAMERA_ID)
    time.sleep(1.0)  # Longer delay for stability
    
    if not rgb_cap.isOpened():
        print("Error: Could not open RGB camera.")
        return
    
    print("RGB camera ready!")
    
    # Initialize Depth Camera (optional) - with extra safety
    depth_cap = None
    if DEPTH_CAMERA_ID is not None:
        print(f"Initializing Depth Camera: {DEPTH_CAMERA_ID}")
        time.sleep(1.0)  # Wait before opening second camera
        
        try:
            depth_cap = BufferlessVideoCapture(DEPTH_CAMERA_ID)
            time.sleep(1.0)  # Wait for depth camera to stabilize
            
            if not depth_cap.isOpened():
                print("Warning: Could not open depth camera. Continuing with RGB only.")
                depth_cap = None
            else:
                print("Depth camera ready!")
        except Exception as e:
            print(f"Warning: Depth camera failed ({e}). Continuing with RGB only.")
            depth_cap = None
    else:
        print("Depth camera disabled (DEPTH_CAMERA_ID not set)")

    print(f"Connecting to {BACKEND_URL}...")
    
    async with websockets.connect(BACKEND_URL) as websocket:
        print("Connected to Backend.")
        
        try:
            while True:
                print("\n[State]: Getting latest frames...")
                
                # Get RGB frame
                ret_rgb, rgb_frame = rgb_cap.read()
                if not ret_rgb or rgb_frame is None:
                    print("Failed to grab RGB frame")
                    await asyncio.sleep(0.1)
                    continue
                
                # Get Depth frame (if available)
                depth_frame = None
                if depth_cap is not None:
                    ret_depth, depth_frame = depth_cap.read()
                    if not ret_depth:
                        depth_frame = None
                
                # Create side-by-side composite
                composite = create_side_by_side(rgb_frame, depth_frame)
                
                # Encode composite to JPEG
                _, buffer = cv2.imencode('.jpg', composite, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                image_bytes = buffer.tobytes()

                # Send frame to backend
                frame_type = "RGB+Depth" if depth_frame is not None else "RGB only"
                print(f"[State]: Sending {len(image_bytes)/1024:.1f} KB {frame_type} image to Brain...")
                await websocket.send(image_bytes)

                # Receive command
                response = await websocket.recv()
                command_data = json.loads(response)
                
                print(f"Received: {command_data}")
                
                # Execute command
                motor.execute_command(command_data)
                
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by server")
        except KeyboardInterrupt:
            print("Client stopped by user")
        finally:
            motor.stop()
            rgb_cap.release()
            if depth_cap:
                depth_cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        asyncio.run(run_agv_client())
    except KeyboardInterrupt:
        pass
