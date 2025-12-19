import asyncio
import websockets
import cv2
import numpy as np
import json
import time
import os
import platform
import math
import threading
from dotenv import load_dotenv
from motor_controller import MotorController
from lidar_driver import LidarDriver

load_dotenv()

# Detect platform for camera backend selection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "ws://localhost:8000/ws")
LIDAR_PORT = os.getenv("LIDAR_PORT", "/dev/ttyTHS1" if IS_LINUX else "COM3")


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


def draw_lidar_view(scan, size=(480, 480), max_dist_mm=4000):
    """
    Draws a 2D radar view of the lidar scan.
    scan: dict {angle_deg: dist_mm}
    """
    # Create black background
    img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    cx, cy = size[0] // 2, size[1] // 2
    
    # Draw reference rings (1m, 2m, 3m)
    scale = min(cx, cy) / max_dist_mm # px per mm
    
    cv2.circle(img, (cx, cy), int(1000 * scale), (50, 50, 50), 1) # 1m
    cv2.circle(img, (cx, cy), int(2000 * scale), (50, 50, 50), 1) # 2m
    cv2.circle(img, (cx, cy), int(3000 * scale), (50, 50, 50), 1) # 3m
    
    # Draw axes
    cv2.line(img, (cx, 0), (cx, size[1]), (30, 30, 30), 1)
    cv2.line(img, (0, cy), (size[0], cy), (30, 30, 30), 1)
    
    # Draw Robot (Triangle)
    pts = np.array([[cx, cy-10], [cx-7, cy+7], [cx+7, cy+7]], np.int32)
    cv2.fillPoly(img, [pts], (0, 0, 255))
    
    # Draw Points
    if not scan:
        cv2.putText(img, "NO LIDAR DATA", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return img
        
    for angle, dist in scan.items():
        if dist <= 0 or dist > max_dist_mm: continue
        
        # Convert polar to cartesian
        # Lidar angle 0 is usually front or back, need to verify orientation for specific unit
        # Standard X4/RPLidar often 0 is front, clockwise positive
        # Mathematical: x = d * cos(a), y = d * sin(a)
        # Screen: y is inverted (top is 0) -> y = cy - d*sin(a)
        # Correct 0-up angle: theta = angle - 90?
        # Let's assume 0 is Front for now.
        
        rad = math.radians(angle)
        # If 0 is front (North), then x = sin, y = cos.
        # But commonly 0 is East. 
        # For YDLidar X4, usually 0 is aligned with the cable notch.
        # Assuming standard polar coordinate processing:
        # x = dist * cos(rad)
        # y = dist * sin(rad)
        
        # Map to screen pixels (cx, cy is origin)
        # We rotate -90 so 0 is up
        px = cx + int(dist * scale * math.cos(rad))
        py = cy - int(dist * scale * math.sin(rad)) # Minus because Y is down
        
        # Color based on distance (Red=Close, Green=Far)
        if dist < 500:
            color = (0, 0, 255)
        elif dist < 1500:
            color = (0, 255, 255)
        else:
            color = (0, 255, 0)
            
        cv2.circle(img, (px, py), 2, color, -1)
        
    return img


def check_safety(scan, safety_dist=300):
    """
    Returns True if safe, False if obstacle detected in front.
    Front sector: 330 deg to 30 deg.
    """
    if not scan: return True
    
    min_front_dist = float('inf')
    
    # Check angles -30 to +30 (handled as 330-360 and 0-30)
    for ang, dist in scan.items():
        if dist <= 0: continue
        if ang < 30 or ang > 330:
            if dist < min_front_dist:
                min_front_dist = dist
                
    if min_front_dist < safety_dist:
        print(f"[Safety] Obstacle detected at {min_front_dist:.1f}mm!")
        return False
        
    return True


async def run_agv_client():
    motor = MotorController()
    
    # Init Lidar
    print(f"Initializing LiDAR on {LIDAR_PORT}...")
    lidar = LidarDriver(LIDAR_PORT)
    lidar.start()
    
    print(f"Initializing RGB Camera: {CAMERA_ID}")
    cap = BufferlessVideoCapture(CAMERA_ID)
    time.sleep(1.0) # Allow camera to warm up
    
    if not cap.isOpened():
        print("Error: Could not open RGB camera.")
        lidar.stop()
        return

    print(f"Connecting to {BACKEND_URL}...")
    
    async with websockets.connect(BACKEND_URL) as websocket:
        print("Connected to Backend.")
        
        try:
            while True:
                # print("\n[State]: Getting frame...")
                
                # Get RGB frame
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("Failed to grab frame")
                    await asyncio.sleep(0.1)
                    continue
                
                # Get LiDAR Scan
                scan = lidar.get_latest_scan()
                
                # Safety Check
                is_safe = check_safety(scan)
                
                # Create Visualization
                lidar_img = draw_lidar_view(scan, size=(480, 480))
                
                # Resize RGB to matches height (480) -> Keep aspect ratio 4:3 -> 640x480
                # Frame is already 640x480
                
                # Combine Side-by-Side
                # Final Size: 1120x480
                combined_img = np.hstack((frame, lidar_img))
                
                # Resize to reduce bandwidth? 
                # 1120 is wide. Let's resize output to width=1000
                scale_percent = 0.8
                width = int(combined_img.shape[1] * scale_percent)
                height = int(combined_img.shape[0] * scale_percent)
                dim = (width, height)
                resized_img = cv2.resize(combined_img, dim, interpolation=cv2.INTER_AREA)
                
                # Encode to JPEG
                _, buffer = cv2.imencode('.jpg', resized_img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                image_bytes = buffer.tobytes()

                print(f"[State]: Sending {len(image_bytes)/1024:.1f} KB Combined image...")
                await websocket.send(image_bytes)

                # Receive command
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    command_data = json.loads(response)
                    
                    cmd = command_data.get("command")
                    
                    # Intercept forward movements if unsafe
                    if not is_safe and cmd in ["MOVE_FORWARD"]:
                        print("[Safety] Blocking forward movement due to obstacle.")
                        command_data["command"] = "STOP"
                        
                    print(f"Received: {command_data}")
                    motor.execute_command(command_data)
                    
                except asyncio.TimeoutError:
                    print("Timeout waiting for backend response")
                    motor.stop()
                
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by server")
        except KeyboardInterrupt:
            print("Client stopped by user")
        finally:
            motor.stop()
            cap.release()
            lidar.stop()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        asyncio.run(run_agv_client())
    except KeyboardInterrupt:
        pass
