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
                if count % 20 == 0:
                     print(f"Scan {count}: {len(data)} points")
                     # data is a dict: {angle: distance, ...}
                     # Print first few items
                     first_angles = list(data.keys())[:5]
                     for ang in first_angles:
                         print(f"  Angle: {ang}, Dist: {data[ang]}")
                
                count += 1
                if time.time() > t_end or count > 50:
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
