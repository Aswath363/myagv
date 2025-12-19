import time
import os
import platform
import math
from lidar_driver import LidarDriver

# Configuration
IS_LINUX = platform.system() == "Linux"
LIDAR_PORT = os.getenv("LIDAR_PORT", "/dev/ttyTHS1" if IS_LINUX else "COM3")

def get_sector_info(scan, center_angle, width=20):
    """Returns (min_dist, angle_of_min_dist) for a sector"""
    if not scan: return None, None
    
    half = width / 2.0
    min_d = float('inf')
    min_a = None
    
    start_a = (center_angle - half) % 360
    end_a = (center_angle + half) % 360
    
    for angle, dist in scan.items():
        if dist <= 10: continue
        
        # Check angle inclusion handling wrap-around
        if start_a < end_a:
            in_sector = start_a <= angle <= end_a
        else:
             in_sector = angle >= start_a or angle <= end_a
             
        if in_sector:
            if dist < min_d:
                min_d = dist
                min_a = angle
                
    if min_d == float('inf'): return None, None
    return min_d, min_a

def main():
    print(f"Initializing LiDAR on {LIDAR_PORT}...")
    lidar = LidarDriver(LIDAR_PORT)
    lidar.start()
    
    print("\n[Detailed Lidar Monitor]")
    
    try:
        while True:
            scan = lidar.get_latest_scan()
            
            # Check 4 directions
            f_dist, f_ang = get_sector_info(scan, 0, 30)
            l_dist, l_ang = get_sector_info(scan, 270, 30) # 270 is Left in X4 (Clockwise)? No, 0=Front, 90=Right, 180=Back, 270=Left
            r_dist, r_ang = get_sector_info(scan, 90, 30)
            b_dist, b_ang = get_sector_info(scan, 180, 30)
            
            print("\033[2J\033[H", end="") # Clear Screen
            print("--- LiDAR Sector Analysis ---")
            
            def fmt(d, a): 
                return f"{d/10.0:.1f}cm @ {a}°" if d else "CLEAR"
            
            print(f"FRONT (0°):   {fmt(f_dist, f_ang)}")
            print(f"RIGHT (90°):  {fmt(r_dist, r_ang)}")
            print(f"BACK (180°):  {fmt(b_dist, b_ang)}")
            print(f"LEFT (270°):  {fmt(l_dist, l_ang)}")
            print("-" * 30)
            
            if f_dist and f_dist < 250:
                 print("\n!! POSSIBLE SELF-OCCLUSION OR OBSTACLE !!")
                 print(f"Closest Front Point: {f_dist} mm at Angle {f_ang}")
                 
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        lidar.stop()

if __name__ == "__main__":
    main()
