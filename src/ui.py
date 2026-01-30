import asyncio
import shlex
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

class App:
    def __init__(self):
        self.console = Console(force_terminal=True, highlight=False)
        self.state = VerificationState()
        self.checker = StatementChecker("data") 
        self.running = True

        # Input buffer handling
        self.input_buffer = Buffer(multiline=False, accept_handler=self._handle_input)
        
        # Key bindings
        self.kb = KeyBindings()
        @self.kb.add("c-c")
        @self.kb.add("c-q")
        def _(event):
            event.app.exit()

        # Layout components
        self.output_control = FormattedTextControl(text=self._get_table_text)
        
        self.layout = Layout(
            HSplit([
                Window(content=self.output_control), # Takes remaining height
                Window(height=1, char='-'),          # Divider
                Window(content=BufferControl(buffer=self.input_buffer), height=1), # Input line
            ])
        )

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            mouse_support=False,
            refresh_interval=0.1 # 10FPS refresh for spinners?
        )

    def _get_table_text(self):
        """Generates the main table content."""
        table = Table(box=None, padding=(0, 2), expand=True)
        table.add_column("Statement", style="cyan", ratio=3)
        table.add_column("Exact Match", style="magenta", ratio=1)
        table.add_column("Fuzzy Match", style="yellow", ratio=2)
        table.add_column("AI Knowledge", style="green", ratio=2)

        for item in self.state.items:
            table.add_row(
                item.statement,
                item.exact_status,
                Text(item.fuzzy_status), # Use Text to allow simple markup if needed
                Text(item.llm_status)
            )

        with self.console.capture() as capture:
            self.console.print(table)
        
        return ANSI(capture.get())

    def _handle_input(self, buff):
        text = buff.text.strip()
        if not text:
            return

        if text == ":q":
            self.app.exit()
            return

        if text.startswith(":ft "):
            cmd_line = text[1:].strip()
            parts = shlex.split(cmd_line)
            args = parts[1:]
            
            for stmt in args:
                # Add item to state synchronously (to show up immediately)
                task = asyncio.create_task(self._process_new_item(stmt))
            
        elif text.startswith(":"):
             # Show error somehow? For now just ignore non-ft commands
             pass

    async def _process_new_item(self, stmt):
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
