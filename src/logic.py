from typing import List, Dict, Any
import asyncio
import os
from src.providers import GeminiProvider
from src.state import VerificationItem, VerificationState

class StatementChecker:
    def __init__(self, data_dir: str):
        self.true_file = os.path.join(data_dir, "true_statements.txt")
        self.false_file = os.path.join(data_dir, "false_statements.txt")
        # Initialize provider (could be dynamic later)
        self.provider = GeminiProvider()

    async def run_exact_check(self, item: VerificationItem, state: VerificationState):
        """Checks for an exact match and updates item."""
        item.exact_status = "Checking..."
        state.flag_changed()
        
        # Simulate some delay
        await asyncio.sleep(0.1)
        
        try:
            with open(self.true_file, 'r') as f:
                if item.statement in [line.strip() for line in f]:
                    item.exact_status = "True (Exact Match)"
                    state.flag_changed()
                    return
            
            with open(self.false_file, 'r') as f:
                if item.statement in [line.strip() for line in f]:
                    item.exact_status = "False (Exact Match)"
                    state.flag_changed()
                    return
                    
            item.exact_status = "Not Found"
        except FileNotFoundError:
            item.exact_status = "Error: Data files not found"
        
        state.flag_changed()

    async def run_fuzzy_check(self, item: VerificationItem, state: VerificationState):
        """Checks for fuzzy match and updates item."""
        item.fuzzy_status = "Checking..."
        state.flag_changed()

        known_true = []
        known_false = []
        try:
            with open(self.true_file, 'r') as f: known_true = [l.strip() for l in f]
            with open(self.false_file, 'r') as f: known_false = [l.strip() for l in f]
        except Exception:
            pass 

        def on_update(msg):
            item.fuzzy_status = msg
            state.flag_changed()

        res = await self.provider.check_similarity(item.statement, known_true, known_false, on_update=on_update)
        
        if res['status'] == 'found':
            item.fuzzy_status = f"{res['result']} (Fuzzy)"
            item.fuzzy_detail = res.get("note")
        elif res['status'] == 'not_found':
            item.fuzzy_status = "Not Found"
        else:
            item.fuzzy_status = f"Error: {res.get('message')}"
        
        state.flag_changed()

    async def run_llm_check(self, item: VerificationItem, state: VerificationState):
        """Checks truthfulness via LLM and updates item."""
        item.llm_status = "Checking..."
        state.flag_changed()

        def on_update(msg):
            item.llm_status = msg
            state.flag_changed()

        res = await self.provider.verify_truth(item.statement, on_update=on_update)
        
        if res['status'] == 'found':
            item.llm_status = f"{res['result']} (AI Knowledge)"
            item.llm_detail = res.get("note")
        else:
            item.llm_status = f"Error: {res.get('message')}"
        
        state.flag_changed()

    def run_all_checks(self, item: VerificationItem, state: VerificationState):
        """Spawns all checks for an item."""
        asyncio.create_task(self.run_exact_check(item, state))
        asyncio.create_task(self.run_fuzzy_check(item, state))
        asyncio.create_task(self.run_llm_check(item, state))
