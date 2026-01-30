import time
import json
import os
from typing import Dict, Tuple

class RateLimitManager:
    _instance = None
    _file_path = "data/ratelimits.json"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RateLimitManager, cls).__new__(cls)
            cls._instance.cooldowns = {} # (provider, model) -> timestamp
            cls._instance._load()
        return cls._instance

    def _load(self):
        if not os.path.exists(self._file_path):
            return
        try:
            with open(self._file_path, 'r') as f:
                data = json.load(f)
                # Convert string keys "provider:model" back to tuple
                for key_str, ts in data.items():
                    if ":" in key_str:
                        p, m = key_str.split(":", 1)
                        # Only keep if future
                        if ts > time.time():
                            self.cooldowns[(p, m)] = ts
        except Exception:
            pass # Ignore corrupt file

    def _save(self):
        data = {}
        now = time.time()
        for (p, m), ts in self.cooldowns.items():
            if ts > now:
                data[f"{p}:{m}"] = ts
        
        try:
            with open(self._file_path, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def report_limit_hit(self, provider: str, model: str, cooldown_seconds: float = 60.0):
        """Mark a provider/model as rate limited for a duration."""
        key = (provider, model)
        until = time.time() + cooldown_seconds
        # If already limited further into future, keep that
        if key in self.cooldowns:
            self.cooldowns[key] = max(self.cooldowns[key], until)
        else:
            self.cooldowns[key] = until
        
        self._save()
        # print(f"[RateLimitManager] {provider}/{model} on cooldown until {time.ctime(until)}")

    def should_wait(self, provider: str, model: str) -> float:
        """Returns seconds to wait for this provider/model. 0 if ready."""
        key = (provider, model)
        if key not in self.cooldowns:
            return 0.0
        
        remaining = self.cooldowns[key] - time.time()
        if remaining <= 0:
            del self.cooldowns[key]
            self._save() # Clean up expired
            return 0.0
        
        return remaining

class GlobalRateLimitError(Exception):
    def __init__(self, provider, model, wait_time):
        self.provider = provider
        self.model = model
        self.wait_time = wait_time
        super().__init__(f"{provider}/{model} is cooled down for {wait_time:.1f}s")
