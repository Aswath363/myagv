import httpx
import asyncio
import json
import time

class MemoryService:
    def __init__(self):
        # Base URL for Firebase Realtime Database
        self.db_url = "https://myagv-57b9a-default-rtdb.asia-southeast1.firebasedatabase.app"
        self.logs_path = "/agv_logs.json"
        
    async def add_log(self, data: dict):
        """
        Pushes a new log entry to the database.
        """
        async with httpx.AsyncClient() as client:
            try:
                # Add timestamp
                data["timestamp"] = time.time()
                await client.post(f"{self.db_url}{self.logs_path}", json=data)
            except Exception as e:
                print(f"Failed to log to Firebase: {e}")

    async def fetch_history(self):
        """
        Fetches all logs, summarizes them, and returns a text summary.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.db_url}{self.logs_path}")
                if response.status_code == 200 and response.content:
                    data = response.json()
                    if not data:
                        return None
                    
                    # Convert dict of push_ids to list
                    history_items = []
                    for key, value in data.items():
                        if isinstance(value, dict) and 'reasoning' in value:
                             history_items.append(f"- {value.get('reasoning')}")
                    
                    return "\n".join(history_items)
                return None
            except Exception as e:
                print(f"Failed to fetch history: {e}")
                return None

    async def clear_history(self):
        """
        Clears the logs from the database.
        """
        async with httpx.AsyncClient() as client:
            try:
                await client.delete(f"{self.db_url}{self.logs_path}")
            except Exception as e:
                print(f"Failed to clear history: {e}")
    async def fetch_goal(self):
        """
        Fetches the current high-level goal from the database.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.db_url}/agv_goals.json")
                if response.status_code == 200 and response.content:
                    data = response.json()
                    if data and isinstance(data, dict):
                        return data.get("current_goal")
                return None
            except Exception as e:
                print(f"Failed to fetch goal: {e}")
                return None
