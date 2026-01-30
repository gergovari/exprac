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

    def add(self, text: str, is_true: bool) -> int:
        entry = StatementEntry(id=self._next_id, text=text, is_true=is_true)
        self.statements.append(entry)
        self._next_id += 1
        self.save()
        return entry.id

    def remove(self, entry_id: int) -> bool:
        initial_len = len(self.statements)
        self.statements = [s for s in self.statements if s.id != entry_id]
        if len(self.statements) < initial_len:
            self.save()
            return True
        return False

    def get_filtered(self, filter_type: str = "all") -> List[StatementEntry]:
        if filter_type == "true":
            return [s for s in self.statements if s.is_true]
        elif filter_type == "false":
            return [s for s in self.statements if not s.is_true]
        return self.statements

    def import_from_file(self, path: str, default_truth: Optional[bool] = None) -> int:
        count = 0
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        # Basic Check: is it CSV or txt?
        # If txt, we read lines. If CSV, we expect columns.
        _, ext = os.path.splitext(path)
        
        with open(path, 'r', encoding='utf-8') as f:
            if ext.lower() == '.csv':
                reader = csv.reader(f)
                for row in reader:
                    # Expected format: "statement", "true/false" OR just "statement" if default provided
                    if not row: continue
                    
                    text = row[0].strip()
                    if not text: continue
                    
                    if default_truth is not None:
                        is_true = default_truth
                    else:
                        # Try to parse 2nd column
                        if len(row) > 1:
                            val = row[1].lower().strip()
                            is_true = val in ('true', '1', 'yes', 't')
                        else:
                            # Skip if unclear
                            continue
                    
                    # Internal add without save (optimize)
                    entry_id = self._next_id
                    self.statements.append(StatementEntry(id=entry_id, text=text, is_true=is_true))
                    self._next_id += 1
                    count += 1
            else:
                # Assume raw text, one per line
                if default_truth is None:
                    raise ValueError("Must provide default truth value for text files.")
                
                for line in f:
                    line = line.strip()
                    if line:
                        entry_id = self._next_id
                        self.statements.append(StatementEntry(id=entry_id, text=line, is_true=default_truth))
                        self._next_id += 1
                        count += 1
        
        if count > 0:
            self.save()
        return count

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
