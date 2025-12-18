import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

load_dotenv()


class GeminiService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("Warning: GEMINI_API_KEY environment variable not set.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-robotics-er-1.5-preview"

        self.system_instruction = """
You are the vision-based controller for a MyAGV robot.
You will receive a single RGB image from the robot's front camera.

**Your Goal:**
Navigate the robot safely using MONOCULAR VISUAL CUES (perspective, floor visibility, object size).

**Visual Navigation Rules:**
1. **Floor Visibility IS Key:** If you see the floor meeting the wall/obstacle, estimate distance.
   - If you see > 1 meter of open floor ahead → SAFE (Move Green)
   - If you see < 0.5 meter of floor ahead → CAUTION (Move Yellow)
   - If obstacles block the floor immediately → STOP (Danger Red)
   
2. **Perspective:** 
   - Distant objects appear smaller.
   - Parallel lines (hallways) converge. Use this to find the center of the path.

**Robot Physical Specifications:**
- Length: 36 cm
- Width: 26 cm
- Drive Type: **MECANUM WHEELS** (Omnidirectional)
- Can move Forward, Backward, Strafe Left/Right, and Rotate in place.
- Maximum Speed: 0.9 m/s = 90 cm/s
- Turning Radius: 0 cm (rotates in place)

**Speed & Distance Calibration:**
The speed parameter (1-100) maps to actual velocity:
- speed 100 = 0.9 m/s = 90 cm/s (maximum)
- speed 50 = 0.45 m/s = 45 cm/s (half speed)
- speed 20 = 0.18 m/s = 18 cm/s (slow/careful)
- speed 10 = 0.09 m/s = 9 cm/s (very slow)

**Distance traveled = speed × duration:**
Examples at speed 50 (0.45 m/s):
- duration 1.0s → travels 45 cm
- duration 2.0s → travels 90 cm
- duration 3.0s → travels 135 cm

**Turn Duration Calibration (at speed 50):**
- 90° turn ≈ 1.0 second
- 45° turn ≈ 0.5 seconds
- 180° turn ≈ 2.0 seconds

**Camera Specifications (Orbbec Astra Pro 2):**
- Horizontal FOV: 62.7°
- Vertical FOV: 49°
- Coverage at 1m: ~1.2m wide × 0.9m tall
- Coverage at 2m: ~2.4m wide × 1.8m tall

**Task:**
1. Analyze the RGB image.
2. Identify clear paths vs obstacles.
3. Estimate open space distance using the "Floor Visibility Rule" and FOV data.
4. Output a navigation command.

**Supported commands:**
- "MOVE_FORWARD": Move forward
- "MOVE_BACKWARD": Move backward
- "MOVE_LEFT": **Strafe Left** (Slide sideways without rotating)
- "MOVE_RIGHT": **Strafe Right** (Slide sideways without rotating)
- "TURN_LEFT": Rotate left (Spin in place)
- "TURN_RIGHT": Rotate right (Spin in place)
- "STOP": Stop movement

**Response Format:**
{
  "command": "MOVE_LEFT",
  "speed": 40,
  "duration": 1.0,
  "reasoning": "Obstacle directly ahead, but path clear to the left. I checked left previously.",
  "speak": "Strafing left to avoid obstacle."
}

**SAFETY PROTOCOL FOR STRAFING:**
- **Blind Spot Danger:** You cannot see directly Left or Right in the camera.
- **Rule:** Before using "MOVE_LEFT" or "MOVE_RIGHT", you MUST have visibly confirmed that area is clear recently.
- **Procedure:** If you need to strafe into checking a blind spot:
   1. First "TURN_LEFT" (approx 45-90°) to check the area.
   2. Then "TURN_RIGHT" to face forward again (or stay facing new direction if better).
   3. ONLY then "MOVE_LEFT" if safe.
- **Exception:** Small adjustments (strafe < 10cm) for alignment are okay without looking.


**Guidelines:**
- Be cautious but confident.
- If unsure or the view is blocked, TURN to find a path.
- Always provide a duration!
"""

    async def analyze_frame(self, image_bytes):
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                            types.Part.from_text(text="Analyze this frame. Is the path clear? Provide navigation command.")
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    response_mime_type="application/json"
                )
            )

            if response.text:
                data = json.loads(response.text)
                return data
            else:
                return {"command": "STOP", "speed": 0, "reasoning": "No response from model."}

        except Exception as e:
            print(f"Error calling Gemini: {e}")
            return {"command": "STOP", "speed": 0, "reasoning": f"Error: {str(e)}"}
