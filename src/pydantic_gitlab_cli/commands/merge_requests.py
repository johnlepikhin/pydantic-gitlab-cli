"""Merge request-related commands."""

import typer
from rich.console import Console

console = Console()

mr_app = typer.Typer(
    name="mr",
    help="Manage GitLab merge requests",
)


@mr_app.command("list")
def list_merge_requests(
    project_id: int = typer.Option(..., "--project", "-p", help="Project ID"),
    state: str = typer.Option("opened", "--state", "-s", help="MR state (opened, closed, merged)"),
) -> None:
    """List merge requests in a project."""
    console.print(f"[bold green]Listing {state} merge requests for project {project_id}...[/bold green]")
    console.print(f"This command will list all {state} merge requests in project {project_id}.")


@mr_app.command("create")
def create_merge_request(
    project_id: int = typer.Option(..., "--project", "-p", help="Project ID"),
    title: str = typer.Argument(..., help="MR title"),
    source_branch: str = typer.Option(..., "--source", "-s", help="Source branch"),
    target_branch: str = typer.Option("main", "--target", "-t", help="Target branch"),
    description: str = typer.Option("", "--description", "-d", help="MR description"),
) -> None:
    """Create a new merge request."""
    console.print(f"[bold yellow]Creating merge request in project {project_id}[/bold yellow]")
    console.print(f"Title: {title}")
    console.print(f"Source: {source_branch} → Target: {target_branch}")
    if description:
        console.print(f"Description: {description}")
    console.print("This command will create a new merge request.")


@mr_app.command("merge")
def merge_request(
    project_id: int = typer.Option(..., "--project", "-p", help="Project ID"),
    mr_iid: int = typer.Argument(..., help="Merge request IID"),
) -> None:
    """Merge a merge request."""
    console.print(f"[bold green]Merging merge request {mr_iid} in project {project_id}[/bold green]")
    console.print(f"This command will merge MR !{mr_iid} in project {project_id}.")
