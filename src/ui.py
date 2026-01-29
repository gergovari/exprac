import asyncio
import shlex
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.layout import Layout
from src.logic import StatementChecker

class App:
    def __init__(self):
        self.console = Console()
        # Initialize logic with data directory
        self.checker = StatementChecker("data") 
        self.session = PromptSession(vi_mode=True)

    def _create_table(self):
        table = Table(title="Verification Results")
        table.add_column("Statement", style="cyan")
        table.add_column("Exact Match", style="magenta")
        table.add_column("Fuzzy Match", style="yellow")
        table.add_column("AI Knowledge", style="green")
        return table

    async def handle_ft_command(self, args):
        if not args:
            self.console.print("[red]Usage: :ft <statement1> <statement2> ...[/red]")
            return

        # Initial table with spinners
        table = self._create_table()
        for stmt in args:
            table.add_row(stmt, Spinner("dots", text="Checking..."), Spinner("dots", text="Checking..."), Spinner("dots", text="Checking..."))

        with Live(table, refresh_per_second=10) as live:
            # Create tasks for each statement
            tasks = []
            for stmt in args:
                tasks.append(self.checker.verify_statement(stmt))
            
            # Wait for all results
            results_list = await asyncio.gather(*tasks)

            # Create a new table for results to avoid modifying the live one in-place dangerously
            new_table = self._create_table()
            
            for i, stmt in enumerate(args):
                res = results_list[i]
                r_exact = self._format_result(res[0])
                r_fuzzy = self._format_result(res[1])
                r_llm = self._format_result(res[2])
                new_table.add_row(stmt, r_exact, r_fuzzy, r_llm)
            
            live.update(new_table)

    def _format_result(self, res):
        if res['status'] == 'found':
            return f"[bold]{res['result']}[/bold] ({res.get('source')})"
        elif res['status'] == 'not_found':
            return "[dim]Not Found[/dim]"
        else:
            return "[red]Error[/red]"

    async def run(self):
        self.console.print("[bold green]Interactive Usage Console[/bold green]")
        self.console.print("Type ':ft \"stm1\" \"stm2\"' to verify statements.")
        self.console.print("Press Ctrl+C or type ':q' to exit.")

        while True:
            try:
                with patch_stdout():
                    text = await self.session.prompt_async("> ")

                if not text.strip():
                    continue

                if text.startswith(":"):
                    cmd_line = text[1:].strip()
                    parts = shlex.split(cmd_line)
                    if not parts:
                        continue
                    
                    cmd = parts[0]
                    args = parts[1:]

                    if cmd == "q":
                        break
                    elif cmd == "ft":
                        await self.handle_ft_command(args)
                    else:
                        self.console.print(f"[red]Unknown command: {cmd}[/red]")
                else:
                    self.console.print("[yellow]Commands must start with ':'[/yellow]")
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                import traceback
                traceback.print_exc()
