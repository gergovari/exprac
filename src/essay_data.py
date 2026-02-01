import json
import csv
import os
import asyncio
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MaterialItem:
    path: str
    id: int = 0
    # Mapping of provider_name to its specific file handle/object
    file_handles: Optional[dict] = None 

    def __post_init__(self):
        if self.file_handles is None:
            self.file_handles = {}

class MaterialBank:
    def __init__(self, persistence_file="data/materials.json"):
        self.items: List[MaterialItem] = []
        self.persistence_file = persistence_file
        self._load()
    
    def _load(self):
        if not os.path.exists(self.persistence_file): return
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
                self.items = [MaterialItem(**d) for d in data]
        except Exception:
            self.items = []

    def _save(self):
        try:
            # Don't save file_handle, it's runtime only
            data = [{"path": i.path, "id": i.id} for i in self.items]
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving MaterialBank: {e}")

    def add_item(self, path: str) -> MaterialItem:
        # Dedup
        for i in self.items:
            if i.path == path: return i
            
        new_id = 1
        if self.items:
             new_id = max(i.id for i in self.items) + 1
        
        item = MaterialItem(path=path, id=new_id)
        self.items.append(item)
        self._save()
        return item

    def remove_item(self, item_id: int):
        self.items = [i for i in self.items if i.id != item_id]
        self._save()

@dataclass
class EssayExample:
    question: str
    answer: str
    id: int = 0

class EssayBank:
    def __init__(self, persistence_file="data/essay_examples.csv"):
        self.examples: List[EssayExample] = []
        self.persistence_file = persistence_file
        self._load()

    def _load(self):
        if not os.path.exists(self.persistence_file): return
        try:
            with open(self.persistence_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                self.examples = []
                for i, row in enumerate(reader):
                    if len(row) >= 2:
                        self.examples.append(EssayExample(question=row[0], answer=row[1], id=i+1))
        except Exception:
            self.examples = []

    def _save(self):
        try:
            with open(self.persistence_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                for ex in self.examples:
                    writer.writerow([ex.question, ex.answer])
        except Exception as e:
            print(f"Error saving EssayBank: {e}")

    def add_example(self, question: str, answer: str) -> bool:
        """Adds an example with duplicate detection. Returns True if added, False if duplicate."""
        q_norm = question.strip().lower()
        a_norm = answer.strip().lower()
        
        for ex in self.examples:
            if ex.question.strip().lower() == q_norm and ex.answer.strip().lower() == a_norm:
                return False
        
        new_id = 1
        if self.examples:
            new_id = max(e.id for e in self.examples) + 1
        
        self.examples.append(EssayExample(question=question.strip(), answer=answer.strip(), id=new_id))
        self._save()
        return True

    def import_from_file(self, path: str) -> tuple[int, int]:
        """Imports examples from a CSV, appending them. Returns (added_count, duplicate_count)."""
        added_count = 0
        dup_count = 0
        try:
            with open(path, 'r', newline='', encoding='utf-8') as f:
                # Sniff delimiter
                try:
                    sample = f.read(2048)
                    f.seek(0)
                    dialect = csv.Sniffer().sniff(sample)
                    delimiter = dialect.delimiter
                except csv.Error:
                    f.seek(0)
                    delimiter = ',' # Fallback
                
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if len(row) >= 2:
                        # Skip header heuristic
                        if added_count == 0 and dup_count == 0 and \
                           row[0].strip().lower() == "question" and row[1].strip().lower() == "answer":
                            continue

                        if self.add_example(row[0], row[1]):
                            added_count += 1
                        else:
                            dup_count += 1
            return (added_count, dup_count)
        except Exception as e:
            # print(f"Import error: {e}") # Debug
            return (0, 0)
            
    def remove_item(self, item_id: int):
        self.examples = [e for e in self.examples if e.id != item_id]
        self._save()

@dataclass
class EssayItem:
    question: str
    answer: Optional[str] = None
    status: str = "Pending" # Pending, Uploading, Generating, Done, Error
    id: int = 0

class EssaySession:
    def __init__(self, persistence_file="data/essay_history.json"):
        self.items: List[EssayItem] = []
        self.persistence_file = persistence_file
        self._load()
        
    def _load(self):
        if not os.path.exists(self.persistence_file): return
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
                self.items = [EssayItem(**d) for d in data]
        except Exception:
            self.items = []

    def save(self):
        try:
            data = [vars(i) for i in self.items]
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_question(self, question: str) -> EssayItem:
        new_id = 1
        if self.items: new_id = max(i.id for i in self.items) + 1
        item = EssayItem(question=question, id=new_id)
        self.items.append(item)
        self.save()
        return item
    def remove_item(self, item_id: int):
        self.items = [i for i in self.items if i.id != item_id]
        self.save()
