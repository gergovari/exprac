import asyncio
import os
from typing import List, Dict, Any
from src.providers import GeminiProvider

class StatementChecker:
    def __init__(self, data_dir: str):
        self.true_file = os.path.join(data_dir, "true_statements.txt")
        self.false_file = os.path.join(data_dir, "false_statements.txt")
        # Initialize provider (could be dynamic later)
        self.provider = GeminiProvider()

    async def check_exact(self, statement: str) -> Dict[str, Any]:
        """Checks for an exact match in the local files."""
        # Simulate some delay
        await asyncio.sleep(0.1)
        
        try:
            with open(self.true_file, 'r') as f:
                if statement in [line.strip() for line in f]:
                    return {"status": "found", "result": True, "source": "Exact Match"}
            
            with open(self.false_file, 'r') as f:
                if statement in [line.strip() for line in f]:
                    return {"status": "found", "result": False, "source": "Exact Match"}
                    
        except FileNotFoundError:
            return {"status": "error", "message": "Data files not found."}

        return {"status": "not_found", "result": None, "source": "Exact Match"}

    async def check_fuzzy(self, statement: str) -> Dict[str, Any]:
        """Checks for a fuzzy match using LLM provider."""
        # Read data
        known_true = []
        known_false = []
        try:
            with open(self.true_file, 'r') as f: known_true = [l.strip() for l in f]
            with open(self.false_file, 'r') as f: known_false = [l.strip() for l in f]
        except Exception:
            pass # Proceed even if empty

        return await self.provider.check_similarity(statement, known_true, known_false)

    async def check_llm_direct(self, statement: str) -> Dict[str, Any]:
        """Checks truthfulness using general knowledge via provider."""
        return await self.provider.verify_truth(statement)

    async def verify_statement(self, statement: str) -> List[Dict[str, Any]]:
        """Runs all checks in parallel."""
        results = await asyncio.gather(
            self.check_exact(statement),
            self.check_fuzzy(statement),
            self.check_llm_direct(statement)
        )
        return results
