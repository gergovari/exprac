from abc import ABC, abstractmethod
import os
import asyncio
import json
from typing import Dict, Any, List
from google import genai
from dotenv import load_dotenv
from src.ratelimit import RateLimitManager, GlobalRateLimitError

load_dotenv()

class LLMProvider(ABC):
    @abstractmethod
    async def check_similarity(self, statement: str, known_true: List[str], known_false: List[str], on_update=None) -> Dict[str, Any]:
        """Checks if a statement is similar to known true/false lists."""
        pass

    @abstractmethod
    async def verify_truth(self, statement: str, on_update=None) -> Dict[str, Any]:
        """Verifies the truth of a statement using general knowledge."""
        pass

class GeminiProvider(LLMProvider):
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        self.provider_name = "gemini"
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
            self.has_api_key = True
        else:
            self.has_api_key = False

    async def _generate_with_retry(self, prompt: str, on_update=None) -> Any:
        # Check global limit logic first
        rl_manager = RateLimitManager()
        wait_time = rl_manager.should_wait(self.provider_name, self.model_name)
        if wait_time > 0:
            raise GlobalRateLimitError(self.provider_name, self.model_name, wait_time)

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt
            )
            return response
        except Exception as e:
            # Check for Rate Limit 429
            if "429" in str(e) or "ResourceExhausted" in str(e):
                # Report limit hit!
                rl_manager.report_limit_hit(self.provider_name, self.model_name, cooldown_seconds=60)
                raise GlobalRateLimitError(self.provider_name, self.model_name, 60)
            else:
                raise e

    async def check_similarity(self, statement: str, known_true: List[str], known_false: List[str], on_update=None) -> Dict[str, Any]:
        if not self.has_api_key:
             raise Exception("Missing API Key")

        try:
            prompt = f"""
            You are a verification assistant. Compare the input statement against the known true and false statements.
            
            Known True: {json.dumps(known_true)}
            Known False: {json.dumps(known_false)}
            
            Input Statement: "{statement}"
            
            Task:
            1. Determine if the input statement is semantically very similar to any statement in the known lists.
            2. If match found in Known True, result is True.
            3. If match found in Known False, result is False.
            4. If no clear match, result is null.
            
            Return JSON only: {{"match_found": bool, "result": bool/null, "similar_to": "string or null"}}
            """
            
            response = await self._generate_with_retry(prompt, on_update=on_update)
            
            try:
                text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(text)
                
                if data.get("match_found"):
                    return {
                        "status": "found", 
                        "result": data.get("result"), 
                        "source": "Fuzzy Match", 
                        "note": f"Similar to: {data.get('similar_to')}"
                    }
                else:
                    return {"status": "not_found", "result": None, "source": "Fuzzy Match"}
            except json.JSONDecodeError:
                 raise ValueError("Invalid LLM Response")

        except GlobalRateLimitError:
            raise

    async def verify_truth(self, statement: str, on_update=None) -> Dict[str, Any]:
        if not self.has_api_key:
             raise Exception("Missing API Key")

        try:
            prompt = f"""
            Verify the factual accuracy of this statement: "{statement}".
            Return JSON only: {{"is_true": bool, "explanation": "short explanation"}}
            """
            
            response = await self._generate_with_retry(prompt, on_update=on_update)
            
            try:
                text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(text)
                
                return {
                    "status": "found", 
                    "result": data.get("is_true"), 
                    "source": "AI Knowledge",
                    "note": data.get("explanation")
                }
            except json.JSONDecodeError:
                raise ValueError("Invalid LLM Response")

        except GlobalRateLimitError:
            raise
