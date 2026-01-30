import yaml
import os
import asyncio
from typing import List, Any
from src.providers import GeminiProvider, ModelNotFoundError
from src.ratelimit import RateLimitManager, GlobalRateLimitError

class ProviderManager:
    def __init__(self, config_path="config.yaml"):
        self.providers = []
        self._load_config(config_path)
    
    def _load_config(self, path):
        if not os.path.exists(path):
            # Fallback default if no config
            print("Config not found, using default Gemini Flash")
            self.providers.append(GeminiProvider(model_name="gemini-2.5-flash"))
            return

        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        
        profiles = config.get('profiles', {})
        chain = config.get('chain', [])
        
        # Support old format for backward compatibility (optional, but good practice)
        if not profiles and chain and isinstance(chain[0], dict):
            # Old format: chain is list of dicts
            for entry in chain:
                self._create_provider_from_dict(entry)
            return

        # New format: chain is list of strings (profile names)
        for profile_name in chain:
            if isinstance(profile_name, str):
                profile = profiles.get(profile_name)
                if profile:
                    self._create_provider_from_dict(profile)
                else:
                    print(f"Warning: Profile '{profile_name}' not found in config.")
            elif isinstance(profile_name, dict):
                 # Mixed/Inline usage?
                 self._create_provider_from_dict(profile_name)

    def _create_provider_from_dict(self, entry):
        provider_type = entry.get('provider')
        model = entry.get('model')
        
        if provider_type == 'gemini':
            self.providers.append(GeminiProvider(model_name=model))
        # Add other providers here
            
    async def execute_with_fallback(self, method_name: str, *args, on_update=None, **kwargs) -> Any:
        """
        Tries to execute `method_name` on providers in the chain.
        If a provider is rate limited, tries the next.
        If all are rate limited, waits for the shortest cooldown and retries.
        """
        rl_manager = RateLimitManager()
        
        while True:
            # Track if we found any available provider to avoid infinite tight loop if config is empty
            attempted_any = False
            min_wait = float('inf')
            
            for provider in self.providers:
                attempted_any = True
                
                # Pre-check cooldown
                wait = rl_manager.should_wait(provider.provider_name, provider.model_name)
                if wait > 0:
                    min_wait = min(min_wait, wait)
                    continue

                try:
                    # Execute method
                    method = getattr(provider, method_name)
                    return await method(*args, on_update=on_update, **kwargs)
                
                except GlobalRateLimitError as e:
                    # Provider hit limit during execution
                    min_wait = min(min_wait, e.wait_time)
                    continue
                except ModelNotFoundError as e:
                    # Config error - report and skip permanently (well, for this loop)
                    if on_update:
                        on_update(f"[Warning] {e}. Skipping...")
                    # Give user time to read
                    await asyncio.sleep(2.0)
                    continue
                except Exception as e:
                    # Non-rate-limit error? For now, maybe fail, or log and continue?
                    # If it's authentication error, we should probably fail.
                    # If it's a 500, maybe fallback.
                    # For safety, let's treat generic errors as "Try next" but log it.
                    if on_update:
                        on_update(f"Error on {provider.model_name}: {str(e)}")
                    continue
            
            if not attempted_any:
                raise Exception("No providers configured.")
                
            # All providers limited or failed.
            if min_wait == float('inf'):
                # Means we didn't hit rate limits, but maybe other errors on all of them?
                # Or config empty.
                wait_time = 5
            else:
                wait_time = min(min_wait + 0.1, 60) # Add buffer, cap at 60
            
            msg = f"All providers busy. Retrying in {wait_time:.1f}s..."
            if on_update:
                on_update(msg)
            
            await asyncio.sleep(wait_time)
            
            if on_update:
                on_update("Retrying fallback chain...")
