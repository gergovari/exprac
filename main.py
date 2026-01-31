import asyncio
import os
import yaml
import json
import sys
from src.ui import App
from src.ratelimit import RateLimitManager

CONFIG_PATH = "config.yaml"

DEFAULT_CONFIG = {
    "language": "Hungarian",
    "data_path": "./data",
    "profiles": {
        "gemini_2_5_flash": {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key_name": "gemini"
        },
        "gemini_2_5_flash_lite": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
            "api_key_name": "gemini"
        },
        "gemini_3_flash": {
            "provider": "gemini",
            "model": "gemini-3-flash-preview",
            "api_key_name": "gemini"
        }
    },
    "chain": [
        "gemini_2_5_flash",
        "gemini_2_5_flash_lite",
        "gemini_3_flash"
    ]
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"[{CONFIG_PATH}] not found. Creating default configuration...")
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
        return DEFAULT_CONFIG
        
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def load_keys(keys_path):
    if not os.path.exists(keys_path):
        return {}
    try:
        with open(keys_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_keys(keys_path, keys):
    os.makedirs(os.path.dirname(keys_path), exist_ok=True)
    with open(keys_path, 'w') as f:
        json.dump(keys, f, indent=2)

def prompt_for_keys(config, current_keys):
    """Scans config for required keys and prompts if missing."""
    profiles = config.get('profiles', {})
    required_keys = set()
    
    for profile in profiles.values():
        key_name = profile.get('api_key_name')
        if key_name:
            required_keys.add(key_name)
            
    updated = False
    for key_name in required_keys:
        if key_name not in current_keys or not current_keys[key_name]:
            print(f"\n[Config] API Key required for '{key_name}'")
            val = input(f"Enter API Key (leave empty to disable associated providers): ").strip()
            if val:
                current_keys[key_name] = val
                updated = True
            else:
                 print(f"[Warning] No key provided. Providers requiring '{key_name}' may fail.")
    
    return current_keys, updated

if __name__ == "__main__":
    # 1. Load Config
    config = load_config()
    data_path = config.get("data_path", "data")
    keys_path = os.path.join(data_path, "keys.json")
    
    # 2. Configure Global Paths
    RateLimitManager.set_data_path(data_path)
    
    # 3. Load & Check Keys
    keys = load_keys(keys_path)
    keys, changed = prompt_for_keys(config, keys)
    
    if changed:
        save_keys(keys_path, keys)
        print(f"[Config] Keys saved to {keys_path}")

    # 4. Launch App
    app = App(config=config, api_keys=keys)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\nGoodbye!")
