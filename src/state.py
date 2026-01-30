import json
import os
from dataclasses import dataclass, field
from typing import List, Optional
import asyncio

@dataclass
class VerificationItem:
    statement: str
    id: int = 0
    exact_status: str = "Pending"
    fuzzy_status: str = "Pending"
    llm_status: str = "Pending"
    
    # Store detailed results or errors to show on hover/selection later if needed
    exact_detail: Optional[str] = None
    fuzzy_detail: Optional[str] = None
    llm_detail: Optional[str] = None

class VerificationState:
    def __init__(self, persistence_file="data/vs_history.json"):
        self.items: List[VerificationItem] = []
        self._lock = asyncio.Lock()
        self.changed = True # Dirty flag for UI redraw
        self.persistence_file = persistence_file
        self._load()

    def _load(self):
        if not os.path.exists(self.persistence_file): return
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
                self.items = []
                # Reconstruct items
                for d in data:
                    # Filter out keys not in dataclass if schema changed, or strict
                    # For safety, explicit call or **d if stable
                    # We might need to handle new fields (default values)
                    # Safe logic: **d works if d keys match fields. 
                    # If we add fields, d might lack them -> defaults used.
                    item = VerificationItem(**d)
                    self.items.append(item)
        except Exception as e:
            print(f"Error loading VS history: {e}")

    def _save(self):
         try:
             # Convert to dicts
             data = [vars(i) for i in self.items]
             with open(self.persistence_file, 'w') as f:
                 json.dump(data, f, indent=2)
         except Exception as e:
             print(f"Error saving VS history: {e}")

    async def add_item(self, statement: str) -> VerificationItem:
        async with self._lock:
            # Dedup: Check existence
            existing = next((i for i in self.items if i.statement == statement), None)
            if existing:
                self.items.remove(existing)
                self.items.append(existing) # Move to end
                self.changed = True
                self._save()
                return existing

            # Assign ID
            new_id = 1
            if self.items:
                 new_id = max(i.id for i in self.items) + 1
            
            item = VerificationItem(statement=statement, id=new_id)
            self.items.append(item)
            self.changed = True
            self._save()
            return item
    
    async def remove_item(self, item_id: int):
         async with self._lock:
             self.items = [i for i in self.items if i.id != item_id]
             self.changed = True
             self._save()

    # We generally object-reference modify items, so specific update methods 
    # might not be strictly needed if we pass the item to the worker, 
    # but having a method triggers the dirty flag.
    def flag_changed(self):
        self.changed = True
        self._save()

    def update_item(self, item: VerificationItem):
        """Signal that an item has been updated."""
        self.changed = True
        self._save()
