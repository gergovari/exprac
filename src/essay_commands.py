from typing import Any, List
from prompt_toolkit.completion import Completion
import asyncio
from src.commands import Command
from src.essay_data import MaterialBank, EssayBank, EssaySession, EssayItem
from src.essay_logic import EssayGenerator

class MaterialBankCommand(Command):
    def __init__(self):
        super().__init__(":mb", "Manage Material Bank (PDFs/context). Usage: `:mb add <path>` | `:mb remove <id>`")

    def get_completions(self, completer: Any, text: str, args: List[str]):
        arg_index = len(args) - 1
        if arg_index == 0:
            for s in ["add", "remove"]:
                if s.startswith(text):
                    yield Completion(s, start_position=-len(text))
        elif arg_index == 1 and args[0] == "add":
            yield from completer.get_path_completions(text)

    async def execute(self, context: Any, args: List[str]):
        if not args:
            context.view_manager.switch_to("mb")
            return

        subcmd = args[0]
        if subcmd == "add":
            if len(args) < 2:
                context.show_message("Error", "Usage: :mb add <path>")
                return
            path = " ".join(args[1:])
            context.m_bank.add_item(path)
            context.show_message("Success", f"Added material: {path}")
            
        elif subcmd == "remove":
            if len(args) < 2: return
            try:
                mid = int(args[1])
                context.m_bank.remove_item(mid)
                context.show_message("Success", f"Removed material {mid}")
            except ValueError:
                context.show_message("Error", "Invalid ID")

class EssayBankCommand(Command):
    def __init__(self):
        super().__init__(":eb", "Manage Essay Bank (previous examples). Usage: `:eb import <csv>` | `:eb remove <id>`")

    def get_completions(self, completer: Any, text: str, args: List[str]):
        arg_index = len(args) - 1
        if arg_index == 0:
            for s in ["import", "remove"]:
                if s.startswith(text):
                    yield Completion(s, start_position=-len(text))
        elif arg_index == 1 and args[0] == "import":
            yield from completer.get_path_completions(text)

    async def execute(self, context: Any, args: List[str]):
        if not args:
            context.view_manager.switch_to("eb")
            return

        subcmd = args[0]
        if subcmd == "import":
            if len(args) < 2: return
            path = " ".join(args[1:])
            count = context.e_bank.import_from_file(path)
            context.show_message("Success", f"Imported {count} examples.")
            
        elif subcmd == "remove":
            if len(args) < 2: return
            try:
                eid = int(args[1])
                context.e_bank.remove_item(eid)
                context.show_message("Success", f"Removed example {eid}")
            except ValueError:
                context.show_message("Error", "Invalid ID")

class EssayWriterCommand(Command):
    def __init__(self):
        super().__init__(":ew", "Write AI Essays. Usage: `:ew <question>` | `:ew remove <id>`")

    def get_completions(self, completer: Any, text: str, args: List[str]):
        arg_index = len(args) - 1
        if arg_index == 0:
            if "remove".startswith(text):
                yield Completion("remove", start_position=-len(text))

    async def execute(self, context: Any, args: List[str]):
        if not args:
            context.view_manager.switch_to("ew")
            return


        if args[0] == "remove":
            if len(args) < 2:
                context.show_message("Error", "Usage: :ew remove <id>")
                return
            try:
                item_id = int(args[1])
                context.e_session.remove_item(item_id)
                context.show_message("Success", f"Removed essay query {item_id}")
            except ValueError:
                context.show_message("Error", "Invalid ID")
            return

        question = " ".join(args)
        
        # Add to session
        item = context.e_session.add_question(question)
        
        # Switch to view
        context.view_manager.switch_to("ew")
        
        # Trigger generation task
        def update_ui(msg=None):
            # Invalidate UI - basic way
            context.app.invalidate()
            
        if not context.essay_generator:
            context.show_message("Error", "Essay Generator is not configured (missing Gemini API key?).")
            return
            
        # Run in background
        asyncio.create_task(context.essay_generator.run(item, on_update=update_ui))
