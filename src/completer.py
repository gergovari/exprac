from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
import shlex
import re
import os

class ConsoleCompleter(Completer):
    def __init__(self, registry, bank=None):
        self.registry = registry
        self.bank = bank
        # expanduser=True allows ~/paths
        self.path_completer = PathCompleter(expanduser=True)

    def get_path_completions(self, text):
        dummy_doc = Document(text, cursor_position=len(text))
        for compl in self.path_completer.get_completions(dummy_doc, None):
            c_text = compl.text
            prefix = text[:len(text) + compl.start_position]
            full_path = prefix + c_text
            if os.path.isdir(os.path.expanduser(full_path)) and not c_text.endswith(os.sep):
                c_text += os.sep
            yield Completion(
                c_text,
                start_position=compl.start_position,
                display=compl.display,
                display_meta=compl.display_meta,
                style=compl.style,
                selected_style=compl.selected_style
            )

    def get_bank_completions(self, query):
        if not query: return
        q_low = query.lower()
        suggestions = set()
        
        for stmt in self.bank.statements:
            s_text = stmt.text
            idx = s_text.lower().find(q_low)
            if idx != -1:
                remainder = s_text[idx + len(query):]
                if not remainder: continue 
                
                next_chunk = ""
                if remainder[0] == ' ':
                    m = re.match(r"^(\s+\S+)", remainder)
                    if m: next_chunk = m.group(1)
                else:
                    m = re.match(r"^(\S+)", remainder)
                    if m: next_chunk = m.group(1)
                
                if next_chunk:
                    full_seg = s_text[idx : idx + len(query) + len(next_chunk)]
                    suggestions.add(full_seg)
        
        for s in sorted(list(suggestions)):
             yield Completion(s, start_position=-len(query))

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # Alias ? (Search), / (Search), . (Verify)
        if (text.startswith("?") or text.startswith("/") or text.startswith(".")) and self.bank:
             # Skip prefix
             start_idx = 1
             while start_idx < len(text) and text[start_idx] == ' ':
                 start_idx += 1
             
             query = text[start_idx:]
             yield from self.get_bank_completions(query)
             return

        # Robust splitting: Filter empty parts but keep trailing empty if space present
        raw_parts = [p for p in text.split(' ') if p]
        if text.endswith(' '):
            parts = raw_parts + ['']
        else:
            parts = raw_parts if raw_parts else ['']
            
        # Determine argument index being typed
        arg_index = len(parts) - 1
        current_word = parts[-1]
        
        # 1. Top Level Command
        if arg_index == 0:
             if not current_word or current_word.startswith(":"):
                 for name in self.registry.commands:
                     if name.startswith(current_word):
                         yield Completion(name, start_position=-len(current_word))
             return

        cmd_name = parts[0]
        cmd_obj = self.registry.commands.get(cmd_name)
        if cmd_obj:
             yield from cmd_obj.get_completions(self, current_word, parts[1:])

def create_completer(registry, bank=None):
    return ConsoleCompleter(registry, bank)
