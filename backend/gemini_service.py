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
You will receive a SIDE-BY-SIDE composite image with RGB on the LEFT and IR (infrared) on the RIGHT.

**Image Layout:**
┌─────────────────┬─────────────────┐
│   RGB IMAGE     │    IR IMAGE     │
│   (What it      │   (Proximity    │
│    looks like)  │    sensing)     │
└─────────────────┴─────────────────┘

**IR Color Coding (colorized from grayscale):**
- RED = Very close (< 0.5m, danger zone)
- ORANGE/YELLOW = Medium distance (0.5-1.5m, caution)
- GREEN = Safe distance (1.5-3m)
- BLUE = Far away (> 3m, clear path)

**Robot Physical Specifications:**
- Length: 36 cm
- Width: 26 cm
- Maximum Speed: 0.9 m/s (90 cm/s)
- Turning Radius: ~18 cm (can rotate in place)

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
1. Analyze BOTH the RGB image (left) AND the IR image (right)
2. Use IR colors to judge actual distances to obstacles
3. Use RGB to identify what the obstacles are
4. Calculate appropriate speed and duration based on visible free space
5. Output a JSON navigation command

**Supported commands:**
- "MOVE_FORWARD": Move forward
- "MOVE_BACKWARD": Move backward  
- "TURN_LEFT": Rotate left
- "TURN_RIGHT": Rotate right
- "STOP": Stop movement

**Response Format:**
{
  "command": "MOVE_FORWARD",
  "speed": 50,
  "duration": 1.5,
  "reasoning": "IR shows green/blue ahead (~2m clear). RGB shows open hallway. Moving 67cm at half speed.",
  "speak": "Path is clear, moving forward."
}

**Safety Guidelines:**
- If RED in center of IR → STOP or turn immediately
- If YELLOW/ORANGE ahead → slow down (speed 20-30), short duration
- If GREEN ahead → moderate speed (40-60), medium duration
- If BLUE ahead → can go faster (60-80), longer duration
- Always leave safety margin - stop 30cm before obstacles
- For tight spaces (< 30cm clearance on sides), slow to speed 20
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
                            types.Part.from_text(text="Analyze this RGB+IR composite image and provide navigation command.")
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
