"""Rich console logging utilities for agent reasoning output."""

from rich.console import Console
from rich.panel import Panel

console = Console()


def log(message: str):
    console.log(message)


def log_panel(content: str, title: str = ""):
    console.print(Panel(content, title=title, border_style="blue"))
