from dataclasses import dataclass, field
from typing import List, Optional
import asyncio

@dataclass
class VerificationItem:
    statement: str
    exact_status: str = "Pending"
    fuzzy_status: str = "Pending"
    llm_status: str = "Pending"
    
    # Store detailed results or errors to show on hover/selection later if needed
    exact_detail: Optional[str] = None
    fuzzy_detail: Optional[str] = None
    llm_detail: Optional[str] = None

class VerificationState:
    def __init__(self):
        self.items: List[VerificationItem] = []
        self._lock = asyncio.Lock()
        self.changed = True # Dirty flag for UI redraw

    async def add_item(self, statement: str) -> VerificationItem:
        async with self._lock:
            item = VerificationItem(statement=statement)
            self.items.append(item)
            self.changed = True
            return item

    # We generally object-reference modify items, so specific update methods 
    # might not be strictly needed if we pass the item to the worker, 
    # but having a method triggers the dirty flag.
    def flag_changed(self):
        self.changed = True
