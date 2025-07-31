"""Check command for GitLab CI YAML validation."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from pydantic_gitlab_cli.linter import LintEngine, LintLevel
from pydantic_gitlab_cli.linter.base import LintResult
from pydantic_gitlab_cli.linter.formatters import formatter_registry
from pydantic_gitlab_cli.linter.rules import (
    AllowFailureValidityRule,
    ArtifactsExpirationRule,
    CachePolicyRule,
    CacheRule,
    CiDebugTraceRule,
    DockerImageSizeRule,
    DockerLatestTagRule,
    GeneralPackageManagerCacheRule,
    GoCacheRule,
    IncludeVersioningRule,
    InterruptibleFailFastRule,
    JavaCacheRule,
    JobDependenciesRule,
    JobNamingRule,
    JobReuseRule,
    KeyOrderRule,
    LintStageRule,
    NodeCacheRule,
    PackageInstallationRule,
    ParallelizationRule,
    ParallelMatrixLimitRule,
    ProtectedContextRule,
    PythonCacheRule,
    ResourceMonitoringRule,
    ReviewAppsRule,
    RulesOptimizationRule,
    RustCacheRule,
    SecretsInCodeRule,
    StagesCompletenessRule,
    StagesStructureRule,
    TimeoutOptimizationRule,
    VariableOptimizationRule,
    YamlSyntaxRule,
)

console = Console()
logger = logging.getLogger(__name__)

# Define typer arguments at module level to avoid B008
FILES_ARGUMENT = typer.Argument(help="GitLab CI YAML files to check")


def check(
    files: list[Path] = FILES_ARGUMENT,
    strict: bool = typer.Option(
        False,
        "--strict",
        "-s",
        help="Enable strict validation mode",
    ),
    output_format: str = typer.Option(
        "console",
        "--format",
        "-f",
        help="Output format (console, json, sarif, junit)",
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    fail_on_warnings: bool = typer.Option(
        False,
        "--fail-on-warnings",
        help="Exit with error code on warnings",
    ),
    output_file: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to file instead of stdout",
    ),
) -> None:
    """Perform static checks on GitLab CI YAML files."""
    console.print(f"[bold green]Checking {len(files)} GitLab CI YAML file(s)...[/bold green]")

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if strict else logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Initialize lint engine with configuration
    engine = LintEngine(config=config)

    # Override config with CLI options
    if fail_on_warnings:
        engine.config.fail_on_warnings = True

    # Register rules
    rules = [
        # Syntax and structure rules
        YamlSyntaxRule(),
        StagesStructureRule(),
        JobDependenciesRule(),
        IncludeVersioningRule(),
        # Docker rules
        DockerLatestTagRule(),
        DockerImageSizeRule(),
        # Quality rules
        PackageInstallationRule(),
        KeyOrderRule(),
        CacheRule(),
        ArtifactsExpirationRule(),
        InterruptibleFailFastRule(),
        # Optimization rules
        VariableOptimizationRule(),
        ParallelizationRule(),
        ParallelMatrixLimitRule(),
        TimeoutOptimizationRule(),
        JobReuseRule(),
        CachePolicyRule(),
        LintStageRule(),
        # Security rules
        SecretsInCodeRule(),
        ProtectedContextRule(),
        CiDebugTraceRule(),
        # Naming rules
        JobNamingRule(),
        # Review and advanced rules
        ReviewAppsRule(),
        StagesCompletenessRule(),
        AllowFailureValidityRule(),
        RulesOptimizationRule(),
        ResourceMonitoringRule(),
        # Cache optimization rules
        PythonCacheRule(),
        NodeCacheRule(),
        RustCacheRule(),
        GoCacheRule(),
        JavaCacheRule(),
        GeneralPackageManagerCacheRule(),
    ]
    engine.register_rules(rules)

    console.print(f"[dim]Registered {len(rules)} lint rules[/dim]")

    # Lint files
    results = engine.lint_files(files, strict=strict)

    # Display results based on format
    if output_format == "console":
        _display_console_results(results)
    else:
        formatter = formatter_registry.get_formatter(output_format)
        if formatter:
            output = formatter.format(results)

            # Write to file or stdout
            if output_file:
                try:
                    with Path(output_file).open("w", encoding="utf-8") as f:
                        f.write(output)
                    console.print(f"[green]Results written to {output_file}[/green]")
                except Exception as e:
                    console.print(f"[red]Failed to write to {output_file}: {e}[/red]")
                    raise typer.Exit(1) from e
            else:
                console.print(output)
        else:
            available_formats = ", ".join(["console", *formatter_registry.list_formats()])
            console.print(f"[bold red]Unknown output format: {output_format}[/bold red]")
            console.print(f"Available formats: {available_formats}")
            raise typer.Exit(1)

    # Exit with error code based on configuration
    if engine.should_fail(results):
        raise typer.Exit(1)


def _display_file_result(result: LintResult) -> None:
    """Display a single file's lint results in cargo-style format."""
    if result.parse_error:
        console.print(f"[bold red]error[/bold red]: failed to parse {result.file_path}")
        console.print(f"  [dim]-->[/dim] {result.parse_error}")
        console.print()
        return

    if result.violations:
        # Show each violation in cargo style
        for violation in result.violations:
            level_color = {LintLevel.ERROR: "red", LintLevel.WARNING: "yellow", LintLevel.INFO: "blue"}.get(
                violation.level, "white"
            )

            level_name = violation.level.value.lower()

            # Location info
            location_info = str(result.file_path)
            if violation.line is not None:
                location_info += f":{violation.line}"
                if violation.column is not None:
                    location_info += f":{violation.column}"

            # Main violation message (cargo-style)
            console.print(
                f"[bold {level_color}]{level_name}[/bold {level_color}][[{violation.rule_id}]]: {violation.message}"
            )
            console.print(f"  [dim]-->[/dim] {location_info}")

            # Add suggestion if available
            if violation.suggestion:
                console.print(f"  [dim]help:[/dim] {violation.suggestion}")

            console.print()


def _display_summary(total_files: int, total_errors: int, total_warnings: int, total_info: int) -> None:
    """Display summary statistics in cargo-style format."""
    # Summary line in cargo style
    summary_parts = []

    if total_errors > 0:
        summary_parts.append(f"[bold red]{total_errors} error{'s' if total_errors != 1 else ''}[/bold red]")

    if total_warnings > 0:
        summary_parts.append(f"[bold yellow]{total_warnings} warning{'s' if total_warnings != 1 else ''}[/bold yellow]")

    if total_info > 0:
        summary_parts.append(f"[bold blue]{total_info} info[/bold blue]")

    if summary_parts:
        console.print("  " + ", ".join(summary_parts) + f" in {total_files} file{'s' if total_files != 1 else ''}")
    # All clean
    elif total_files > 0:
        console.print(
            f"  [green]✓[/green] {total_files} file{'s' if total_files != 1 else ''} checked, no issues found"
        )
    else:
        console.print("  [dim]No files to check[/dim]")


def _display_console_results(results: list[LintResult]) -> None:
    """Display results in console format (cargo-style)."""
    total_files = len(results)
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_info = sum(r.info_count for r in results)

    console.print()

    # Display violations for each file
    for result in results:
        _display_file_result(result)

    # Display summary
    _display_summary(total_files, total_errors, total_warnings, total_info)
