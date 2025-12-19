import time
import os
import platform
import math
from lidar_driver import LidarDriver

# Configuration
IS_LINUX = platform.system() == "Linux"
LIDAR_PORT = os.getenv("LIDAR_PORT", "/dev/ttyTHS1" if IS_LINUX else "COM3")

def get_front_distance(scan, sector_angle=20):
    """
    Calculates the minimum distance in the front sector.
    sector_angle: Total angle to check (e.g. 20 means -10 to +10 degrees)
    Returns: Min distance in mm, or None if no valid points.
    """
    if not scan:
        return None
        
    front_dists = []
    
    # YDLidar X4: 0 is Front, Clockwise.
    # We want angles [0 to sector/2] AND [360 - sector/2 to 360]
    half_sector = sector_angle / 2.0
    
    for angle, dist in scan.items():
        if dist <= 10: continue # Ignore noise
        
        # Check if angle is in front sector
        if angle <= half_sector or angle >= (360 - half_sector):
             front_dists.append(dist)
             
    if not front_dists:
        return None
        
    return min(front_dists)

def main():
    print(f"Initializing LiDAR on {LIDAR_PORT}...")
    lidar = LidarDriver(LIDAR_PORT)
    lidar.start()
    
    print("\n[Front Distance Monitor]")
    print("Press Ctrl+C to stop...\n")
    
    try:
        while True:
            scan = lidar.get_latest_scan()
            
            # Check 30 degree cone (+/- 15 deg)
            dist_mm = get_front_distance(scan, sector_angle=30)
            
            # Clear line (ANSI escape) to update in place
            print("\033[K", end="") 
            
            if dist_mm:
                dist_cm = dist_mm / 10.0
                
                # Visual Bar
                # [=====      ] 50cm
                max_bar = 200 # 2m max for bar
                bar_len = 20
                filled = int(min(dist_cm, max_bar) / max_bar * bar_len)
                bar = "#" * filled + "-" * (bar_len - filled)
                
                status = "SAFE"
                if dist_cm < 20: status = "CRITICAL"
                elif dist_cm < 50: status = "WARNING"
                
                print(f"\rFront Object: {dist_cm:.1f} cm  [{bar}]  {status}", end="", flush=True)
            else:
                print("\rFront Object: > 800 cm     [--------------------]  CLEAR", end="", flush=True)
                
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        lidar.stop()

if __name__ == "__main__":
    main()
