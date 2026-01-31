from typing import List, Dict, Any, Optional
import asyncio
import os
from src.manager import ProviderManager
from src.state import VerificationItem, VerificationState
from src.bank import StatementBank

class StatementChecker:
    def __init__(self, data_dir: str, bank: Optional[StatementBank] = None, api_keys: dict = None):
        self.data_dir = data_dir
        self.bank = bank
        self.true_file = os.path.join(data_dir, "true_statements.txt")
        self.false_file = os.path.join(data_dir, "false_statements.txt")
        # Initialize manager with keys
        self.manager = ProviderManager(api_keys=api_keys)

    async def _check_file(self, file_path: str, statement: str) -> bool:
        try:
            with open(file_path, 'r') as f:
                return statement in [line.strip().lower() for line in f]
        except FileNotFoundError:
            return False

    async def _read_lines(self, file_path: str) -> List[str]:
        try:
            with open(file_path, 'r') as f:
                return [line.strip() for line in f]
        except FileNotFoundError:
            return []

    def _update_fuzzy_loading(self, item: VerificationItem, state: VerificationState, msg: str):
        item.fuzzy_status = msg
        state.update_item(item)

    async def run_exact_check(self, item: VerificationItem, state: VerificationState):
        """Checks for an exact match and updates item."""
        item.exact_status = "Checking..."
        state.update_item(item) # Use update_item instead of flag_changed

        stmt = item.statement.strip().lower()

        if self.bank:
            # Check bank first
            for entry in self.bank.statements:
                if entry.text.strip().lower() == stmt:
                    item.exact_status = "True" if entry.is_true else "False"
                    state.update_item(item)
                    return

        # Fallback to files if bank not set or not found (legacy behavior)
        if await self._check_file(self.true_file, stmt):
            item.exact_status = "True (Exact Match)"
        elif await self._check_file(self.false_file, stmt):
            item.exact_status = "False (Exact Match)"
        else:
            item.exact_status = "Not Found"

        state.update_item(item) # Use update_item instead of flag_changed

    async def run_fuzzy_check(self, item: VerificationItem, state: VerificationState):
        """Checks for fuzzy match and updates item."""
        item.fuzzy_status = "Checking..."
        state.flag_changed()

        known_true = []
        known_false = []
        if self.bank:
            known_true = [s.text for s in self.bank.statements if s.is_true]
            known_false = [s.text for s in self.bank.statements if not s.is_true]
        else:
            try:
                with open(self.true_file, 'r') as f: known_true = [l.strip() for l in f]
                with open(self.false_file, 'r') as f: known_false = [l.strip() for l in f]
            except Exception:
                pass 

        def on_update(msg):
            item.fuzzy_status = msg
            state.flag_changed()

        try:
            res = await self.manager.execute_with_fallback(
                'check_similarity', 
                item.statement, known_true, known_false, 
                on_update=on_update
            )
            
            if res['status'] == 'found':
                item.fuzzy_status = f"{res['result']} (Fuzzy)"
                item.fuzzy_detail = res.get("note")
            elif res['status'] == 'not_found':
                item.fuzzy_status = "Not Found"
            else:
                item.fuzzy_status = f"Error: {res.get('message')}"
        except Exception as e:
            item.fuzzy_status = f"Error: {str(e)}"
        
        state.flag_changed()

    async def run_llm_check(self, item: VerificationItem, state: VerificationState):
        """Checks truthfulness via LLM and updates item."""
        item.llm_status = "Checking..."
        state.flag_changed()

        def on_update(msg):
            item.llm_status = msg
            state.flag_changed()

        try:
            res = await self.manager.execute_with_fallback(
                'verify_truth', 
                item.statement, 
                on_update=on_update
            )
            
            if res['status'] == 'found':
                item.llm_status = f"{res['result']} (AI Knowledge)"
                item.llm_detail = res.get("note")
            else:
                item.llm_status = f"Error: {res.get('message')}"
        except Exception as e:
             item.llm_status = f"Error: {str(e)}"
        
        state.flag_changed()

    def run_all_checks(self, item: VerificationItem, state: VerificationState):
        """Spawns all checks for an item."""
        asyncio.create_task(self.run_exact_check(item, state))
        asyncio.create_task(self.run_fuzzy_check(item, state))
        asyncio.create_task(self.run_llm_check(item, state))
