import csv
import os
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class StatementEntry:
    id: int
    text: str
    is_true: bool

class StatementBank:
    def __init__(self, persistence_path: str = "data/bank.csv"):
        self.persistence_path = persistence_path
        self.statements: List[StatementEntry] = []
        self._next_id = 1
        self.load()

    def load(self):
        if not os.path.exists(self.persistence_path):
            return

        try:
            with open(self.persistence_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None) # Skip header
                if not header: return

                max_id = 0
                for row in reader:
                    if len(row) < 3: continue
                    try:
                        entry_id = int(row[0])
                        text = row[1]
                        is_true = row[2].lower() == 'true'
                        
                        self.statements.append(StatementEntry(entry_id, text, is_true))
                        if entry_id > max_id:
                            max_id = entry_id
                    except ValueError:
                        continue
                
                self._next_id = max_id + 1
        except Exception as e:
            print(f"Error loading bank: {e}")

    def save(self):
        # Ensure dir exists
        os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
        self.export_to_file(self.persistence_path, include_id=True)

    def add(self, text: str, is_true: bool) -> bool:
        """Adds a statement. Returns True if added, False if duplicate."""
        norm = text.strip().lower()
        if any(s.text.strip().lower() == norm for s in self.statements):
            return False

        entry = StatementEntry(id=self._next_id, text=text.strip(), is_true=is_true)
        self.statements.append(entry)
        self._next_id += 1
        self.save()
        return True

    def remove(self, entry_id: int) -> bool:
        initial_len = len(self.statements)
        self.statements = [s for s in self.statements if s.id != entry_id]
        if len(self.statements) < initial_len:
            self.save()
            return True
        return False

    def get_filtered(self, filter_type: str = "all", search_query: str = "") -> List[StatementEntry]:
        if filter_type == "true":
            base = [s for s in self.statements if s.is_true]
        elif filter_type == "false":
            base = [s for s in self.statements if not s.is_true]
        else:
            base = self.statements
        
        if search_query:
            q = search_query.lower()
            return [s for s in base if q in s.text.lower()]
            
        return base

    def import_from_file(self, path: str, default_truth: Optional[bool] = None) -> tuple[int, int]:
        added_count = 0
        dup_count = 0
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        _, ext = os.path.splitext(path)
        
        with open(path, 'r', encoding='utf-8') as f:
            if ext.lower() == '.csv':
                reader = csv.reader(f)
                for row in reader:
                    if not row: continue
                    text = row[0].strip()
                    if not text: continue
                    
                    is_true = False
                    if default_truth is not None:
                         is_true = default_truth
                    elif len(row) > 1:
                         is_true = row[1].lower().strip() in ('true', '1', 'yes', 't')
                    
                    if self.add(text, is_true):
                        added_count += 1
                    else:
                        dup_count += 1
            else:
                # Text file
                for line in f:
                    text = line.strip()
                    if not text: continue
                    is_true = default_truth if default_truth is not None else False
                    
                    if self.add(text, is_true):
                        added_count += 1
                    else:
                        dup_count += 1
                        
        self.save()
        return (added_count, dup_count)



    def export_to_file(self, path: str, filter_type: str = "all", include_id: bool = False) -> int:
        data = self.get_filtered(filter_type)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if include_id:
                writer.writerow(['id', 'statement', 'is_true'])
                for entry in data:
                    writer.writerow([entry.id, entry.text, entry.is_true])
            else:
                writer.writerow(['statement', 'is_true'])
                for entry in data:
                    writer.writerow([entry.text, entry.is_true])
        return len(data)
    
    # Helpers for Logic integration
    def get_known_true_texts(self) -> List[str]:
        return [s.text for s in self.statements if s.is_true]

    def get_known_false_texts(self) -> List[str]:
        return [s.text for s in self.statements if not s.is_true]
