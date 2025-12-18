"""
Find the correct camera index for Orbbec Astra Pro 2 RGB camera.
Tests all available indices with DirectShow backend.
"""
import cv2

print("="*60)
print("  ORBBEC ASTRA PRO 2 - CAMERA FINDER")
print("="*60)

# Try indices 0-10 with different backends
for i in range(10):
    # Try with DirectShow backend (Windows)
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            # Check if color image
            is_color = False
            if len(frame.shape) == 3:
                b, g, r = cv2.split(frame)
                diff = (cv2.absdiff(r, g).mean() + cv2.absdiff(r, b).mean()) / 2
                is_color = diff > 5
            
            cam_type = "RGB/COLOR" if is_color else "IR/DEPTH (grayscale)"
            print(f"Index {i} (DSHOW): WORKS - {frame.shape} - {cam_type}")
            cv2.imwrite(f"test_cam_{i}_dshow.jpg", frame)
        else:
            print(f"Index {i} (DSHOW): Opens but can't read frame")
        cap.release()
    else:
        print(f"Index {i} (DSHOW): Cannot open")

print("\n" + "="*60)
print("Check the saved test_cam_*.jpg files to identify RGB camera")
print("="*60)
