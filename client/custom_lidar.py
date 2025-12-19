import serial
import time
import struct
import math

class CustomYDLidarDriver:
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.scanning = False

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Opened {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            print(f"Failed to open serial: {e}")
            return False

    def start_scan(self):
        if not self.ser: return
        # Create start scan command: A5 60
        # Some models use A5 60, others A5 65...
        # Let's try standard X4 command
        cmd = b'\xA5\x60' 
        self.ser.write(cmd)
        print("Sent Start Scan command")
        time.sleep(0.5)
        self.ser.reset_input_buffer()
        self.scanning = True

    def stop_scan(self):
        if not self.ser: return
        cmd = b'\xA5\x65'
        self.ser.write(cmd)
        time.sleep(0.1)
        self.scanning = False

    def disconnect(self):
        if self.ser:
            self.stop_scan()
            self.ser.close()

    def read_scan(self):
        if not self.ser or not self.scanning: return None
        
        # We need to find the header AA 55
        # Read byte by byte until we find it
        
        # Look for AA 55
        # Since we are reading potentially misaligned stream
        header = b''
        while len(header) < 2:
            b = self.ser.read(1)
            if not b: return None # Timeout
            
            if len(header) == 0:
                if b == b'\xaa':
                    header += b
            elif len(header) == 1:
                if b == b'\x55':
                    header += b
                else:
                     # Reset if not 55
                     if b == b'\xaa':
                         # We found another AA, maybe that's the start
                         header = b'\xaa'
                     else:
                         header = b''
        
        # Found Header AA 55
        # Read CT (1) and LS (1)
        info = self.ser.read(2)
        if len(info) < 2: return None
        
        ct = info[0]
        ls = info[1] # Sample count
        
        # Read FSA (2), LSA (2), CS (2)
        headers = self.ser.read(6)
        if len(headers) < 6: return None
        
        fsa = struct.unpack('<H', headers[0:2])[0]
        lsa = struct.unpack('<H', headers[2:4])[0]
        cs  = struct.unpack('<H', headers[4:6])[0]
        
        # Read Data: LS * 2 bytes
        data_len = ls * 2
        raw_data = self.ser.read(data_len)
        if len(raw_data) < data_len: return None
        
        # Calculate Angles
        # FSA and LSA are shifted by 1 bit, then / 64
        angle_fsa = (fsa >> 1) / 64.0
        angle_lsa = (lsa >> 1) / 64.0
        
        diff_angle = angle_lsa - angle_fsa
        if diff_angle < 0:
            diff_angle += 360
            
        points = []
        
        for i in range(ls):
            # Each point is 2 bytes
            idx = i * 2
            # Dist is 2 bytes, little endian
            # Bit 0 and 1 might be quality or flags?
            # Standard X4: 
            #   <distance_low> <distance_high>
            #   Distance = value / 4.0
            
            val = struct.unpack('<H', raw_data[idx:idx+2])[0]
            distance = val / 4.0
            
            # Angle interpolation
            # ang = (diff_angle / (ls - 1)) * i + angle_fsa + correction
            # ignoring correction for simplicity first
            if ls > 1:
                angle = angle_fsa + (diff_angle / (ls - 1)) * i
            else:
                angle = angle_fsa
                
            if distance > 0:
                points.append((angle, distance))
                
        return points

def run_test():
    import os
    port = os.getenv("LIDAR_PORT", "/dev/ttyTHS1")
    if os.path.exists("/dev/ttyUSB0"): port = "/dev/ttyUSB0"
    
    driver = CustomYDLidarDriver(port)
    if driver.connect():
        driver.start_scan()
        
        try:
            total_points = 0
            for i in range(200): # Read 200 packets
                pts = driver.read_scan()
                if pts:
                    total_points += len(pts)
                    # Print one in every 20 packets info
                    if i % 20 == 0:
                        print(f"Packet {i}: {len(pts)} points. Total so far: {total_points}")
                        if len(pts) > 0:
                            print(f"  Sample: Ang={pts[0][0]:.1f}, Dist={pts[0][1]:.1f}")
                            print(f"          Ang={pts[-1][0]:.1f}, Dist={pts[-1][1]:.1f}")
                else:
                    # print(".", end="", flush=True)
                    pass
        except KeyboardInterrupt:
            pass
        finally:
            driver.disconnect()

if __name__ == "__main__":
    run_test()
