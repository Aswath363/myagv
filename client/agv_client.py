import asyncio
import websockets
import cv2
import numpy as np
import json
import time
import os
import platform
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


def capture_single_frame(camera_id):
    """
    Open a camera, capture ONE frame, then close it immediately.
    This avoids having multiple cameras open simultaneously.
    """
    if camera_id is None:
        return None
    
    backend = get_platform_backend()
    
    # Open camera
    if isinstance(camera_id, int):
        cap = cv2.VideoCapture(camera_id, backend)
    elif isinstance(camera_id, str) and camera_id.startswith("/dev/video"):
        cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(camera_id)
    
    if not cap.isOpened():
        print(f"Failed to open camera: {camera_id}")
        return None
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Grab a few frames to let camera stabilize (auto-exposure, etc.)
    for _ in range(5):
        cap.read()
    
    # Capture the actual frame
    ret, frame = cap.read()
    
    # IMMEDIATELY release the camera
    cap.release()
    
    if ret and frame is not None:
        return frame
    return None


def colorize_depth(depth_frame):
    """
    Convert depth frame to colorized visualization.
    Red = close, Blue = far
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
    
    # Apply colormap (invert so close=red, far=blue)
    inverted = 255 - normalized
    colorized = cv2.applyColorMap(inverted, cv2.COLORMAP_JET)
    
    return colorized


def create_side_by_side(rgb_frame, depth_frame):
    """
    Create a side-by-side composite of RGB and colorized depth.
    """
    if rgb_frame is None:
        return None
        
    if depth_frame is None:
        return rgb_frame
    
    h, w = rgb_frame.shape[:2]
    
    # Colorize depth
    depth_colored = colorize_depth(depth_frame)
    if depth_colored is None:
        return rgb_frame
    
    # Resize depth to match RGB
    depth_resized = cv2.resize(depth_colored, (w, h))
    
    # Create side-by-side
    composite = np.hstack((rgb_frame, depth_resized))
    
    # Add labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(composite, "RGB", (10, 30), font, 0.8, (255, 255, 255), 2)
    cv2.putText(composite, "DEPTH (Red=Close, Blue=Far)", (w + 10, 30), font, 0.6, (255, 255, 255), 2)
    
    return composite


async def run_agv_client():
    motor = MotorController()
    
    print(f"RGB Camera: {CAMERA_ID}")
    print(f"Depth Camera: {DEPTH_CAMERA_ID}")
    print(f"Connecting to {BACKEND_URL}...")
    
    async with websockets.connect(BACKEND_URL) as websocket:
        print("Connected to Backend.")
        
        try:
            while True:
                print("\n[State]: Capturing frames sequentially...")
                
                # Step 1: Capture RGB frame
                print("  -> Capturing RGB...")
                rgb_frame = capture_single_frame(CAMERA_ID)
                if rgb_frame is None:
                    print("Failed to capture RGB frame")
                    await asyncio.sleep(0.5)
                    continue
                print("  -> RGB captured!")
                
                # Step 2: Capture Depth frame (if enabled)
                depth_frame = None
                if DEPTH_CAMERA_ID is not None:
                    print("  -> Capturing Depth...")
                    time.sleep(0.2)  # Small delay between camera switches
                    depth_frame = capture_single_frame(DEPTH_CAMERA_ID)
                    if depth_frame is not None:
                        print("  -> Depth captured!")
                    else:
                        print("  -> Depth capture failed, using RGB only")
                
                # Step 3: Create composite
                composite = create_side_by_side(rgb_frame, depth_frame)
                
                # Step 4: Encode and send
                _, buffer = cv2.imencode('.jpg', composite, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                image_bytes = buffer.tobytes()

                frame_type = "RGB+Depth" if depth_frame is not None else "RGB only"
                print(f"[State]: Sending {len(image_bytes)/1024:.1f} KB {frame_type} image...")
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
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        asyncio.run(run_agv_client())
    except KeyboardInterrupt:
        pass
