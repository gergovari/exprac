import asyncio
import shlex
import os
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
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.table import Table
from rich.text import Text
from src.logic import StatementChecker
from src.manager import ProviderManager
from src.state import VerifierState
from src.commands import (
    CommandRegistry, QuitCommand, NextTabCommand, 
    PrevTabCommand, SwitchTabCommand, VerifierCommand,
    StatementBankCommand, SearchAliasCommand, 
    VerifyDotAliasCommand, ForwardSearchAliasCommand
)
from src.completer import create_completer
from src.essay_data import MaterialBank, EssayBank, EssaySession
from src.essay_logic import EssayGenerator
from src.essay_commands import MaterialBankCommand, EssayBankCommand, EssayWriterCommand

class View(ABC):
    use_cursor = False
    def __init__(self, name: str, title: str = None):
        self.name = name
        self.title = title or name
    
    @abstractmethod
    def render(self, console: Console) -> Any:
        pass

    def handle_enter(self, app: Any):
        """Handle Enter key press."""
        pass

class ScrollableListView(View):
    def __init__(self, name: str, title: str):
        super().__init__(name, title)
        self.scroll_offset = 0
        self.selected_index = 0

    def _get_page_size(self):
        import shutil
        return max(5, shutil.get_terminal_size().lines - 9)

    def get_items(self) -> list:
        return []

    def move_selection(self, delta: int):
        items = self.get_items()
        if not items: return
        
        total = len(items)
        self.selected_index = max(0, min(total - 1, self.selected_index + delta))
        
        page_size = self._get_page_size()
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + page_size:
            self.scroll_offset = max(0, self.selected_index - page_size + 1)

    def scroll(self, direction: int):
        items = self.get_items()
        page_size = self._get_page_size()
        max_offset = max(0, len(items) - page_size)
        self.scroll_offset = max(0, min(max_offset, self.scroll_offset + direction))

    def render_footer(self, total: int, visible: int):
        from rich.align import Align
        from rich.text import Text
        txt = f"Showing {visible}/{total} | Index {self.scroll_offset}"
        return Align.right(Text(txt, style="dim"))

class VerifierView(ScrollableListView):
    def __init__(self, state: VerifierState):
        super().__init__("sv", "✅ Verify")
        self.state = state
    
    def get_items(self) -> list:
        return self.state.items

    def render(self, console: Console) -> Any:
        from rich.console import Group
        from rich.align import Align
        
        header = Text(" Verification Queue ", style="reverse bold magenta")

        table = Table(box=None, padding=(0, 2), expand=True)
        table.add_column("ID", style="cyan", width=4, justify="right")
        table.add_column("Statement", style="cyan", ratio=3)
        table.add_column("Exact Match", style="magenta", ratio=1)
        table.add_column("AI (Bank)", style="yellow", ratio=2)
        table.add_column("AI (General)", style="green", ratio=2)

        all_items = self.state.items
        page_size = self._get_page_size()
        visible_items = all_items[self.scroll_offset : self.scroll_offset + page_size]

        for i, item in enumerate(visible_items):
            def make_cell(status, detail):
                t = Text()
                s_style = "white"
                st = str(status)
                if st.startswith("True"): s_style = "bright_green"
                elif st.startswith("False"): s_style = "bright_red"
                elif st == "Pending": s_style = "dim yellow"
                elif st == "Not Found": s_style = "dim"
                elif st.startswith("Error"): s_style = "red bold"
                elif st == "Checking...": s_style = "blue blink"
                
                t.append(st, style=s_style)
                if detail:
                    t.append(" | ")
                    t.append(str(detail), style="dim italic grey70")
                return t

            table.add_row(
                str(item.id),
                item.statement,
                make_cell(item.exact_status, item.exact_detail),
                make_cell(item.fuzzy_status, item.fuzzy_detail),
                make_cell(item.llm_status, item.llm_detail)
            )
        
        return Group(
            Align.center(header),
            Text(""), 
            table,
            Text(""),
            self.render_footer(len(all_items), len(visible_items))
        )

class StatementBankView(ScrollableListView):
    def __init__(self, bank: StatementBank):
        super().__init__("sb", "📚 Bank")
        self.bank = bank
        self.filter_modes = ["all", "true", "false"]
        self.current_filter_index = 0
        self.search_query = ""

    def get_items(self) -> list:
        return self.bank.get_filtered(self.filter_mode, self.search_query)

    @property
    def filter_mode(self):
        return self.filter_modes[self.current_filter_index]

    def set_filter(self, mode: str):
        if mode in self.filter_modes:
            self.current_filter_index = self.filter_modes.index(mode)
            self.scroll_offset = 0
            self.selected_index = 0

    def cycle_filter(self, direction: int):
        self.current_filter_index = (self.current_filter_index + direction) % len(self.filter_modes)
        self.scroll_offset = 0
        self.selected_index = 0

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
        for i, item in enumerate(visible_items):
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

        return Group(
            Align.center(Text.from_ansi(header_str)), 
            Text(""), # Spacer
            table,
            Text(""),
            self.render_footer(len(all_items), len(visible_items))
        )



class HelpView(View):
    def __init__(self, registry: CommandRegistry):
        super().__init__("help", "ℹ️  Help")
        self.registry = registry
    
    def render(self, console: Console) -> Any:
        from rich.panel import Panel
        from rich.columns import Columns
        from rich.console import Group
        from rich.align import Align
        from rich.text import Text
        from rich.table import Table
        from rich import box

        # Title
        title = Text("✨ Truth Verification Console Help ✨", style="bold magenta")
        
        # 1. Navigation (Left Panel)
        nav_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        nav_table.add_column("Key", style="yellow bold", width=12)
        nav_table.add_column("Action", style="white")
        
        nav_table.add_row("TAB / S-TAB", "Switch Tab")
        nav_table.add_row(":", "Enter Command Mode")
        nav_table.add_row("ESC", "Exit / Clear Input")
        nav_table.add_row("Arrows", "Navigate Lists")
        nav_table.add_row("hjkl", "Vim Navigation")
        nav_table.add_row("PgUp/Dn", "Scroll Page")
        nav_table.add_row("Home/End", "Scroll Top/Bot")
        
        nav_panel = Panel(nav_table, title="⌨️  Navigation", border_style="blue", expand=True)
        
        # 2. Quick Actions (Right Panel)
        alias_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        alias_table.add_column("Key", style="yellow bold", width=12)
        alias_table.add_column("Action", style="white")
        
        alias_table.add_row(". <stmt>...", "Verify statement(s)")
        alias_table.add_row("/ <query>", "Search Statement Bank")
        alias_table.add_row("? <query>", "Search Statement Bank")
        
        # Spacer for alignment
        alias_table.add_row("", "") 
        
        alias_panel = Panel(alias_table, title="⚡ Quick Actions (Aliases)", border_style="cyan", expand=True)

        # 3. Commands Detail
        cmd_text = Text()
        
        # Legend
        cmd_text.append("Syntax: ", style="bold")
        cmd_text.append("<required> ", style="cyan"); cmd_text.append("[optional]\n\n", style="dim cyan")
        
        cmd_text.append("Core Commands:\n", style="bold underline")
        cmd_text.append("  :vs <text>...   ", style="green"); cmd_text.append("Verify one or more statements (space separated)\n")
        cmd_text.append("  :vs remove <id> ", style="green"); cmd_text.append("Remove item from verification queue\n")
        cmd_text.append("  :vs retry <id>  ", style="green"); cmd_text.append("Retry verification for specific item\n\n")
        
        cmd_text.append("Statement Bank:\n", style="bold underline")
        cmd_text.append("  :sb add <txt> <t/f>   ", style="green"); cmd_text.append("Add statement to bank\n")
        cmd_text.append("  :sb remove <id>       ", style="green"); cmd_text.append("Remove statement from bank\n")
        cmd_text.append("  :sb search <query>    ", style="green"); cmd_text.append("Filter bank entries\n")
        cmd_text.append("  :sb import <file> [t] ", style="green"); cmd_text.append("Import lines (optional default truth)\n")
        cmd_text.append("  :sb export <file>     ", style="green"); cmd_text.append("Export bank to file\n\n")

        cmd_text.append("System:\n", style="bold underline")
        cmd_text.append("  :bn / :bp   ", style="green"); cmd_text.append("Next / Previous Tab\n")
        cmd_text.append("  :b <name>   ", style="green"); cmd_text.append("Switch tab by name (vs, sb, help)\n")
        cmd_text.append("  :q          ", style="green"); cmd_text.append("Quit application")

        cmd_panel = Panel(cmd_text, title="🚀 Command Reference", border_style="green", expand=True)

        # 4. Glossary
        glossary_text = Text()
        glossary_text.append("Statement Bank: ", style="bold yellow"); glossary_text.append("Local database of known truths/falsehoods.\n")
        glossary_text.append("Exact Match:    ", style="bold yellow"); glossary_text.append("Verifies against Bank using precise text.\n")
        glossary_text.append("AI (Bank):      ", style="bold yellow"); glossary_text.append("Infers truth from Bank using AI logic (Fuzzy).\n")
        glossary_text.append("AI (General):   ", style="bold yellow"); glossary_text.append("Uses AI's world knowledge to verify facts.\n")
        
        glossary_panel = Panel(glossary_text, title="📖 Glossary", border_style="white", expand=True)
        
        # Layout
        top_row = Columns([nav_panel, alias_panel], expand=True)
        
        return Group(
            Align.center(title),
            Text(""),
            top_row,
            cmd_panel,
            glossary_panel
        )

class MaterialBankView(ScrollableListView):
    def __init__(self, bank: MaterialBank):
        super().__init__("mb", "📂 Materials")
        self.bank = bank

    def get_items(self) -> list:
        return self.bank.items

    def render(self, console: Console) -> Any:
        from rich.console import Group
        from rich.table import Table
        from rich.text import Text
        
        header = Text(" PDF Materials (for Essay Context) ", style="reverse bold blue")
        
        table = Table(box=None, padding=(0, 2), expand=True)
        table.add_column("ID", style="cyan", width=4, justify="right")
        table.add_column("Path", style="yellow")
        
        items = self.bank.items
        page_size = self._get_page_size()
        visible = items[self.scroll_offset : self.scroll_offset + page_size]
        
        for i, item in enumerate(visible):
            table.add_row(str(item.id), item.path)
            
        return Group(header, Text(""), table, Text(""), self.render_footer(len(items), len(visible)))

class EssayBankView(ScrollableListView):
    use_cursor = True
    def __init__(self, bank: EssayBank):
        super().__init__("eb", "📚 Examples")
        self.bank = bank

    def get_items(self) -> list:
        return self.bank.examples

    def handle_enter(self, app: Any):
        items = self.bank.examples
        if not items: return
        idx = self.selected_index
        if 0 <= idx < len(items):
            item = items[idx]
            app.show_dialog("Example Detail", f"Q: {item.question}\n\nA:\n{item.answer}")

    def render(self, console: Console) -> Any:
        from rich.console import Group
        from rich.table import Table
        from rich.text import Text
        
        header = Text(" Essay Style Examples (Few-Shot) ", style="reverse bold green")
        
        table = Table(box=None, padding=(0, 2), expand=True)
        table.add_column("ID", style="cyan", width=4, justify="right")
        table.add_column("Question", style="white", ratio=1)
        table.add_column("Answer Snippet", style="dim white", ratio=2)
        
        items = self.bank.examples
        page_size = self._get_page_size()
        visible = items[self.scroll_offset : self.scroll_offset + page_size]
        
        for i, item in enumerate(visible):
            snippet = (item.answer[:50] + "...") if len(item.answer) > 50 else item.answer
            
            style = "reverse" if (i + self.scroll_offset == self.selected_index) else ""
            table.add_row(str(item.id), item.question, snippet, style=style)
            
        return Group(header, Text(""), table, Text(""), self.render_footer(len(items), len(visible)))

class EssayWriterView(ScrollableListView):
    use_cursor = True
    def __init__(self, session: EssaySession):
        super().__init__("ew", "✍️  Writer")
        self.session = session

    def get_items(self) -> list:
        return self.session.items

    def handle_enter(self, app: Any):
        items = self.session.items
        if not items: return
        idx = self.selected_index
        if 0 <= idx < len(items):
            item = items[idx]
            app.show_dialog("Essay Detail", f"Q: {item.question}\n\nA:\n{item.answer or 'Generating...'}")

    def render(self, console: Console) -> Any:
        from rich.console import Group
        from rich.table import Table
        from rich.text import Text
        
        header = Text(" Essay Generator ", style="reverse bold magenta")
        
        table = Table(box=None, padding=(0, 2), expand=True, show_header=True)
        table.add_column("ID", style="cyan", width=4, justify="right")
        table.add_column("Question", style="white", ratio=2)
        table.add_column("Status", style="yellow", ratio=2)
        table.add_column("Answer Snippet", style="dim white", ratio=1)
        
        items = self.session.items
        
        page_size = self._get_page_size()
        visible = items[self.scroll_offset : self.scroll_offset + page_size]
        
        for i, item in enumerate(visible):
            status_style = "dim"
            if item.status == "Generating...": status_style = "blue blink"
            elif item.status == "Uploading...": status_style = "yellow blink"
            elif item.status == "Done": status_style = "green"
            elif item.status.startswith("Error"): status_style = "red"
            
            ans = item.answer or ""
            snippet = (ans[:60] + "...") if len(ans) > 60 else ans
            
            row_style = "reverse" if (i + self.scroll_offset == self.selected_index) else ""
            table.add_row(
                str(item.id), 
                item.question, 
                Text(item.status, style=status_style), 
                snippet, 
                style=row_style
            )
            
        return Group(header, Text(""), table, Text(""), self.render_footer(len(items), len(visible)))

class ViewManager:
    def __init__(self):
        self.groups = {
            "Statements": [],
            "Essays": [],
            "Help": []
        }
        self.views = []
        self.active_index = 0
    
    def add_view(self, view: View, group: str = "Statements"):
        self.views.append(view)
        if group not in self.groups:
            self.groups[group] = []
        self.groups[group].append(view)
        
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
    def __init__(self, config: dict = None, api_keys: dict = None):
        self.console = Console(force_terminal=True, highlight=False)
        self.config = config or {}
        self.data_path = self.config.get("data_path", "data")
        
        # Ensure data dir exists
        os.makedirs(self.data_path, exist_ok=True)
        
        # 1. Manager (with keys)
        self.manager = ProviderManager(config_path="config.yaml", api_keys=api_keys)
        
        # 2. SV Components
        self.state = VerifierState(os.path.join(self.data_path, "sv_history.json"))
        self.bank = StatementBank(os.path.join(self.data_path, "bank.csv")) 
        self.checker = StatementChecker(self.data_path, bank=self.bank, manager=self.manager) 
        
        # 3. Essay Components
        self.m_bank = MaterialBank(os.path.join(self.data_path, "materials.json"))
        self.e_bank = EssayBank(os.path.join(self.data_path, "essay_examples.csv"))
        self.e_session = EssaySession(os.path.join(self.data_path, "essay_history.json"))
        
        # Generator
        gemini = self.manager.get_provider("gemini")
        if not gemini and self.manager.providers: 
             gemini = self.manager.providers[0] # Fallback
        self.essay_generator = EssayGenerator(self.manager, self.m_bank, self.e_bank, self.e_session)

        self.running = True
        
        # Command Registry
        self.registry = CommandRegistry()
        self.registry.register(QuitCommand())
        self.registry.register(NextTabCommand())
        self.registry.register(PrevTabCommand())
        self.registry.register(SwitchTabCommand())
        self.registry.register(VerifierCommand())
        self.registry.register(StatementBankCommand())
        self.registry.register(SearchAliasCommand())
        self.registry.register(VerifyDotAliasCommand())
        self.registry.register(ForwardSearchAliasCommand())
        # Essay Commands
        self.registry.register(MaterialBankCommand())
        self.registry.register(EssayBankCommand())
        self.registry.register(EssayWriterCommand())

        # View System
        self.view_manager = ViewManager()
        self.view_manager.add_view(VerifierView(self.state), "Statements")
        self.view_manager.add_view(StatementBankView(self.bank), "Statements")
        self.view_manager.add_view(EssayWriterView(self.e_session), "Essays")
        self.view_manager.add_view(MaterialBankView(self.m_bank), "Essays")
        self.view_manager.add_view(EssayBankView(self.e_bank), "Essays")
        self.view_manager.add_view(HelpView(self.registry), "Help")

        # Smart View Selection (Startup)
        if self.state.items:
            self.view_manager.switch_to("sv")
        elif self.bank.statements:
            self.view_manager.switch_to("sb")
        else:
            self.view_manager.switch_to("help")

        # Input buffer handling
        self.completer = create_completer(self.registry, self.bank)
        self.input_buffer = Buffer(
            multiline=False, 
            accept_handler=self._handle_input,
            completer=self.completer,
            complete_while_typing=False,
            history=FileHistory('data/command_history')
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
        @self.kb.add(":", filter=is_normal_mode_filter)
        def _(event):
            self.app.layout.focus(self.input_buffer)
            self.input_buffer.text = ":"
            self.input_buffer.cursor_position = 1

        @self.kb.add("?", filter=is_normal_mode_filter)
        def _(event):
            self.app.layout.focus(self.input_buffer)
            self.input_buffer.text = "?"
            self.input_buffer.cursor_position = 1

        @self.kb.add("/", filter=is_normal_mode_filter)
        def _(event):
            self.app.layout.focus(self.input_buffer)
            self.input_buffer.text = "/"
            self.input_buffer.cursor_position = 1

        @self.kb.add(".", filter=is_normal_mode_filter)
        def _(event):
            self.app.layout.focus(self.input_buffer)
            self.input_buffer.text = "."
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

        @self.kb.add("enter", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if view:
                view.handle_enter(self)

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
            if isinstance(view, ScrollableListView):
                if view.use_cursor:
                    view.move_selection(-1)
                else:
                    view.scroll(-1)

        @self.kb.add("down", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, ScrollableListView):
                if view.use_cursor:
                    view.move_selection(1)
                else:
                    view.scroll(1)

        # Vim Navigation (h, j, k, l)
        @self.kb.add("h", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, StatementBankView):
                view.cycle_filter(-1)
        
        @self.kb.add("l", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, StatementBankView):
                view.cycle_filter(1)

        @self.kb.add("k", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, ScrollableListView):
                if view.use_cursor:
                    view.move_selection(-1)
                else:
                    view.scroll(-1)

        @self.kb.add("j", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, ScrollableListView):
                if view.use_cursor:
                    view.move_selection(1)
                else:
                    view.scroll(1)

        @self.kb.add("pageup", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, ScrollableListView):
                 if view.use_cursor:
                    view.move_selection(-5)
                 else:
                    view.scroll(-5)

        @self.kb.add("pagedown", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, ScrollableListView):
                 if view.use_cursor:
                    view.move_selection(5)
                 else:
                    view.scroll(5)

        @self.kb.add("home", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, ScrollableListView):
                if view.use_cursor:
                    view.move_selection(-999999)
                else:
                    view.scroll(-999999)

        @self.kb.add("end", filter=is_normal_mode_filter)
        def _(event):
            view = self.view_manager.get_active()
            if isinstance(view, ScrollableListView):
                if view.use_cursor:
                    view.move_selection(999999)
                else:
                    view.scroll(999999)

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

    def show_dialog(self, title: str, text: str):
        from prompt_toolkit.widgets import Dialog, Button
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.containers import Float
        
        def close():
            if self.root_container.floats:
                self.root_container.floats.pop()
            self.app.layout.focus(self.output_control)
            self.app.invalidate()

        close_btn = Button(text="Close", handler=close)

        dialog = Float(content=Dialog(
            title=title,
            body=Window(FormattedTextControl(text), wrap_lines=True),
            buttons=[close_btn],
            modal=True,
            width=80
        ))
        
        self.root_container.floats.append(dialog)
        self.app.layout.focus(close_btn)
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
        """Renders the current view with a stable localized console to avoid output corruption."""
        try:
            view = self.view_manager.get_active()
            if not view: return ""
            
            import shutil
            from io import StringIO
            from rich.console import Console as RichConsole
            
            # Use a fresh StringIO and fixed-width console for THIS render
            # This prevents state leakage and ensures prompt_toolkit gets a clean string
            cols = shutil.get_terminal_size().columns
            out = StringIO()
            temp_console = RichConsole(file=out, width=cols, force_terminal=True, highlight=False, color_system="auto")
            
            renderable = view.render(temp_console)
            temp_console.print(renderable)
            
            return ANSI(out.getvalue())
        except Exception as e:
            return ANSI(f"\x1b[31mRender Error in {view.name if 'view' in locals() else 'unknown'}: {str(e)}\x1b[0m")

    def _get_tab_bar_text(self):
        """Renders the tab bar line cleanly with groups."""
        parts = []
        for group_name, views in self.view_manager.groups.items():
            if not views: continue
            
            # Restore Group Header
            parts.append(f" [{group_name}] ")
            
            for view in views:
                active = (view == self.view_manager.get_active())
                name = view.title
                if active:
                    parts.append(f" \x1b[7m {name} \x1b[0m ")
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
        item, is_new = await self.state.add_item(stmt)
        if is_new:
            self.checker.run_all_checks(item, self.state)
        # Else: Just focused (moved to end), no checks rerun.
    
    async def process_retry_item(self, item_id: int):
        # Find item
        item = next((i for i in self.state.items if i.id == item_id), None)
        if not item:
            self.show_message("Error", f"Item {item_id} not found.")
            return

        # Reset statuses
        item.exact_status = "Pending"
        item.fuzzy_status = "Pending"
        item.llm_status = "Pending"
        item.exact_detail = None
        item.fuzzy_detail = None
        item.llm_detail = None
        
        self.state.update_item(item)
        self.checker.run_all_checks(item, self.state)
        self.show_message("Success", f"Retrying verification for {item_id}.")

    async def _refresh_loop(self):
        """Force UI refresh periodically."""
        while self.running:
            self.app.invalidate()
            await asyncio.sleep(0.1)

    def resume_pending(self):
        """Resumes pending verifications on startup."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return 

        count = 0
        # Verifications
        for item in self.state.items:
            resumed = False
            # Exact
            if str(item.exact_status) in ["Pending", "Checking..."]:
                loop.create_task(self.checker.run_exact_check(item, self.state))
                resumed = True
            
            # Fuzzy
            s = str(item.fuzzy_status)
            if s in ["Pending", "Checking..."] or s.startswith("Rate") or s.startswith("Error") or s.startswith("Retry"):
                loop.create_task(self.checker.run_fuzzy_check(item, self.state))
                resumed = True

            # LLM
            s = str(item.llm_status)
            if s in ["Pending", "Checking..."] or s.startswith("Rate") or s.startswith("Error") or s.startswith("Retry"):
                 loop.create_task(self.checker.run_llm_check(item, self.state))
                 resumed = True
                
            if resumed: count += 1

        # Essays
        def update_ui(msg=None):
            self.app.invalidate()

        for item in self.e_session.items:
            s = str(item.status)
            if s in ["Pending", "Starting...", "Uploading...", "Generating..."] or s.startswith("Rate"):
                loop.create_task(self.essay_generator.run(item, on_update=update_ui))
                count += 1
            
        if count > 0:
            self.show_message("Info", f"Resumed {count} pending tasks.")

    async def run(self):
        # Resume pending items
        self.resume_pending()

        # Start refresh loop in background
        refresh_task = asyncio.create_task(self._refresh_loop())
        try:
            await self.app.run_async()
        finally:
            self.running = False
            refresh_task.cancel()
