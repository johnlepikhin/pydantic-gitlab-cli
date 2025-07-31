"""Issue-related commands."""

import typer
from rich.console import Console

console = Console()

issues_app = typer.Typer(
    name="issues",
    help="Manage GitLab issues",
)


@issues_app.command("list")
def list_issues(
    project_id: int = typer.Option(..., "--project", "-p", help="Project ID"),
    state: str = typer.Option("opened", "--state", "-s", help="Issue state (opened, closed)"),
) -> None:
    """List issues in a project."""
    console.print(f"[bold green]Listing {state} issues for project {project_id}...[/bold green]")
    console.print(f"This command will list all {state} issues in project {project_id}.")


@issues_app.command("create")
def create_issue(
    project_id: int = typer.Option(..., "--project", "-p", help="Project ID"),
    title: str = typer.Argument(..., help="Issue title"),
    description: str = typer.Option("", "--description", "-d", help="Issue description"),
) -> None:
    """Create a new issue."""
    console.print(f"[bold yellow]Creating issue in project {project_id}[/bold yellow]")
    console.print(f"Title: {title}")
    if description:
        console.print(f"Description: {description}")
    console.print("This command will create a new issue in the specified project.")


@issues_app.command("close")
def close_issue(
    project_id: int = typer.Option(..., "--project", "-p", help="Project ID"),
    issue_iid: int = typer.Argument(..., help="Issue IID"),
) -> None:
    """Close an issue."""
    console.print(f"[bold red]Closing issue {issue_iid} in project {project_id}[/bold red]")
    console.print(f"This command will close issue #{issue_iid} in project {project_id}.")
