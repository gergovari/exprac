import asyncio
import shlex
from abc import ABC, abstractmethod
from prompt_toolkit import Application
from prompt_toolkit.layout.containers import HSplit, Window, FloatContainer, Float
from prompt_toolkit.widgets import Dialog, Label, Button
from src.bank import StatementBank
from typing import Any
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
    PrevTabCommand, SwitchTabCommand, VerifyStatementCommand,
    StatementBankCommand, SearchAliasCommand
)
from src.completer import create_completer

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
        table.add_column("AI (Bank)", style="yellow", ratio=2)
        table.add_column("AI (General)", style="green", ratio=2)

        for item in self.state.items:
            def make_cell(status, detail):
                t = Text()
                s_style = "white"
                st = str(status)
                if st.startswith("True"): s_style = "bright_green"
                elif st.startswith("False"): s_style = "bright_red"
                elif st == "Not Found": s_style = "dim"
                elif st.startswith("Error"): s_style = "red bold"
                
                t.append(st, style=s_style)
                if detail:
                    t.append("\n")
                    t.append(str(detail), style="dim italic grey70")
                return t

            table.add_row(
                item.statement,
                make_cell(item.exact_status, item.exact_detail),
                make_cell(item.fuzzy_status, item.fuzzy_detail),
                make_cell(item.llm_status, item.llm_detail)
            )
        return table

class StatementBankView(View):
    def __init__(self, bank: StatementBank):
        super().__init__("sb")
        self.bank = bank
        self.filter_modes = ["all", "true", "false"]
        self.current_filter_index = 0
        self.scroll_offset = 0
        self.current_filter_index = 0
        self.scroll_offset = 0
        self.search_query = ""

    def _get_page_size(self):
        import shutil
        height = shutil.get_terminal_size().lines
        # Overhead: Tabs(1)+Header(3)+Spacer(1)+Meta(1)+Status(1)+Input(1) = ~8. + Padding.
        return max(5, height - 10)

    @property
    def filter_mode(self):
        return self.filter_modes[self.current_filter_index]

    def set_filter(self, mode: str):
        if mode in self.filter_modes:
            self.current_filter_index = self.filter_modes.index(mode)
            self.scroll_offset = 0

    def cycle_filter(self, direction: int):
        self.current_filter_index = (self.current_filter_index + direction) % len(self.filter_modes)
        self.scroll_offset = 0

    def scroll(self, direction: int):
        items = self.bank.get_filtered(self.filter_mode, self.search_query)
        page_size = self._get_page_size()
        max_offset = max(0, len(items) - page_size)
        self.scroll_offset = max(0, min(max_offset, self.scroll_offset + direction))

    def render(self, console: Console) -> Any:
        # Header showing Tabs
        header_text = []
        for mode in self.filter_modes:
            label = mode.capitalize()
            if mode == self.filter_mode:
                header_text.append(f"\x1b[7m {label} \x1b[0m")
            else:
                header_text.append(f" {label} ")
        
        if self.search_query:
            header_text.append(f" \x1b[33mSearch: {self.search_query}\x1b[0m ")
        
        from rich.console import Group
        from rich.panel import Panel
        from rich.align import Align

        header_str = "".join(header_text)
        
        # Table
        table = Table(box=None, padding=(0, 2), expand=True)
        table.add_column("ID", style="cyan", justify="right", width=4)
        table.add_column("Statement", style="white", ratio=1)
        table.add_column("Truth", style="magenta", width=8, justify="center")

        all_items = self.bank.get_filtered(self.filter_mode, self.search_query)
        page_size = self._get_page_size()
        visible_items = all_items[self.scroll_offset : self.scroll_offset + page_size]
        
        import re
        for item in visible_items:
            truth_str = "True" if item.is_true else "False"
            style = "green" if item.is_true else "red"
            
            stmt_text = Text(item.text, style="white")
            if self.search_query:
                # Highlight the search query in the text
                # We use (?i) for case-insensitivity as Rich's API varies on flags arg
                stmt_text.highlight_regex(
                    "(?i)" + re.escape(self.search_query), 
                    style="bold black on yellow"
                )

            table.add_row(str(item.id), stmt_text, Text(truth_str, style=style))

        # Scroll Indicator (Simple text based)
        meta_text = f"Showing {len(visible_items)}/{len(all_items)} | Index {self.scroll_offset}"
        
        return Group(
            Align.center(Text.from_ansi(header_str)), 
            Text(""), # Spacer
            table,
            Text(""),
            Align.right(Text(meta_text, style="dim"))
        )



class HelpView(View):
    def __init__(self, registry: CommandRegistry):
        super().__init__("help")
        self.registry = registry
    
    def render(self, console: Console) -> Any:
        from rich.panel import Panel
        from rich.columns import Columns
        from rich.console import Group
        from rich.align import Align
        from rich.text import Text

        # Title
        title = Text("✨ Truth Verification Console Help ✨", style="bold magenta")
        
        # Interaction Guide
        nav_text = Text()
        nav_text.append("Normal Mode\n", style="bold cyan underline")
        nav_text.append("  TAB / S-TAB  ", style="yellow"); nav_text.append(": Switch View\n")
        nav_text.append("  :            ", style="yellow"); nav_text.append(": Enter Command Mode\n")
        nav_text.append("  Arrows       ", style="yellow"); nav_text.append(": Navigate Bank/List\n\n")
        
        nav_text.append("Command Mode\n", style="bold cyan underline")
        nav_text.append("  ESC          ", style="yellow"); nav_text.append(": Cancel / Return to Normal\n")
        nav_text.append("  ENTER        ", style="yellow"); nav_text.append(": Execute Command\n")
        
        nav_panel = Panel(nav_text, title="⌨️  Navigation & Keys", border_style="blue")
        
        # Commands List
        cmd_text = Text()
        for name, cmd in self.registry.commands.items():
            cmd_text.append(f"{name:<5} ", style="bold green")
            cmd_text.append(f"{cmd.description}\n")
            
        cmd_panel = Panel(cmd_text, title="🚀 Commands", border_style="green")
        
        # Bank Guide
        bank_text = Text()
        bank_text.append("Statement Bank Navigation\n", style="bold cyan underline")
        bank_text.append("  ← / →        ", style="yellow"); bank_text.append(": Cycle Filters (All/True/False)\n")
        bank_text.append("  ↑ / ↓        ", style="yellow"); bank_text.append(": Scroll List\n")
        
        bank_panel = Panel(bank_text, title="💾 Statement Bank", border_style="magenta")

        # Layout
        body = Columns([nav_panel, cmd_panel])
        
        return Group(
            Align.center(title),
            Text(""),
            body,
            bank_panel
        )

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
        self.bank = StatementBank("data/bank.csv") # Persist to disk
        self.checker = StatementChecker("data", bank=self.bank) 
        self.running = True
        
        # Command Registry
        self.registry = CommandRegistry()
        self.registry.register(QuitCommand())
        self.registry.register(NextTabCommand())
        self.registry.register(PrevTabCommand())
        self.registry.register(SwitchTabCommand())
        self.registry.register(VerifyStatementCommand())
        self.registry.register(StatementBankCommand())
        self.registry.register(SearchAliasCommand())

        # View System
        self.view_manager = ViewManager()
        self.view_manager.add_view(VerificationView(self.state))
        self.view_manager.add_view(StatementBankView(self.bank))
        self.view_manager.add_view(HelpView(self.registry))

        # Input buffer handling
        self.completer = create_completer(self.registry, self.bank)
        self.input_buffer = Buffer(
            multiline=False, 
            accept_handler=self._handle_input,
            completer=self.completer,
            complete_while_typing=False
        )
        
        from prompt_toolkit.filters import Condition

        # Key bindings
        self.kb = KeyBindings()

        @Condition
        def is_normal_mode_filter():
            try:
                return self.app.layout.has_focus(self.output_control)
            except:
                return False

        # Mode Switching
        # Mode Switching
        @self.kb.add(":")
        def _(event):
            if is_normal_mode_filter():
                self.app.layout.focus(self.input_buffer)
                self.input_buffer.text = ":"
                self.input_buffer.cursor_position = 1

        @self.kb.add("?")
        def _(event):
            if is_normal_mode_filter():
                self.app.layout.focus(self.input_buffer)
                self.input_buffer.text = "?"
                self.input_buffer.cursor_position = 1

        @self.kb.add("escape")
        def _(event):
            self.input_buffer.text = ""
            self.app.layout.focus(self.output_control)

        # Command Mode: Backspace to exit if empty
        @self.kb.add("backspace", filter=~is_normal_mode_filter)
        def _(event):
            buff = event.app.current_buffer
            
            # Perform standard backspace
            buff.delete_before_cursor(count=1)
            
            # If empty, exit to Normal Mode
            if len(buff.text) == 0:
                self.app.layout.focus(self.output_control)

        # Tab Navigation
        @self.kb.add("tab", filter=is_normal_mode_filter)
        def _(event):
            self.view_manager.next_view()

        @self.kb.add("s-tab", filter=is_normal_mode_filter)
        def _(event):
            self.view_manager.prev_view()

        # Arrow Navigation (Normal Mode Only)
        @self.kb.add("left", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, StatementBankView):
                view.cycle_filter(-1)
        
        @self.kb.add("right", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, StatementBankView):
                view.cycle_filter(1)

        @self.kb.add("up", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, StatementBankView):
                view.scroll(-1)

        @self.kb.add("down", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, StatementBankView):
                view.scroll(1)

        @self.kb.add("c-c")
        @self.kb.add("c-q")
        def _(event):
            event.app.exit()

        # Layout components
        self.output_control = FormattedTextControl(
            text=self._get_active_view_text,
            focusable=True, # Allow focus for Normal Mode
            show_cursor=False # Hide cursor in Normal Mode
        )
        self.tab_bar_control = FormattedTextControl(text=self._get_tab_bar_text)
        
        # Main body
        body = HSplit([
            Window(content=self.tab_bar_control, height=1), # Tab Bar at Top
            Window(content=self.output_control), # Main Content
            Window(content=FormattedTextControl(text=self._get_status_bar_text), height=1), # Status Bar
            Window(content=BufferControl(buffer=self.input_buffer), height=1), # Input line
        ])
        
        # Float container for popups
        self.root_container = FloatContainer(
            content=body,
            floats=[]
        )
        
        self.layout = Layout(self.root_container)

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            mouse_support=False,
            refresh_interval=0.1
        )
        # Start in Normal Mode
        self.layout.focus(self.output_control)

        # Status Bar State
        self.status_message = ""
        self.status_type = "info"
        self.clear_task = None

    def show_message(self, title: str, text: str):
        """Display a message in the status bar."""
        self.status_type = "error" if title.lower() == "error" else "info"
        self.status_message = f"{title}: {text}" if title.lower() == "error" else text
        
        if self.clear_task:
            self.clear_task.cancel()
        
        async def clear():
            await asyncio.sleep(5)
            self.status_message = ""
            self.app.invalidate()
            
        self.clear_task = asyncio.create_task(clear())
        self.app.invalidate()

    def _get_status_bar_text(self):
        """Render the status bar."""
        is_command = False
        try:
            is_command = self.app.layout.has_focus(self.input_buffer)
        except: pass
        
        mode = " COMMAND " if is_command else " NORMAL "
        mode_style = "reverse"
        
        parts = [
            (mode_style, mode),
            ("", " ")
        ]
        
        if self.status_message:
            msg_style = "#ff0000" if self.status_type == "error" else "#00ff00"
            parts.append((msg_style, self.status_message))
            
        return parts

    def _get_active_view_text(self):
        """Renders the current view using Rich + Capture."""
        view = self.view_manager.get_active()
        if not view: return ""
        
        # Sync width to ensure expand=True works
        import shutil
        self.console.width = shutil.get_terminal_size().columns
        
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
        # Always return focus to Normal Mode after execution try
        self.app.layout.focus(self.output_control)
        
        if not text:
            return
        
        # Execute via registry
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
