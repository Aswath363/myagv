import asyncio
import websockets
import cv2
import json
import time
import os
import threading
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


class BufferlessVideoCapture:
    """
    A wrapper around cv2.VideoCapture that continuously reads frames in a
    background thread, ensuring only the latest frame is ever returned.
    This solves the stale buffer problem when processing is slow.
    """
    def __init__(self, name):
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
