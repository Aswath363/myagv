import time
import PyLidar3
import platform
import os
import sys

def get_lidar_port():
    system = platform.system()
    if system == "Windows":
        return "COM3"
    elif system == "Linux":
        if os.path.exists("/dev/ttyTHS1"):
            return "/dev/ttyTHS1" # Probable Jetson Nano UART
        return "/dev/ttyUSB0"
    return "/dev/ttyUSB0"

def run_test():
    port = os.getenv("LIDAR_PORT", get_lidar_port())
    print(f"Connecting to YDLidar/X4 on {port}...")
    
    # Initialize PyLidar3
    # Note: PyLidar3 connects immediately upon init
    try:
        # PyLidar3(port) uses default baudrate. 
        # Check documentation: usually 115200 or 128000 for X4/G4
        # We observed 115200 gave readable headers in debug dump.
        lidar = PyLidar3.YdLidarX4(port) 
        
        if(lidar.Connect()):
            print(f"Connected to LiDAR on {port}")
            print("Turning on motor/laser...")
            # gen = lidar.StartScanning() # This returns a generator
             
            t_end = time.time() + 10
            count = 0
            
            # StartScanning returns a generator yielding dicts
            for data in lidar.StartScanning():
                if count % 10 == 0:
                     # Filter out zero/invalid distances
                     valid_points = {k: v for k, v in data.items() if v > 0}
                     
                     print(f"Scan {count}: {len(data)} total points, {len(valid_points)} valid points")
                     
                     if valid_points:
                         min_dist = min(valid_points.values())
                         max_dist = max(valid_points.values())
                         print(f"  Range: {min_dist:.1f}mm - {max_dist:.1f}mm")
                         
                         # Print 3 random samples from valid points
                         sample_angles = list(valid_points.keys())[:3]
                         for ang in sample_angles:
                             print(f"  Angle: {ang}°, Dist: {valid_points[ang]}mm")
                     else:
                         print("  No valid points detected yet (spinning up?)")
                
                count += 1
                if count > 100: # Run for about 100 scans to be sure
                    break
                    
            print("Stopping...")
            lidar.StopScanning()
            lidar.Disconnect()
        else:
            print("Failed to connect (lidar.Connect() returned False)")

    except Exception as e:
        print(f"Error: {e}")
        print("Note: use sudo chmod 666 /dev/ttyTHS1")

if __name__ == "__main__":
    run_test()
