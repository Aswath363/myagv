import os
import sys
import time
import platform
from rplidar import RPLidar

def get_lidar_port():
    """
    Attempt to find the LiDAR port based on the operating system.
    Returns a default port string.
    """
    system = platform.system()
    if system == "Windows":
        return "COM3"  # Common default, user may need to change
    elif system == "Linux":
        # On Jetson Nano/Raspberry Pi, it's often ttyUSB0 or ttyUSB1
        if os.path.exists("/dev/ttyUSB0"):
            return "/dev/ttyUSB0"
        elif os.path.exists("/dev/ttyACM0"):
            return "/dev/ttyACM0"
        return "/dev/ttyUSB0"
    else:
        return "/dev/ttyUSB0"

def run_lidar_test():
    port = os.getenv("LIDAR_PORT", get_lidar_port())
    print(f"Attempting to connect to LiDAR on port: {port}")
    
    lidar = None
    try:
        lidar = RPLidar(port)
        
        info = lidar.get_info()
        print("\nLiDAR Info:")
        for k, v in info.items():
            print(f"{k}: {v}")
            
        health = lidar.get_health()
        print(f"\nLiDAR Health: {health}")
        
        print("\nStarting scan (press Ctrl+C to stop)...")
        
        # scan returns items as a generator: (new_scan, quality, angle, distance)
        # new_scan: bool, True if this is the start of a new 360 scan
        # quality: int, reflection quality
        # angle: float, 0-360 degrees
        # distance: float, distance in millimeters
        
        count = 0
        for i, scan in enumerate(lidar.iter_scans()):
            print(f"\nScan {i}: got {len(scan)} points")
            # Print first 5 points of the scan
            for point in scan[:5]:
                quality, angle, distance = point
                print(f"  Angle: {angle:.1f}°, Dist: {distance:.1f}mm, Quality: {quality}")
            
            count += 1
            if count >= 10:  # Stop after 10 scans for this test
                break
                
    except Exception as e:
        print(f"\nError: {e}")
        print("Note: If you are on Linux/Jetson, make sure you have permissions:")
        print(f"sudo chmod 666 {port}")
    except KeyboardInterrupt:
        print("\nStopping...")
        
    finally:
        if lidar:
            print("Disconnecting LiDAR...")
            lidar.stop()
            lidar.stop_motor()
            lidar.disconnect()

if __name__ == "__main__":
    run_lidar_test()
