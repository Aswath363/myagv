import time
try:
    from pymycobot import MyAgv
    MOCK_MODE = False
except ImportError:
    print("pymycobot not found, running in MOCK MODE")
    MOCK_MODE = True

class MotorController:
    def __init__(self, port="/dev/ttyS0", baudrate=115200):
        self.mock = MOCK_MODE
        if not self.mock:
            try:
                self.agv = MyAgv(port, baudrate)
                print("MyAGV connected.")
            except Exception as e:
                print(f"Failed to connect to MyAGV: {e}")
                print("Falling back to MOCK MODE")
                self.mock = True
        else:
            print("MotorController initialized in MOCK MODE")

    def execute_command(self, cmd_data):
        """
        Executes a command dictionary.
        Format: {"command": "MOVE_FORWARD", "speed": 50}
        """
        command = cmd_data.get("command")
        speed = int(cmd_data.get("speed", 0))
        
        print(f"Executing: {command} at speed {speed}")

        if self.mock:
            return

        if command == "MOVE_FORWARD":
            self.agv.go_ahead(speed)
        elif command == "MOVE_BACKWARD":
            self.agv.retreat(speed)
        elif command == "MOVE_LEFT":
            # Strafe Left
            self.agv.pan_left(speed)
        elif command == "MOVE_RIGHT":
            # Strafe Right
            self.agv.pan_right(speed)
        elif command == "TURN_LEFT":
            # Rotate in place
            self.agv.counterclockwise_rotation(speed)
        elif command == "TURN_RIGHT":
            # Rotate in place
            self.agv.clockwise_rotation(speed)
        elif command == "STOP":
            self.agv.stop()
        else:
            print(f"Unknown command: {command}")
            return

        # usage of duration
        duration = float(cmd_data.get("duration", 0))
        if duration > 0 and command != "STOP":
            time.sleep(duration)
            self.stop()

    def stop(self):
        print("Stopping motors...")
        if not self.mock:
            self.agv.stop()
