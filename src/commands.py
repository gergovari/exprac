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
            # Optional: Feedback for unknown command
            pass
    
    def get_help_text(self) -> str:
        """Generates markdown help text from registered commands."""
        lines = ["# Help", ""]
        for cmd in self.commands.values():
            lines.append(f"- `{cmd.name}`: {cmd.description}")
        return "\n".join(lines)
