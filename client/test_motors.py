from pymycobot import MyAgv
import time

print("="*60)
print("  MYAGV MOTOR TESTER")
print("="*60)

try:
    agv = MyAgv("/dev/ttyS0", 115200)
    print("Combined connected successfully.")
except Exception as e:
    print(f"Connection failed: {e}")
    exit()

def test_move(name, func):
    print(f"\nTesting: {name}")
    print("  -> Running for 2 seconds...")
    func(10)  # Slow speed 10
    time.sleep(2)
    print("  -> Stopping.")
    agv.stop()
    time.sleep(1)

# Test 1: Go Ahead
test_move("GO AHEAD (Should move Forward)", agv.go_ahead)

# Test 2: Retreat
test_move("RETREAT (Should move Backward)", agv.retreat)

# Test 3: Pan Left
test_move("PAN LEFT (Should strafe Left)", agv.pan_left)

# Test 4: Pan Right
test_move("PAN RIGHT (Should strafe Right)", agv.pan_right)

# Test 5: CounterClockwise Rotation
test_move("COUNTERCLOCKWISE (Should Spin Left)", agv.counterclockwise_rotation)

# Test 6: Clockwise Rotation
test_move("CLOCKWISE (Should Spin Right)", agv.clockwise_rotation)

print("\n"+"="*60)
print("TEST COMPLETE")
print("="*60)
