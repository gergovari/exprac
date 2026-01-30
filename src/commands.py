from abc import ABC, abstractmethod
from typing import List, Any
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

class VerifyStatementCommand(Command):
    def __init__(self):
        super().__init__(":vs", "Verify statements. Usage: :vs \"stmt1\" \"stmt2\"")

    async def execute(self, context: Any, args: List[str]):
        # Ensure we are on the verification tab
        context.view_manager.switch_to("vs")
        
        for stmt in args:
            if stmt:
                # We assume context (App) has a method to process items
                # We'll need to expose `process_new_item` in App
                await context.process_new_item(stmt)

class StatementBankCommand(Command):
    def __init__(self):
        super().__init__(":sb", "Statement Bank. Usage: :sb [add|remove|import|export|all|true|false]")

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

            elif subcmd == "export":
                if len(args) < 2: raise ValueError("Usage: :sb export <file> [filter]")
                path = args[1]
                filter_type = args[2] if len(args) > 2 else "all"
                count = context.bank.export_to_file(path, filter_type)
                context.show_message("Success", f"Exported {count} items.")
                
        except Exception as e:
            context.show_message("Error", str(e))

class CommandRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, command: Command):
        self.commands[command.name] = command

    async def execute(self, text: str, context: Any):
        text = text.strip()
        if not text: return

        try:
            parts = shlex.split(text)
        except ValueError:
            # Fallback for unclosed quote or parsing error
            # Attempt to split by first space (simple command parsing)
            parts = text.split(" ", 1)
        
        if not parts: return
        
        cmd_name = parts[0]
        args = parts[1:]

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
