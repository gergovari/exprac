from google import genai
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("No API Key found")
    exit(1)

client = genai.Client(api_key=api_key)

print("Listing available models...")
try:
    # New SDK wrapper for listing models
    for m in client.models.list(config={'page_size': 100}):
        print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
