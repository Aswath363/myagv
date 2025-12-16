import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def list_models():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)
    
    print("Listing available models...")
    try:
        # Synchronous list
        for model in client.models.list(config={"page_size": 100}):
            print(f"Model: {model.name}")
            print(f"  DisplayName: {model.display_name}")
            print("-" * 20)
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
