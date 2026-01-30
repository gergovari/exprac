import time
from typing import Dict, Tuple

class RateLimitManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RateLimitManager, cls).__new__(cls)
            cls._instance.cooldowns = {} # (provider, model) -> timestamp
        return cls._instance

    def report_limit_hit(self, provider: str, model: str, cooldown_seconds: float = 60.0):
        """Mark a provider/model as rate limited for a duration."""
        key = (provider, model)
        until = time.time() + cooldown_seconds
        # If already limited further into future, keep that
        if key in self.cooldowns:
            self.cooldowns[key] = max(self.cooldowns[key], until)
        else:
            self.cooldowns[key] = until
        # print(f"[RateLimitManager] {provider}/{model} on cooldown until {time.ctime(until)}")

    def should_wait(self, provider: str, model: str) -> float:
        """Returns seconds to wait for this provider/model. 0 if ready."""
        key = (provider, model)
        if key not in self.cooldowns:
            return 0.0
        
        remaining = self.cooldowns[key] - time.time()
        if remaining <= 0:
            del self.cooldowns[key]
            return 0.0
        
        return remaining

class GlobalRateLimitError(Exception):
    def __init__(self, provider, model, wait_time):
        self.provider = provider
        self.model = model
        self.wait_time = wait_time
        super().__init__(f"{provider}/{model} is cooled down for {wait_time:.1f}s")
