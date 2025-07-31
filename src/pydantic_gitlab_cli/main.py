"""Main CLI application entry point."""

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .commands.check import check
from .commands.init_config import init_config
from .commands.issues import issues_app
from .commands.list_rules import list_rules
from .commands.merge_requests import mr_app
from .commands.projects import projects_app

app = typer.Typer(
    name="pydantic-gitlab-cli",
    help="GitLab CI/CD configuration linter and analyzer",
    add_completion=False,
)

app.add_typer(projects_app)
app.add_typer(issues_app)
app.add_typer(mr_app)
app.command()(check)
app.command(name="init-config")(init_config)
app.command(name="list-rules")(list_rules)

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"pydantic-gitlab-cli version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """GitLab CI/CD configuration linter and analyzer with comprehensive rule checking."""
    pass


@app.command()
def info() -> None:
    """Show information about the CLI tool."""
    table = Table(title="GitLab CI/CD Linter Info")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Version", __version__)
    table.add_row("Description", "GitLab CI/CD configuration linter and analyzer")
    table.add_row("Python Package", "pydantic-gitlab-cli")
    table.add_row("Author", "Evgenii Lepikhin")
    table.add_row("Email", "johnlepikhin@gmail.com")

    console.print(table)


if __name__ == "__main__":
    app()
