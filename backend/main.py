from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import json
import time
from gemini_service import GeminiService

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gemini_service = GeminiService()

@app.get("/")
async def root():
    return {"message": "MyAGV Vision Backend is running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")
    try:
        while True:
            # Receive JSON message containing image and lidar data
            message = await websocket.receive_text()
            payload = json.loads(message)
            
            # Extract components
            import base64
            image_b64 = payload.get("image", "")
            lidar_data = payload.get("lidar", {})
            
            image_bytes = base64.b64decode(image_b64) if image_b64 else None
            
            # Record start time for latency check
            start_time = time.time()
            
            # Process with Gemini (pass both image and lidar)
            command_data = await gemini_service.analyze_frame(image_bytes, lidar_data)
            
            # Calculate processing time
            process_time = time.time() - start_time
            command_data['latency'] = f"{process_time:.3f}s"
            
            # Send command back to client
            await websocket.send_json(command_data)
            
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error in websocket connection: {e}")
        try:
            await websocket.close()
        except:
            pass


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(memory_consolidation_loop())

async def memory_consolidation_loop():
    print("Memory consolidation daemon started.")
    while True:
        await asyncio.sleep(120)  # Wait 2 minutes
        try:
            # 1. Fetch & Update Goals
            print("Checking for new goals...")
            goal = await gemini_service.memory.fetch_goal()
            if goal:
                gemini_service.update_current_goal(goal)

            # 2. Consolidate Memory
            print("Consolidating memory from Firebase...")
            history = await gemini_service.memory.fetch_history()
            if history:
                # Summarize with Gemini
                print("Summarizing recent events...")
                summary = await gemini_service.summarize_memory(history)
                
                gemini_service.update_memory_context(summary)
                await gemini_service.memory.clear_history()
                print(f"Memory consolidated: {summary[:50]}...")
            else:
                print("No new memories to consolidate.")
        except Exception as e:
            print(f"Memory consolidation failed: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
