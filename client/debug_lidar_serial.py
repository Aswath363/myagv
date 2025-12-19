import serial
import time
import binascii
import os
import platform
import serial.tools.list_ports

def get_possible_ports():
    ports = []
    # List all
    com_ports = list(serial.tools.list_ports.comports())
    for p in com_ports:
        ports.append(p.device)
    
    # Add common hardcoded ones just in case
    if platform.system() == "Linux":
        if "/dev/ttyTHS1" not in ports and os.path.exists("/dev/ttyTHS1"):
            ports.append("/dev/ttyTHS1")
        if "/dev/ttyUSB0" not in ports and os.path.exists("/dev/ttyUSB0"):
            ports.append("/dev/ttyUSB0")
    
    return ports

def dump_serial(port, baudrate=115200, timeout=2):
    print(f"--- DUMPING {port} @ {baudrate} ---")
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        print(f"Opened {port}. Reading for 5 seconds...")
        
        start_time = time.time()
        received_data = b""
        
        while time.time() - start_time < 5:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                received_data += chunk
                
        ser.close()
        
        if len(received_data) == 0:
            print("No data received.")
        else:
            print(f"Received {len(received_data)} bytes.")
            print("First 50 bytes (Hex):")
            print(binascii.hexlify(received_data[:50]).decode('utf-8'))
            
            # Heuristic check for RPLidar (starts with A5)
            if received_data.startswith(b'\xa5'):
                 print("-> POSSIBLE RPLIDAR DETECTED (starts with 0xA5)")
            
            # Heuristic for YDLidar (S4, X4 often use 0xA5 0x5A or similar, but some use 0x54)
            
    except Exception as e:
        print(f"Error reading {port}: {e}")
    print("----------------------------------\n")

if __name__ == "__main__":
    ports = get_possible_ports()
    print(f"Found ports: {ports}")
    
    bauds = [115200, 128000, 230400, 256000]
    
    for p in ports:
        for b in bauds:
            dump_serial(p, b)
