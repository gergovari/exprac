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

class ModelNotFoundError(Exception):
    pass

class GeminiProvider(LLMProvider):
    def __init__(self, model_name: str = "gemini-2.5-flash", language: str = "English"):
        self.model_name = model_name
        self.language = language
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
            err_msg = str(e)
            # Check for Rate Limit 429
            if "429" in err_msg or "ResourceExhausted" in err_msg:
                # Report limit hit!
                rl_manager.report_limit_hit(self.provider_name, self.model_name, cooldown_seconds=60)
                raise GlobalRateLimitError(self.provider_name, self.model_name, 60)
            elif "404" in err_msg or "NOT_FOUND" in err_msg:
                raise ModelNotFoundError(f"Model '{self.model_name}' not found/supported")
            else:
                raise e

    async def check_similarity(self, statement: str, known_true: List[str], known_false: List[str], on_update=None) -> Dict[str, Any]:
        if not self.has_api_key:
             raise Exception("Missing API Key")

        try:
            prompt = f"""
            You are a verification assistant. Verify the 'Input Statement' using ONLY the provided 'Known True' and 'Known False' statements as your knowledge base.
            
            Known True: {json.dumps(known_true)}
            Known False: {json.dumps(known_false)}
            
            Input Statement: "{statement}"
            
            Task:
            1. Semantically Equivalent: Treat statements as the same if they refer to the same attribute of the same subject, even if modifiers like "relatively", "basically", or "very" are present or absent.
            2. Logical Implication:
               - If a statement is Known False, its variations with weaker/stronger modifiers are likely also False.
               - If "X is Y" is False, and Z is the opposite of Y, then "X is Z" might be True (if the domain implies binary options like fast/slow).
            
            Guidance:
            - If "Tiger is relatively slow" is False, then "Tiger is slow" is also False.
            - If "Tiger is slow" is False, "Tiger is fast" is likely True.
            
            Determine the truth value if ANY strong logical link exists.
            IMPORTANT: The 'reason' field MUST be in {self.language} language.
            
            Return JSON only:
            {{
                "determined": boolean,   // true if you can determine the truth value based on the lists
                "truth_value": boolean,  // true/false (if determined)
                "reason": "explanation of the link or match"
            }}
            """
            
            response = await self._generate_with_retry(prompt, on_update=on_update)
            
            try:
                text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(text)
                
                if data.get("determined"):
                    return {
                        "status": "found", 
                        "result": data.get("truth_value"), 
                        "source": "Bank Inference", 
                        "note": data.get("reason")
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
            Return JSON only: {{"is_true": bool, "explanation": "short explanation in {self.language}"}}
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
