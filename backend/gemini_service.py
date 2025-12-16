import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

# Load environment variables
load_dotenv()

from memory_service import MemoryService

class GeminiService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("Warning: GEMINI_API_KEY environment variable not set.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-robotics-er-1.5-preview"
        self.memory = MemoryService()
        self.long_term_context = ""
        self.current_goal = None

        self.system_instruction = """
You are the vision-based controller for a MyAGV robot.
You will receive image frames from the robot's camera.
Your goal is to navigate the robot safely and intelligently.

**Robot Dimensions:**
- Length: 36 cm
- Width: 26 cm
- Height: Unknown (assume standard low-profile AGV)

**Task:**
Analyze the image and output a JSON command.
Consider the robot's dimensions when navigating tight spaces.
If you see an obstacle or interesting object, comment on it in the "speak" field.

**Supported commands:**
- "MOVE_FORWARD": speed 10 (Fixed)
- "MOVE_BACKWARD": speed 10 (Fixed)
- "TURN_LEFT": speed 10 (Fixed)
- "TURN_RIGHT": speed 10 (Fixed)
- "STOP": speed 0

**Response Format:**
  "command": "MOVE_FORWARD",
  "speed": 10,
  "duration": 1.5,
  "reasoning": "Path is clear for about 1 meter.",
  "speak": "Moving forward for 1.5 seconds."
}
**Crucial:** 
- ALWAYS use speed 10 for safety.
- Always provide a 'duration' (in seconds) for MOVE/TURN commands.
- For turns, estimate time needed for the angle (e.g. 1.0s for ~90 degrees).
- For movement, estimate time based on free space (e.g. 1-3 seconds).
- Default to 1.0s if unsure.
"""

    async def summarize_memory(self, raw_history):
        """
        Uses Gemini to convert raw logs into a concise narrative summary.
        """
        try:
            prompt = f"""
            Here is a log of your recent actions and reasoning:
            {raw_history}

            Summarize this into a concise narrative of what you have done, what obstacles you encountered, and how you navigated them. 
            Focus on the "story" of the movement. Keep it under 100 words.
            """
            
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
            )
            
            if response.text:
                return response.text
            return raw_history # Fallback to raw if fail

        except Exception as e:
            print(f"Summarization error: {e}")
            return raw_history

    def update_memory_context(self, summary_text):
        if summary_text:
            print("[Brain]: Integrating consolidated memory...")
            # Append smoothly to the context
            self.long_term_context += f"\n\n[Memory of Previous Events]:\n{summary_text}"
            
    def update_current_goal(self, goal_text):
        if goal_text:
            self.current_goal = goal_text
            print(f"[Brain]: Received new goal: {goal_text}")

    async def analyze_frame(self, image_bytes):
        try:
            # Create a user content part with the image
            # Assumes image_bytes is a raw byte stream of an image (JPEG/PNG)
            
            # Dynamic System Instruction with Memory
            current_instruction = self.system_instruction
            if self.long_term_context:
                current_instruction += self.long_term_context
            
            # Inject Goal if present
            if self.current_goal:
                current_instruction += f"\n\n**CURRENT MISSION/GOAL FROM DATABASE**:\n{self.current_goal}\nPrioritize this goal above general wandering."

            # Using the generate_content_async method
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_bytes, mime_type="video/mp4"),
                            types.Part.from_text(text="Analyze this video clip and provide navigation command.")
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=current_instruction,
                    response_mime_type="application/json"
                )
            )

            # Parse the JSON response
            if response.text:
                data = json.loads(response.text)
                # Async log to memory (fire and forget)
                asyncio.create_task(self.memory.add_log(data))
                return data
            else:
                return {"command": "STOP", "speed": 0, "reasoning": "No response from model."}

        except Exception as e:
            print(f"Error calling Gemini: {e}")
            return {"command": "STOP", "speed": 0, "reasoning": f"Error: {str(e)}"}
