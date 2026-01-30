import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in environment.")
    exit(1)

client = genai.Client(api_key=api_key)

try:
    print("Listing available models...")
    # The new SDK might use a different method to list models, checking basics first
    # Using the low-level client or iterating if possible. 
    # The SDK structure: client.models.list() usually.
    
    # We will try the standard way for the new SDK
    pager = client.models.list()
    for model in pager:
        print(f"Model: {model.name}")
        print(f"  Display Name: {model.display_name}")
        print(f"  Supported Actions: {model.supported_generation_methods}")
        print("-" * 20)
        
except Exception as e:
    print(f"Error listing models: {e}")
