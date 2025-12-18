import cv2
import os
import time
from dotenv import load_dotenv

load_dotenv()

def test_video_stream():
    # Load config same as agv_client.py
    _cam_id = os.getenv("CAMERA_ID", "0")
    try:
        camera_source = int(_cam_id)
        source_desc = f"device index {camera_source}"
    except ValueError:
        # Heuristics
        if _cam_id.startswith("http") or _cam_id.startswith("rtsp") or _cam_id.startswith("tcp"):
             camera_source = _cam_id
        elif any(char.isdigit() for char in _cam_id) and "." in _cam_id:
            camera_source = f"http://{_cam_id}"
        else:
            camera_source = _cam_id
        source_desc = f"URL {camera_source}"

    print(f"Attempting to connect to: {source_desc}")
    
    cap = cv2.VideoCapture(camera_source)
    
    if not cap.isOpened():
        print("ERROR: Could not open video source.")
        return

    print("Success: Video source opened.")
    
    # Try to read a few frames
    for i in range(5):
        ret, frame = cap.read()
        if ret:
            print(f"Frame {i+1}: Successfully read ({frame.shape[1]}x{frame.shape[0]})")
            if i == 0:
                # Save first frame to verify content
                filename = "test_frame.jpg"
                cv2.imwrite(filename, frame)
                print(f"Saved first frame to {filename}")
        else:
            print(f"Frame {i+1}: Failed to read.")
            time.sleep(1)

    cap.release()
    print("Test complete.")

if __name__ == "__main__":
    test_video_stream()
