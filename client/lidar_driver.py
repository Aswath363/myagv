import serial
import time
import struct
import threading
import math

class LidarDriver:
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.scanning = False
        self.latest_scan = {} # {angle: distance}
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"[LiDAR] Opened {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            print(f"[LiDAR] Failed to open serial: {e}")
            return False

    def start(self):
        if not self.ser:
            if not self.connect(): return
            
        self.running = True
        self._send_start_cmd()
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        print("[LiDAR] Driver started in background thread.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self._send_stop_cmd()
        if self.ser:
            self.ser.close()
            self.ser = None
        print("[LiDAR] Driver stopped.")

    def get_latest_scan(self):
        with self.lock:
            return self.latest_scan.copy()

    def _send_start_cmd(self):
        if not self.ser: return
        try:
            cmd = b'\xA5\x60' 
            self.ser.write(cmd)
            time.sleep(0.1)
            self.ser.reset_input_buffer()
            self.scanning = True
        except Exception as e:
            print(f"[LiDAR] Error sending start: {e}")

    def _send_stop_cmd(self):
        if not self.ser: return
        try:
            cmd = b'\xA5\x65'
            self.ser.write(cmd)
            time.sleep(0.1)
            self.scanning = False
        except:
            pass

    def _update_loop(self):
        temp_points = {}
        last_packet_time = time.time()
        
        while self.running and self.ser:
            try:
                points = self._parse_next_packet()
                if points:
                    last_packet_time = time.time()
                    with self.lock:
                        for ang, dist in points:
                            # Simple filtering
                            if dist > 0:
                                self.latest_scan[int(ang)] = dist
                
                # Reconnect if no data for 2 seconds
                if time.time() - last_packet_time > 2.0:
                    print("[LiDAR] No data for 2s, resetting...")
                    self._send_stop_cmd()
                    time.sleep(0.5)
                    self.ser.reset_input_buffer()
                    self._send_start_cmd()
                    last_packet_time = time.time()
                    
            except Exception as e:
                # print(f"[LiDAR] Parse error: {e}")
                time.sleep(0.1)

    def _parse_next_packet(self):
        if not self.ser: return None
        
        # Look for Header AA 55
        header = b''
        while len(header) < 2:
            b = self.ser.read(1)
            if not b: return None 
            if len(header) == 0 and b == b'\xaa':
                header += b
            elif len(header) == 1:
                if b == b'\x55':
                    header += b
                elif b == b'\xaa':
                    header = b'\xaa'
                else:
                    header = b''

        # Read CT (1) and LS (1)
        info = self.ser.read(2)
        if len(info) < 2: return None
        ls = info[1] # Sample count
        
        # Read FSA (2), LSA (2), CS (2)
        headers = self.ser.read(6)
        if len(headers) < 6: return None
        
        fsa = struct.unpack('<H', headers[0:2])[0]
        lsa = struct.unpack('<H', headers[2:4])[0]
        
        # Read Data
        data_len = ls * 2
        raw_data = self.ser.read(data_len)
        if len(raw_data) < data_len: return None
        
        angle_fsa = (fsa >> 1) / 64.0
        angle_lsa = (lsa >> 1) / 64.0
        
        diff = angle_lsa - angle_fsa
        if diff < 0: diff += 360
        
        packet_points = []
        for i in range(ls):
            dist = struct.unpack('<H', raw_data[i*2:(i+1)*2])[0] / 4.0
            if ls > 1:
                angle = angle_fsa + (diff / (ls - 1)) * i
            else:
                angle = angle_fsa
            
            if angle >= 360: angle -= 360
            if dist > 10: # Min valid range
                packet_points.append((angle, dist))
                
        return packet_points

if __name__ == "__main__":
    # Test stub
    import os
    port = os.getenv("LIDAR_PORT", "/dev/ttyTHS1")
    if os.path.exists("/dev/ttyUSB0"): port = "/dev/ttyUSB0"
    
    drv = LidarDriver(port)
    drv.start()
    
    try:
        while True:
            time.sleep(1)
            scan = drv.get_latest_scan()
            if scan:
                 print(f"Scan contains {len(scan)} points")
                 angles = sorted(list(scan.keys()))
                 if angles:
                     print(f"  0 deg: {scan.get(0, 'N/A')}")
                     print(f"  90 deg: {scan.get(90, 'N/A')}")
            else:
                print("Waiting for data...")
    except KeyboardInterrupt:
        drv.stop()
