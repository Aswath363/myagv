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
You are the advanced control system for a MyAGV robot with DUAL SENSOR INPUT.
You receive:
1. **RGB Camera Image:** Front-facing visual view.
2. **LiDAR Sector Data (JSON Text):** Precise distance measurements in 4 directions.

**Your Goal:**
Navigate safely and intelligently using the LIDAR DATA as the primary source of truth for distances, and RGB for object identification only.

**LiDAR Data Format:**
You will receive text like:
```
LIDAR READINGS:
- FRONT (345°-15°): 450mm (closest at 2°)
- RIGHT (75°-105°): 1200mm (closest at 88°)
- BACK (165°-195°): CLEAR (>2000mm)
- LEFT (255°-285°): 800mm (closest at 270°)
```
- Distance in **millimeters (mm)**. 
- "CLEAR" means no obstacle within 2 meters.
- Use these values DIRECTLY for navigation decisions.

**Navigation Logic (LiDAR DRIVEN):**
1. **FRONT < 200mm:** STOP or TURN. Too close!
2. **FRONT 200-500mm:** Slow down (speed 10-20), consider STRAFE if sides are clear.
3. **FRONT 500-1000mm:** Caution, proceed at speed 30-40.
4. **FRONT > 1000mm:** Safe to proceed at speed 50+.
5. **Always check the SIDE you want to STRAFE towards.** If that side < 300mm, do not strafe there.

**Robot Physical Specifications:**
- Size: 36 cm x 26 cm
- Drive Type: MECANUM WHEELS (Omnidirectional)
- Max Speed: 0.9 m/s (Speed 100)

**Speed & Distance Calibration:**
- speed 50 = 0.45 m/s = 45 cm/s -> duration 1.0s = 45cm travel.
- speed 20 = 0.18 m/s -> Precision maneuvering.
- 90° turn at speed 50 ≈ 1.0 second.

**Response Format (JSON):**
{
  "command": "MOVE_FORWARD",
  "speed": 40,
  "duration": 1.0,
  "reasoning": "FRONT is 850mm (clear). LEFT is 400mm, RIGHT is 1200mm. Safe to proceed.",
  "speak": "Path clear, moving forward."
}

**SAFETY PROTOCOLS:**
1. **NEVER output STOP unless trapped on all 4 sides.** Always try to STRAFE or TURN around obstacles.
2. **Trust LiDAR over RGB.** If camera shows clear but LiDAR < 300mm, DO NOT move that direction.
3. **Micro-movements:** If FRONT < 400mm, use short durations (0.2-0.5s).

**Supported Commands:**
- MOVE_FORWARD, MOVE_BACKWARD
- MOVE_LEFT (strafe), MOVE_RIGHT (strafe)
- TURN_LEFT, TURN_RIGHT (rotate in place)
- STOP
"""

    def _format_lidar_text(self, lidar_data):
        """Formats LiDAR sector data into readable text for the prompt."""
        if not lidar_data:
            return "LIDAR DATA: Unavailable."
        
        # Convert string keys to int (from JSON)
        lidar_data = {int(k): v for k, v in lidar_data.items()}
        
        def get_sector_min(angles_list):
            """Get minimum distance and angle for a list of angles to check."""
            min_dist = float('inf')
            min_ang = None
            for ang in angles_list:
                if ang in lidar_data:
                    d = lidar_data[ang]
                    if d < min_dist:
                        min_dist = d
                        min_ang = ang
            if min_dist == float('inf'):
                return None, None
            return min_dist, min_ang
        
        # Define sectors (YDLidar X4: 0=Front, Clockwise)
        # FRONT: 345-360 and 0-15
        front_angles = list(range(345, 360)) + list(range(0, 16))
        right_angles = list(range(75, 106))
        back_angles = list(range(165, 196))
        left_angles = list(range(255, 286))
        
        f_dist, f_ang = get_sector_min(front_angles)
        r_dist, r_ang = get_sector_min(right_angles)
        b_dist, b_ang = get_sector_min(back_angles)
        l_dist, l_ang = get_sector_min(left_angles)
        
        def fmt(d, a):
            if d is None: return "CLEAR (>2000mm)"
            if d > 2000: return "CLEAR (>2000mm)"
            return f"{int(d)}mm (closest at {a}°)"
        
        return f"""LIDAR READINGS:
- FRONT (345°-15°): {fmt(f_dist, f_ang)}
- RIGHT (75°-105°): {fmt(r_dist, r_ang)}
- BACK (165°-195°): {fmt(b_dist, b_ang)}
- LEFT (255°-285°): {fmt(l_dist, l_ang)}"""

    async def analyze_frame(self, image_bytes, lidar_data=None):
        try:
            # Format LiDAR data as text
            lidar_text = self._format_lidar_text(lidar_data)
            
            prompt_text = f"""Analyze this camera frame and the LiDAR data below. Provide a navigation command.

{lidar_text}

Based on the image and LiDAR readings, what should the robot do next?"""

            parts = []
            if image_bytes:
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            parts.append(types.Part.from_text(text=prompt_text))

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=parts
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

