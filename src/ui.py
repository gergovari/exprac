import asyncio
import shlex
from abc import ABC, abstractmethod
from prompt_toolkit import Application
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.table import Table
from rich.text import Text
from src.logic import StatementChecker
from src.state import VerificationState
from src.commands import (
    CommandRegistry, QuitCommand, NextTabCommand, 
    PrevTabCommand, SwitchTabCommand, VerifyStatementCommand
)

class View(ABC):
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def render(self, console: Console) -> Any:
        pass

class VerificationView(View):
    def __init__(self, state: VerificationState):
        super().__init__("vs") # Main view name
        self.state = state
    
    def render(self, console: Console) -> Any:
        table = Table(box=None, padding=(0, 2), expand=True)
        table.add_column("Statement", style="cyan", ratio=3)
        table.add_column("Exact Match", style="magenta", ratio=1)
        table.add_column("Fuzzy Match", style="yellow", ratio=2)
        table.add_column("AI Knowledge", style="green", ratio=2)

        for item in self.state.items:
            table.add_row(
                item.statement,
                item.exact_status,
                Text(item.fuzzy_status), 
                Text(item.llm_status)
            )
        return table

class HelpView(View):
    def __init__(self, registry: CommandRegistry):
        super().__init__("help")
        self.registry = registry
    
    def render(self, console: Console) -> Any:
        from rich.markdown import Markdown
        return Markdown(self.registry.get_help_text())

class ViewManager:
    def __init__(self):
        self.views = []
        self.active_index = 0
    
    def add_view(self, view: View):
        self.views.append(view)
        
    def next_view(self):
        self.active_index = (self.active_index + 1) % len(self.views)
        
    def prev_view(self):
        self.active_index = (self.active_index - 1) % len(self.views)
        
    def switch_to(self, name: str) -> bool:
        for i, view in enumerate(self.views):
            if view.name == name:
                self.active_index = i
                return True
        return False
        
    def get_active(self) -> View:
        if not self.views: return None
        return self.views[self.active_index]

class App:
    def __init__(self):
        self.console = Console(force_terminal=True, highlight=False)
        self.state = VerificationState()
        self.checker = StatementChecker("data") 
        self.running = True
        
        # Command Registry
        self.registry = CommandRegistry()
        self.registry.register(QuitCommand())
        self.registry.register(NextTabCommand())
        self.registry.register(PrevTabCommand())
        self.registry.register(SwitchTabCommand())
        self.registry.register(VerifyStatementCommand())

        # View System
        self.view_manager = ViewManager()
        self.view_manager.add_view(VerificationView(self.state))
        self.view_manager.add_view(HelpView(self.registry))

        # Input buffer handling
        self.input_buffer = Buffer(multiline=False, accept_handler=self._handle_input)
        
        # Key bindings
        self.kb = KeyBindings()
        @self.kb.add("c-c")
        @self.kb.add("c-q")
        def _(event):
            event.app.exit()

        # Layout components
        self.output_control = FormattedTextControl(text=self._get_active_view_text)
        self.tab_bar_control = FormattedTextControl(text=self._get_tab_bar_text)
        
        self.layout = Layout(
            HSplit([
                Window(content=self.tab_bar_control, height=1), # Tab Bar at Top
                Window(content=self.output_control), # Main Content
                Window(height=1, char='-'),          # Context/Input Divider
                Window(content=BufferControl(buffer=self.input_buffer), height=1), # Input line
            ])
        )

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            mouse_support=False,
            refresh_interval=0.1
        )

    def _get_active_view_text(self):
        """Renders the current view using Rich + Capture."""
        view = self.view_manager.get_active()
        if not view: return ""
        
        renderable = view.render(self.console)
        
        with self.console.capture() as capture:
            self.console.print(renderable)
        
        return ANSI(capture.get())

    def _get_tab_bar_text(self):
        """Renders the tab bar line."""
        parts = []
        for i, view in enumerate(self.view_manager.views):
            name = view.name
            if i == self.view_manager.active_index:
                # ANSI Reverse Video for selected tab
                parts.append(f"\x1b[7m {name} \x1b[0m")
            else:
                parts.append(f" {name} ")
        return ANSI("".join(parts))

    def _handle_input(self, buff):
        text = buff.text.strip()
        if not text:
            return
        
        # Execute via registry
        # We spawn it as a task because execute is async and accept_handler can be sync/async,
        # but prompt_toolkit usually expects a boolean return or None. 
        # accept_handler can return True to keep buffer check? No.
        # It's best to run async command in background task.
        asyncio.create_task(self.registry.execute(text, self))

    async def process_new_item(self, stmt):
        item = await self.state.add_item(stmt)
        self.checker.run_all_checks(item, self.state)

    async def _refresh_loop(self):
        """Force UI refresh periodically."""
        while self.running:
            self.app.invalidate()
            await asyncio.sleep(0.1)

    async def run(self):
        # Start refresh loop in background
        refresh_task = asyncio.create_task(self._refresh_loop())
        try:
            await self.app.run_async()
        finally:
            self.running = False
            refresh_task.cancel()
