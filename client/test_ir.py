import cv2
import os
import time
import numpy as np

print("="*60)
print("  ORBBEC ASTRA PRO 2 - IR CAMERA DIAGNOSTIC")
print("="*60)

def test_device(dev_path):
    print(f"\nTesting {dev_path}...")
    try:
        cap = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)
        
        if not cap.isOpened():
            print(f"  ❌ Failed to open {dev_path}")
            return
            
        # Try to set resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Read a few frames to stabilize
        for _ in range(10):
            cap.read()
            time.sleep(0.05)
            
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            h, w = frame.shape[:2]
            channels = frame.shape[2] if len(frame.shape) > 2 else 1
            
            # Convert to grayscale for analysis
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
                
            min_val, max_val, _, _ = cv2.minMaxLoc(gray)
            mean_val = np.mean(gray)
            std_dev = np.std(gray)
            
            print(f"  ✅ Capture SUCCESS!")
            print(f"     Resolution: {w}x{h}, Channels: {channels}")
            print(f"     Pixel Range: {min_val:.0f} - {max_val:.0f}")
            print(f"     Mean Brightness: {mean_val:.1f}")
            print(f"     Contrast (StdDev): {std_dev:.1f}")
            
            # Analyze image type
            if std_dev < 1.0:
                 print(f"     ⚠️  FLAT IMAGE (Solid Color) - Likely invalid or fake device")
            elif channels == 3 and std_dev > 10:
                 print(f"     📸 Likely RGB Camera")
            elif channels == 1 or (channels==3 and np.abs(np.mean(frame[:,:,0]) - np.mean(frame[:,:,2])) < 5):
                 print(f"     ⚪ Likely IR/Depth Camera (Grayscale)")
            
            filename = f"test_snap_{os.path.basename(dev_path)}.jpg"
            cv2.imwrite(filename, frame)
            print(f"     💾 Saved to {filename}")
            
        else:
             print(f"  ❌ Capture failed (empty frame)")
             
    except Exception as e:
        print(f"  ❌ Error: {e}")

# Scan devices /dev/video0 to /dev/video9
print("\nScanning devices...")
found_devices = [f"/dev/video{i}" for i in range(10) if os.path.exists(f"/dev/video{i}")]

if not found_devices:
    print("No /dev/video devices found!")
else:
    for dev in found_devices:
        test_device(dev)

print("\n"+"="*60)
print("CHECK THE SAVED IMAGES:")
print("1. Look for a grayscale image that looks like a night-vision camera.")
print("2. That is your IR_CAMERA_ID.")
print("3. Check its Pixel Range - should be wide (e.g., 0-255), not flat (90-90).")
print("="*60)
