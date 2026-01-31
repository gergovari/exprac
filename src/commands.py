from abc import ABC, abstractmethod
from typing import List, Any
from prompt_toolkit.completion import Completion
import shlex
import asyncio

class Command(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, context: Any, args: List[str]):
        """
        Executes the command.
        :param context: The App instance.
        :param args: List of arguments passed to the command.
        """
        pass

    def get_completions(self, completer: Any, text: str, args: List[str]):
        """Yields completions for arguments."""
        return []

class QuitCommand(Command):
    def __init__(self):
        super().__init__(":q", "Quit the application")

    async def execute(self, context: Any, args: List[str]):
        context.app.exit()

class NextTabCommand(Command):
    def __init__(self):
        super().__init__(":bn", "Switch to next tab")

    async def execute(self, context: Any, args: List[str]):
        context.view_manager.next_view()

class PrevTabCommand(Command):
    def __init__(self):
        super().__init__(":bp", "Switch to previous tab")

    async def execute(self, context: Any, args: List[str]):
        context.view_manager.prev_view()

class SwitchTabCommand(Command):
    def __init__(self):
        super().__init__(":b", "Switch to tab by name. Usage: :b <name>")

    async def execute(self, context: Any, args: List[str]):
        if not args: return
        context.view_manager.switch_to(args[0])

class VerifierCommand(Command):
    def __init__(self):
        super().__init__(":sv", "Verify statements. Usage: :sv \"stmt1\" | :sv remove <id> | :sv retry <id>")

    def get_completions(self, completer: Any, text: str, args: List[str]):
        arg_index = len(args) - 1
        
        if arg_index == 0:
            subcmds = ["remove", "retry", "clear"]
            for s in subcmds:
                if s.startswith(text):
                    yield Completion(s, start_position=-len(text))
            
            # Also yield bank completions for statement verification
            yield from completer.get_bank_completions(text)

    async def execute(self, context: Any, args: List[str]):
        # Check for subcommands
        # Check for subcommands
        if args and args[0] == "remove":
            # Usage: :sv remove <id>
            if len(args) < 2:
                context.show_message("Error", "Usage: :sv remove <id>")
                return
            try:
                sid = int(args[1])
                await context.state.remove_item(sid)
                context.show_message("Success", f"Item {sid} removed.")
            except ValueError:
                context.show_message("Error", "Invalid ID.")
            return

        elif args and args[0] == "clear":
            await context.state.clear()
            context.show_message("Success", "Verification queue cleared.")
            return

        elif args and args[0] == "retry":
            # Usage: :sv retry <id>
            if len(args) < 2:
                context.show_message("Error", "Usage: :sv retry <id>")
                return
            try:
                sid = int(args[1])
                # context is App instance
                await context.process_retry_item(sid)
            except ValueError:
                context.show_message("Error", "Invalid ID.")
            return

        # Normal verification flow
        context.view_manager.switch_to("sv")
        
        for stmt in args:
            if stmt:
                # We assume context (App) has a method to process items
                # We'll need to expose `process_new_item` in App
                await context.process_new_item(stmt)
        
        # Autoscroll to bottom
        vs_view = None
        for v in context.view_manager.views:
            if v.name == "sv":
                vs_view = v
                break
        if vs_view:
            vs_view.scroll(99999)

class StatementBankCommand(Command):
    def __init__(self):
        super().__init__(":sb", "Statement Bank. Usage: :sb [add|remove|import|export|all|true|false]")

    def get_completions(self, completer: Any, text: str, args: List[str]):
        arg_index = len(args) - 1
        
        if arg_index == 0:
            subcmds = ["add", "remove", "import", "export", "true", "false", "all", "search"]
            for s in subcmds:
                if s.startswith(text):
                    yield Completion(s, start_position=-len(text))
            return
            
        subcmd = args[0]
        
        if arg_index == 1:
            if subcmd in ["import", "export"]:
                yield from completer.get_path_completions(text)
                
        if arg_index == 2:
            options = []
            if subcmd in ["add", "import"]: options = ["true", "false"]
            elif subcmd == "export": options = ["all", "true", "false"]
            
            for o in options:
                if o.startswith(text):
                    yield Completion(o, start_position=-len(text))

    async def execute(self, context: Any, args: List[str]):
        # Switch to tab first
        context.view_manager.switch_to("sb")
        
        if not args:
            return

        subcmd = args[0].lower()
        


        # Operations
        try:
            if subcmd == "add":
                # args: add "text" true
                if len(args) < 3:
                     raise ValueError("Usage: :sb add 'text' true/false")
                text = args[1]
                is_true = args[2].lower() in ('true', '1', 'yes', 't')
                is_true = args[2].lower() in ('true', '1', 'yes', 't')
                if context.bank.add(text, is_true):
                    context.show_message("Success", f"Statement added.")
                else:
                    context.show_message("Info", f"Ignored duplicate statement.")
            
            elif subcmd == "remove":
                if len(args) < 2: raise ValueError("Usage: :sb remove <id>")
                sid = int(args[1])
                if context.bank.remove(sid):
                    context.show_message("Success", f"Statement {sid} removed.")
                else:
                    context.show_message("Error", f"ID {sid} not found.")

            elif subcmd == "import":
                if len(args) < 2: raise ValueError("Usage: :sb import <file> [default_truth]")
                path = args[1]
                default_truth = None
                if len(args) > 2:
                    default_truth = args[2].lower() in ('true', '1', 'yes', 't')
                
                if len(args) > 2:
                    default_truth = args[2].lower() in ('true', '1', 'yes', 't')
                
                count, dups = context.bank.import_from_file(path, default_truth)
                msg = f"Imported {count} items."
                if dups > 0:
                    msg += f" Ignored {dups} duplicates."
                context.show_message("Success", msg)

            elif subcmd == "search":
                # :sb search "query" or :sb search query words
                query = " ".join(args[1:]) if len(args) > 1 else ""
                
                # Find the view to update state
                sb_view = None
                for v in context.view_manager.views:
                    if v.name == "sb":
                        sb_view = v
                        break
                
                if sb_view:
                    sb_view.search_query = query
                    sb_view.scroll_offset = 0 
                    status = f"Filter set: {query}" if query else "Filter cleared"
                    context.show_message("Info", status)

            elif subcmd == "export":
                if len(args) < 2: raise ValueError("Usage: :sb export <file> [filter]")
                path = args[1]
                filter_type = args[2] if len(args) > 2 else "all"
                count = context.bank.export_to_file(path, filter_type)
                context.show_message("Success", f"Exported {count} items.")
                
        except Exception as e:
            context.show_message("Error", str(e))

class VerifyDotAliasCommand(Command):
    def __init__(self):
        super().__init__(".", "Verify statements. Alias for :sv.")

    async def execute(self, context: Any, args: List[str]):
        # Switch to sv view
        context.view_manager.switch_to("sv")
        
        if not args:
            context.show_message("Error", "No statements provided.")
            return

        count = 0
        for stmt in args:
            if stmt.strip():
                await context.process_new_item(stmt)
                count += 1
                
        context.show_message("Info", f"Added {count} statement(s).")
            
        # Autoscroll
        vs_view = None
        for v in context.view_manager.views:
            if v.name == "sv":
                vs_view = v
                break
        if vs_view:
             vs_view.scroll(99999)

class SearchAliasCommand(Command):
    def __init__(self):
        super().__init__("?", "Search Statement Bank. Alias for :sb search.")

    async def execute(self, context: Any, args: List[str]):
        # Switch to sb view
        context.view_manager.switch_to("sb")
        
        query = " ".join(args)
        
        # Find view
        sb_view = None
        for v in context.view_manager.views:
            if v.name == "sb":
                sb_view = v
                break
        
        if sb_view:
            sb_view.search_query = query
            sb_view.scroll_offset = 0 
            status = f"Filter set: {query}" if query else "Filter cleared"
            context.show_message("Info", status)

class ForwardSearchAliasCommand(Command):
    def __init__(self):
        super().__init__("/", "Search Statement Bank. Alias for :sb search.")

    async def execute(self, context: Any, args: List[str]):
        # Switch to sb view
        context.view_manager.switch_to("sb")
        
        query = " ".join(args)
        
        # Find view
        sb_view = None
        for v in context.view_manager.views:
            if v.name == "sb":
                sb_view = v
                break
        
        if sb_view:
            sb_view.search_query = query
            sb_view.scroll_offset = 0 
            status = f"Filter set: {query}" if query else "Filter cleared"
            context.show_message("Info", status)

class CommandRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, command: Command):
        self.commands[command.name] = command

    async def execute(self, text: str, context: Any):
        text = text.strip()
        if not text: return
        
        # Special handling for aliases ?, /, .
        # Special handling for aliases ?, /, .
        if text.startswith("?") or text.startswith("/") or text.startswith("."):
            cmd_name = text[0]
            rest = text[1:].strip()
            args = []
            if rest:
                # Smart parsing for . (Verify) to support multiple quoted args
                if cmd_name == "." and ('"' in rest or "'" in rest):
                    try:
                        args = shlex.split(rest)
                    except ValueError:
                        args = [rest]
                else:
                    args = [rest]

            if cmd_name in self.commands:
                await self.commands[cmd_name].execute(context, args)
            return

        try:
            parts = shlex.split(text)
        except ValueError:
            # Fallback for unclosed quote or parsing error
            parts = text.split(" ", 1)
        
        if not parts: return
        
        cmd_name = parts[0]
        args = parts[1:]

        # SMART PARSING LIMITATION:
        # For verification/writing commands, we prefer "whole sentence" interpretation 
        # if the user didn't explicitly quote.
        smart_commands = [":sv", ":ew", ":vs"]
        
        # Exception: if it looks like a subcommand (remove/retry) for :sv/:vs, don't smart parse
        is_subcommand = False
        if cmd_name in [":sv", ":vs", ":ew"]:
             if text.startswith(f"{cmd_name} remove") or text.startswith(f"{cmd_name} retry"):
                 is_subcommand = True

        if cmd_name in smart_commands and ('"' not in text and "'" not in text) and not is_subcommand:
             raw_parts = text.split(None, 1)
             if len(raw_parts) > 1:
                 args = [raw_parts[1]]

        if cmd_name in self.commands:
            await self.commands[cmd_name].execute(context, args)
        else:
            # Feedback for unknown command - use show_message now!
            if hasattr(context, "show_message"):
                context.show_message("Error", f"Unknown command: {cmd_name}")
    
    def get_help_text(self) -> str:
        """Generates markdown help text from registered commands."""
        lines = ["# Help", ""]
        for cmd in self.commands.values():
            lines.append(f"- `{cmd.name}`: {cmd.description}")
        return "\n".join(lines)
