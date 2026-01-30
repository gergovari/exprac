from abc import ABC, abstractmethod
import os
import asyncio
import json
from typing import Dict, Any, List
from google import genai
from dotenv import load_dotenv

load_dotenv()

class LLMProvider(ABC):
    @abstractmethod
    async def check_similarity(self, statement: str, known_true: List[str], known_false: List[str]) -> Dict[str, Any]:
        """Checks if a statement is similar to known true/false lists."""
        pass

    @abstractmethod
    async def verify_truth(self, statement: str) -> Dict[str, Any]:
        """Verifies the truth of a statement using general knowledge."""
        pass

class GeminiProvider(LLMProvider):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
            self.has_api_key = True
        else:
            self.has_api_key = False

    async def check_similarity(self, statement: str, known_true: List[str], known_false: List[str]) -> Dict[str, Any]:
        if not self.has_api_key:
             return {"status": "error", "message": "Missing API Key"}

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
            
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model='gemini-2.5-flash',
                contents=prompt
            )
            
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
                 return {"status": "error", "message": "Invalid LLM Response"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def verify_truth(self, statement: str) -> Dict[str, Any]:
        if not self.has_api_key:
             return {"status": "error", "message": "Missing API Key"}

        try:
            prompt = f"""
            Verify the factual accuracy of this statement: "{statement}".
            Return JSON only: {{"is_true": bool, "explanation": "short explanation"}}
            """
            
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model='gemini-2.5-flash',
                contents=prompt
            )
            
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
                return {"status": "error", "message": "Invalid LLM Response"}

        except Exception as e:
            return {"status": "error", "message": str(e)}
