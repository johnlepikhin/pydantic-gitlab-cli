"""Init config command for generating default configuration."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from pydantic_gitlab_cli.linter.config import create_default_config

console = Console()
logger = logging.getLogger(__name__)


def init_config(
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for config file (default: .gitlab-ci-lint.yml)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing config file",
    ),
) -> None:
    """Generate a default configuration file."""

    # Determine output path
    config_path = Path(output) if output else Path.cwd() / ".gitlab-ci-lint.yml"

    # Check if file already exists
    if config_path.exists() and not force:
        console.print(f"[red]Configuration file already exists: {config_path}[/red]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    try:
        # Generate default configuration
        config_content = create_default_config()

        # Write to file
        with config_path.open("w", encoding="utf-8") as f:
            f.write(config_content)

        console.print(f"[green]✓[/green] Created configuration file: {config_path}")
        console.print("\n[dim]You can now customize the configuration to fit your needs.[/dim]")
        console.print("[dim]Run the linter with: pydantic-gitlab-cli check <files>[/dim]")

    except Exception as e:
        console.print(f"[red]Failed to create configuration file: {e}[/red]")
        raise typer.Exit(1) from e
