from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
import shlex

class ConsoleCompleter(Completer):
    def __init__(self, registry):
        self.registry = registry
        # expanduser=True allows ~/paths
        self.path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        parts = text.split(' ')
        
        # Current word is the last part
        current_word = parts[-1]
        
        # Determine argument index being typed
        # Note: split(' ') on "cmd " gives ['cmd', '']. Index is 1. Correct.
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
                subcmds = ["add", "remove", "import", "export", "true", "false", "all"]
                for s in subcmds:
                    if s.startswith(current_word):
                        yield Completion(s, start_position=-len(current_word))
                return
            
            subcmd = parts[1]
            
            # Arg 2: File Path (import/export)
            if arg_index == 2:
                if subcmd in ["import", "export"]:
                    # Isolate the path for the completer by creating a dummy document
                    # This ensures PathCompleter sees only "data/tr" not ":sb import data/tr"
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

def create_completer(registry):
    return ConsoleCompleter(registry)
