import os
import sys
import time
import platform
import serial.tools.list_ports
from rplidar import RPLidar

def get_lidar_port():
    """
    Attempt to find the LiDAR port based on the operating system.
    Returns a default port string.
    """
    # Debug: List all available ports
    ports = list(serial.tools.list_ports.comports())
    print("Available Serial Ports:")
    detected_port = None
    for p in ports:
        print(f" - {p.device}: {p.description}")
        # Try to guess common lidar ports
        if "CP210" in p.description or "USB" in p.description:
            if platform.system() == "Linux" and "ttyUSB" in p.device:
                detected_port = p.device

    system = platform.system()
    if system == "Windows":
        return "COM3"  # Common default, user may need to change
    elif system == "Linux":
        if detected_port:
            print(f"Auto-detected likely LiDAR port: {detected_port}")
            return detected_port
            
        # Fallbacks
        if os.path.exists("/dev/ttyUSB0"):
            return "/dev/ttyUSB0"
        elif os.path.exists("/dev/ttyTHS1"):
            print("Found /dev/ttyTHS1 (Jetson Nano UART) - using this.")
            return "/dev/ttyTHS1"
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
        # Add timeout to constructor
        lidar = RPLidar(port, timeout=3)
        
        # Try to get info with a retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
                info = lidar.get_info()
                print("\nLiDAR Info:")
                for k, v in info.items():
                    print(f"{k}: {v}")
                
                health = lidar.get_health()
                print(f"\nLiDAR Health: {health}")
                break
            except Exception as e:
                print(f"Connection attempt {attempt+1} failed: {e}")
                
                # Robust buffer clearing
                if hasattr(lidar, 'clean_input'):
                    lidar.clean_input()
                elif hasattr(lidar, 'clear_input'):
                    lidar.clear_input()
                elif hasattr(lidar, '_serial'):
                    lidar._serial.reset_input_buffer()
                else:
                    print("Could not clear input buffer (method not found)")
                    lidar.stop()
                    
                time.sleep(1)
        
        print("\nStarting scan (press Ctrl+C to stop)...")
        
        count = 0
        try:
            for i, scan in enumerate(lidar.iter_scans()):
                print(f"\nScan {i}: got {len(scan)} points")
                for point in scan[:5]:
                    quality, angle, distance = point
                    print(f"  Angle: {angle:.1f}°, Dist: {distance:.1f}mm, Quality: {quality}")
                
                count += 1
                if count >= 10:
                    break
        except Exception as scan_error:
            print(f"Scan error: {scan_error}")
            try:
                lidar.stop()
                if hasattr(lidar, 'clean_input'):
                    lidar.clean_input()
                elif hasattr(lidar, 'clear_input'):
                    lidar.clear_input()
            except:
                pass
                
    except Exception as e:
        print(f"\nCritical Error: {e}")
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
