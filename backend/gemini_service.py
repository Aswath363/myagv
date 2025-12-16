import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

# Load environment variables
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
You will receive image frames from the robot's camera.
Your goal is to navigate the robot safely and intelligently.

Analyze the image and output a JSON command.
Supported commands:
- "MOVE_FORWARD": speed 0-100
- "MOVE_BACKWARD": speed 0-100
- "TURN_LEFT": speed 0-100
- "TURN_RIGHT": speed 0-100
- "STOP": speed 0

Response Format:
{
  "command": "MOVE_FORWARD",
  "speed": 50,
  "reasoning": "Path is clear ahead."
}
"""

    async def analyze_frame(self, image_bytes):
        try:
            # Create a user content part with the image
            # Assumes image_bytes is a raw byte stream of an image (JPEG/PNG)
            
            # Using the generate_content_async method
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                            types.Part.from_text(text="Analyze this frame and provide navigation command.")
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    response_mime_type="application/json"
                )
            )

            # Parse the JSON response
            if response.text:
                return json.loads(response.text)
            else:
                return {"command": "STOP", "speed": 0, "reasoning": "No response from model."}

        except Exception as e:
            print(f"Error calling Gemini: {e}")
            return {"command": "STOP", "speed": 0, "reasoning": f"Error: {str(e)}"}
