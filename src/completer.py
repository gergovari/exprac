from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
import shlex

class ConsoleCompleter(Completer):
    def __init__(self, registry, bank=None):
        self.registry = registry
        self.bank = bank
        # expanduser=True allows ~/paths
        self.path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # Alias ? Logic (Prefix-based)
        if text.startswith("?") and self.bank:
            try:
                query = text[1:]
                if query:
                    q_low = query.lower()
                    suggestions = set()
                    import re
                    
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
            except:
                pass
            return

        parts = text.split(' ')
        
        # Current word is the last part
        current_word = parts[-1]
        
        # Determine argument index being typed
        arg_index = len(parts) - 1
        
        # 1. Top Level Command
        if arg_index == 0:
             if not current_word or current_word.startswith(":"):
                 for name in self.registry.commands:
                     if name.startswith(current_word):
                         yield Completion(name, start_position=-len(current_word))
             return

        cmd = parts[0]
        
        # 2. :sb Logic
        if cmd == ":sb":
            # Subcommand
            if arg_index == 1:
                subcmds = ["add", "remove", "import", "export", "true", "false", "all", "search"]
                for s in subcmds:
                    if s.startswith(current_word):
                        yield Completion(s, start_position=-len(current_word))
                return
            
            subcmd = parts[1]
            
            # Special handling for search to allow multi-word completion (Sentence completion)
            if subcmd == "search" and self.bank and arg_index >= 2:
                try:
                    search_idx = text.lower().find("search")
                    if search_idx != -1:
                        prefix_start = search_idx + 6 
                        # skip spaces
                        while prefix_start < len(text) and text[prefix_start] == ' ':
                            prefix_start += 1
                        
                        query = text[prefix_start:]
                        if not query: return
                        
                        q_low = query.lower()
                        suggestions = set()
                        import re
                        
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
                except Exception:
                    pass
                return

            # Arg 2: File Path (import/export)
            if arg_index == 2:
                if subcmd in ["import", "export"]:
                    dummy_doc = Document(current_word, cursor_position=len(current_word))
                    yield from self.path_completer.get_completions(dummy_doc, complete_event)
                return

            # Arg 3: Boolean (add, import) or Filter (export)
            if arg_index == 3:
                options = []
                if subcmd in ["add", "import"]:
                    options = ["true", "false"]
                elif subcmd == "export":
                    options = ["all", "true", "false"]
                
                for o in options:
                    if o.startswith(current_word):
                        yield Completion(o, start_position=-len(current_word))

def create_completer(registry, bank=None):
    return ConsoleCompleter(registry, bank)
