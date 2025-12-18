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
You will receive a SIDE-BY-SIDE composite image with RGB on the LEFT and DEPTH on the RIGHT.

**Image Layout:**
┌─────────────────┬─────────────────┐
│   RGB IMAGE     │   DEPTH IMAGE   │
│   (What it      │   (How far      │
│    looks like)  │    things are)  │
└─────────────────┴─────────────────┘

**Depth Color Coding:**
- RED = Very close (danger zone, < 0.5m)
- ORANGE/YELLOW = Close (0.5-1.5m, caution)
- GREEN = Medium distance (1.5-3m, safe)
- BLUE = Far away (> 3m, clear path)

**Robot Dimensions:**
- Length: 36 cm
- Width: 26 cm

**Camera Specifications (Orbbec Astra Pro 2):**
- Horizontal FOV: 62.7°
- Vertical FOV: 49°
- Coverage at 1m: ~1.2m wide x 0.9m tall
- Coverage at 2m: ~2.4m wide x 1.8m tall

**Task:**
1. Analyze BOTH the RGB image (left) AND the depth image (right)
2. Use depth colors to judge actual distances to obstacles
3. Use RGB to identify what the obstacles are
4. Output a JSON navigation command

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
  "reasoning": "Depth shows clear path (mostly blue/green ahead). RGB shows open hallway.",
  "speak": "Path is clear, moving forward."
}

**Guidelines:**
- speed: 1-100 (use depth colors to decide - more red = slower)
- duration: seconds (use depth to estimate safe travel distance)
- If you see RED in the center of the depth image, STOP or turn
- If depth is mostly BLUE/GREEN ahead, you can move faster and longer
- Always mention what you see in BOTH RGB and depth in your reasoning
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
                            types.Part.from_text(text="Analyze this RGB+Depth composite image and provide navigation command.")
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
