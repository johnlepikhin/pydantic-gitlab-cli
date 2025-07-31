"""List available lint rules command."""

import logging

import typer
from rich.console import Console
from rich.table import Table

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


def list_rules(
    category: str = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter rules by category (syntax, structure, security, quality, optimization, etc.)",
    ),
    enabled_only: bool = typer.Option(False, "--enabled-only", help="Show only enabled rules"),
) -> None:
    """List all available lint rules with descriptions."""

    # Get all available rules
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

    # Filter by category if specified
    if category:
        rules = [rule for rule in rules if rule.category.lower() == category.lower()]

    # Filter by enabled status if specified
    if enabled_only:
        rules = [rule for rule in rules if rule.enabled]

    # Sort rules by rule_id
    rules.sort(key=lambda x: x.rule_id)

    # Create table
    table = Table(title=f"Available Lint Rules{f' (Category: {category})' if category else ''}")
    table.add_column("Rule ID", style="cyan", no_wrap=True)
    table.add_column("Level", style="yellow", no_wrap=True)
    table.add_column("Category", style="green", no_wrap=True)
    table.add_column("Status", style="blue", no_wrap=True)
    table.add_column("Description", style="white")

    # Add rules to table
    for rule in rules:
        status = "✓ Enabled" if rule.enabled else "✗ Disabled"
        status_style = "green" if rule.enabled else "red"

        table.add_row(
            rule.rule_id,
            rule.level.value.upper(),
            rule.category,
            f"[{status_style}]{status}[/{status_style}]",
            rule.description,
        )

    # Display table
    console.print(table)

    # Show summary
    total_rules = len(rules)
    enabled_rules = sum(1 for rule in rules if rule.enabled)
    disabled_rules = total_rules - enabled_rules

    console.print()
    console.print(
        f"[bold]Summary:[/bold] {total_rules} rules total, "
        f"[green]{enabled_rules} enabled[/green], "
        f"[red]{disabled_rules} disabled[/red]"
    )

    # Show available categories
    if not category:
        categories = sorted({rule.category for rule in rules})
        console.print(f"[dim]Available categories: {', '.join(categories)}[/dim]")
        console.print("[dim]Use --category to filter by category[/dim]")

    logger.info("Listed %d lint rules", total_rules)
