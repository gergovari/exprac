import os

def setup_env():
    print("This script will help you set up your Gemini API key.")
    print("1. Go to https://aistudio.google.com/app/apikey")
    print("2. Sign in with your Google account.")
    print("3. Click 'Create API key'.")
    print("4. Copy the key starting with 'AIza...'.\n")
    
    key = input("Enter your API Key: ").strip()
    
    if not key:
        print("No key entered. Exiting.")
        return

    with open(".env", "w") as f:
        f.write(f"GEMINI_API_KEY={key}\n")
    
    print("\nSuccess! .env file created.")
    print("You can now run the app with: source venv/bin/activate && python main.py")

if __name__ == "__main__":
    setup_env()
