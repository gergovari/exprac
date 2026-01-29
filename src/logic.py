import asyncio
import os
from typing import List, Dict, Any

class StatementChecker:
    def __init__(self, data_dir: str):
        self.true_file = os.path.join(data_dir, "true_statements.txt")
        self.false_file = os.path.join(data_dir, "false_statements.txt")

    async def check_exact(self, statement: str) -> Dict[str, Any]:
        """Checks for an exact match in the local files."""
        # Simulate some delay
        await asyncio.sleep(0.5)
        
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
        """Checks for a fuzzy match using LLM (Mocked)."""
        await asyncio.sleep(1.5) # Simulate network call
        # Mock logic
        return {"status": "found", "result": True, "source": "Fuzzy Match (Mock)", "note": "Similar to '...'"}

    async def check_llm_direct(self, statement: str) -> Dict[str, Any]:
        """Checks truthfulness using general knowledge (Mocked)."""
        await asyncio.sleep(2.5) # Simulate longer network call
        return {"status": "found", "result": True, "source": "AI Knowledge (Mock)"}

    async def verify_statement(self, statement: str) -> List[Dict[str, Any]]:
        """Runs all checks in parallel."""
        results = await asyncio.gather(
            self.check_exact(statement),
            self.check_fuzzy(statement),
            self.check_llm_direct(statement)
        )
        return results
