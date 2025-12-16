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
            # Receive binary frame
            data = await websocket.receive_bytes()
            
            # Record start time for latency check
            start_time = time.time()
            
            # Process with Gemini
            # We assume the client sends a new frame only after receiving a command,
            # or we might want to skip frames if processing is slow.
            # For this MVP, we process every frame received.
            
            command_data = await gemini_service.analyze_frame(data)
            
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
