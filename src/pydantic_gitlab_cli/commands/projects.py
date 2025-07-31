"""Project-related commands."""

import typer
from rich.console import Console

console = Console()

projects_app = typer.Typer(
    name="projects",
    help="Manage GitLab projects",
)


@projects_app.command("list")
def list_projects() -> None:
    """List GitLab projects."""
    console.print("[bold green]Listing GitLab projects...[/bold green]")
    console.print("This command will list all accessible GitLab projects.")


@projects_app.command("info")
def project_info(project_id: int = typer.Argument(..., help="Project ID")) -> None:
    """Get information about a specific project."""
    console.print(f"[bold blue]Getting info for project ID: {project_id}[/bold blue]")
    console.print(f"This command will show details for project {project_id}.")


@projects_app.command("create")
def create_project(
    name: str = typer.Argument(..., help="Project name"),
    description: str = typer.Option("", "--description", "-d", help="Project description"),
) -> None:
    """Create a new GitLab project."""
    console.print(f"[bold yellow]Creating project: {name}[/bold yellow]")
    if description:
        console.print(f"Description: {description}")
    console.print("This command will create a new GitLab project.")
