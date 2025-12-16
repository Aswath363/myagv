import time
try:
    from pymycobot import MyAgv
    MOCK_MODE = False
except ImportError:
    print("pymycobot not found (this is normal on PC). MOCK MODE enabled.")
    MOCK_MODE = True

class MotorController:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        self.mock = MOCK_MODE
        if not self.mock:
            try:
                self.agv = MyAgv(port, baudrate)
                print("MyAGV connected successfully.")
            except Exception as e:
                print(f"Failed to connect to MyAGV hardware: {e}")
                print("Falling back to MOCK MODE.")
                self.mock = True
        else:
            print("MotorController running in MOCK MODE.")

    def execute_command(self, cmd_data):
        """
        Executes a command dictionary.
        Format: {"command": "MOVE_FORWARD", "speed": 50}
        """
        command = cmd_data.get("command")
        speed = int(cmd_data.get("speed", 0))
        
        print(f"[AGV] Executing: {command} speed={speed}")

        if self.mock:
            return

        try:
            if command == "MOVE_FORWARD":
                self.agv.go_ahead(speed)
            elif command == "MOVE_BACKWARD":
                self.agv.retreat(speed)
            elif command == "TURN_LEFT":
                self.agv.pan_left(speed)
            elif command == "TURN_RIGHT":
                self.agv.pan_right(speed)
            elif command == "STOP":
                self.agv.stop()
            else:
                print(f"[AGV] Unknown command: {command}")
        except Exception as e:
            print(f"[AGV] Motor error: {e}")

    def stop(self):
        print("[AGV] Emergency Stop.")
        if not self.mock:
            try:
                self.agv.stop()
            except:
                pass
