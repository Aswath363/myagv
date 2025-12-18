"""
Find the correct camera index for Orbbec Astra Pro 2 RGB camera.
Works on both Windows (DirectShow) and Linux (V4L2).

On Linux, Orbbec cameras typically appear as:
  /dev/video0 - Depth
  /dev/video2 - IR  
  /dev/video4 - RGB (this is what you want)

On Windows with DirectShow:
  Index 0, 1 - Usually IR/Depth
  Index 2 - RGB (this is what you want)
"""
import cv2
import platform

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

print("="*60)
print("  ORBBEC ASTRA PRO 2 - CAMERA FINDER")
print(f"  Platform: {platform.system()}")
print("="*60)

# Select backend based on platform
if IS_WINDOWS:
    backend = cv2.CAP_DSHOW
    backend_name = "DSHOW"
elif IS_LINUX:
    backend = cv2.CAP_V4L2
    backend_name = "V4L2"
else:
    backend = cv2.CAP_ANY
    backend_name = "ANY"

print(f"\nUsing backend: {backend_name}")
print("Scanning camera indices 0-10...\n")

rgb_found = None

# Try indices 0-10
for i in range(11):
    cap = cv2.VideoCapture(i, backend)
    
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            # Check if color image
            is_color = False
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                b, g, r = cv2.split(frame)
                diff = (cv2.absdiff(r, g).mean() + cv2.absdiff(r, b).mean()) / 2
                is_color = diff > 5
            
            cam_type = "RGB/COLOR ✓" if is_color else "IR/DEPTH (grayscale)"
            print(f"Index {i}: WORKS - {frame.shape[1]}x{frame.shape[0]} - {cam_type}")
            
            # Save test image
            cv2.imwrite(f"test_cam_{i}.jpg", frame)
            
            if is_color and rgb_found is None:
                rgb_found = i
        else:
            print(f"Index {i}: Opens but can't read frame")
        cap.release()
    else:
        print(f"Index {i}: Cannot open")

print("\n" + "="*60)
if rgb_found is not None:
    print(f"✅ RGB CAMERA FOUND AT INDEX: {rgb_found}")
    print(f"\nUpdate your .env file:")
    print(f"  CAMERA_ID={rgb_found}")
else:
    print("⚠️  No RGB camera found. Check connections and drivers.")
    print("   On Linux, you may need to install libuvc or Orbbec SDK.")
print("="*60)
