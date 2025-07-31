"""Cache optimization rules for package managers."""

from __future__ import annotations

import logging
import re

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintLevel, LintRule

logger = logging.getLogger(__name__)


class PackageManagerCacheRule(LintRule):
    """Base class for package manager cache optimization rules."""

    def __init__(self, enabled: bool = True, level: LintLevel = LintLevel.WARNING):
        super().__init__(enabled=enabled, level=level)
        # Define package manager patterns - subclasses should override
        self.install_patterns = []
        self.cache_paths = []
        self.package_manager_name = "unknown"

    @property
    def category(self) -> str:
        return "cache_optimization"

    def _extract_script_commands(self, job) -> list[str]:
        """Extract all script commands from a job."""
        commands = []

        # Extract from script
        if hasattr(job, "script") and job.script:
            if isinstance(job.script, list):
                commands.extend(job.script)
            elif isinstance(job.script, str):
                commands.append(job.script)

        # Extract from before_script
        if hasattr(job, "before_script") and job.before_script:
            if isinstance(job.before_script, list):
                commands.extend(job.before_script)
            elif isinstance(job.before_script, str):
                commands.append(job.before_script)

        # Extract from after_script
        if hasattr(job, "after_script") and job.after_script:
            if isinstance(job.after_script, list):
                commands.extend(job.after_script)
            elif isinstance(job.after_script, str):
                commands.append(job.after_script)

        return commands

    def _has_install_commands(self, commands: list[str]) -> list[str]:
        """Check if commands contain package installation commands."""
        found_commands = []

        for command in commands:
            if isinstance(command, str):
                # Check each install pattern
                for pattern in self.install_patterns:
                    if re.search(pattern, command, re.IGNORECASE):
                        found_commands.append(command.strip())
                        break

        return found_commands

    def _extract_cache_paths(self, cache_config) -> list[str]:
        """Extract cache paths from cache configuration."""
        cache_paths = []

        if isinstance(cache_config, list):
            # Multiple cache configurations
            for cache_item in cache_config:
                if isinstance(cache_item, dict):
                    paths = cache_item.get("paths", [])
                    if isinstance(paths, list):
                        cache_paths.extend(paths)
                elif hasattr(cache_item, "paths") and cache_item.paths and isinstance(cache_item.paths, list):
                    cache_paths.extend(cache_item.paths)
        elif isinstance(cache_config, dict):
            # Single cache configuration
            paths = cache_config.get("paths", [])
            if isinstance(paths, list):
                cache_paths.extend(paths)
        elif hasattr(cache_config, "paths") and cache_config.paths and isinstance(cache_config.paths, list):
            # Pydantic model
            cache_paths.extend(cache_config.paths)

        return cache_paths

    def _is_relevant_cache(self, cache_paths: list[str]) -> bool:
        """Check if cache paths match expected patterns."""
        for expected_path in self.cache_paths:
            for actual_path in cache_paths:
                if expected_path in actual_path or actual_path in expected_path:
                    return True
        return False

    def _has_appropriate_cache(self, job) -> tuple[bool, list[str]]:
        """Check if job has appropriate cache configuration."""
        if not hasattr(job, "cache") or not job.cache:
            return False, []

        cache_paths = self._extract_cache_paths(job.cache)
        has_relevant_cache = self._is_relevant_cache(cache_paths)

        return has_relevant_cache, cache_paths

    def check(self, ci_config: GitLabCI, result) -> None:
        """Check for package manager usage without appropriate caching."""
        try:
            if not ci_config.jobs:
                return

            for job_name, job in ci_config.jobs.items():
                # Skip template jobs
                if job_name.startswith("."):
                    continue

                # Extract script commands
                commands = self._extract_script_commands(job)
                if not commands:
                    continue

                # Check for package installation commands
                install_commands = self._has_install_commands(commands)
                if not install_commands:
                    continue

                # Check if appropriate cache is configured
                has_cache, current_cache_paths = self._has_appropriate_cache(job)

                if not has_cache:
                    # Create suggestion for cache configuration
                    suggested_paths = ", ".join([f'"{path}"' for path in self.cache_paths[:3]])  # Show first 3 paths
                    suggestion = f"Add cache configuration: cache: {{ paths: [{suggested_paths}] }}"

                    self.add_violation(
                        result=result,
                        message=f"Job uses {self.package_manager_name} commands but lacks appropriate caching",
                        job_name=job_name,
                        suggestion=suggestion,
                    )

        except Exception as e:
            logger.error("Error checking %s cache optimization: %s", self.rule_id, e)


class PythonCacheRule(PackageManagerCacheRule):
    """GL027: Python pip cache optimization."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.WARNING)
        self.install_patterns = [
            r"\bpip\s+install\b",
            r"\bpip3\s+install\b",
            r"\bpython\s+-m\s+pip\s+install\b",
            r"\bpython3\s+-m\s+pip\s+install\b",
        ]
        self.cache_paths = [
            "~/.cache/pip",
            "/root/.cache/pip",
            "pip-cache/",
            ".pip-cache/",
        ]
        self.package_manager_name = "pip"

    @property
    def rule_id(self) -> str:
        return "GL027"

    @property
    def description(self) -> str:
        return "Python pip installations should use cache optimization"


class NodeCacheRule(PackageManagerCacheRule):
    """GL028: Node.js npm/yarn cache optimization."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.WARNING)
        self.install_patterns = [
            r"\bnpm\s+install\b",
            r"\bnpm\s+ci\b",
            r"\byarn\s+install\b",
            r"\byarn\s+--frozen-lockfile\b",
            r"\byarn\s+--production\b",
        ]
        self.cache_paths = [
            "node_modules/",
            "~/.npm",
            "~/.yarn/cache",
            ".npm/",
            ".yarn/cache/",
        ]
        self.package_manager_name = "npm/yarn"

    @property
    def rule_id(self) -> str:
        return "GL028"

    @property
    def description(self) -> str:
        return "Node.js npm/yarn installations should use cache optimization"


class RustCacheRule(PackageManagerCacheRule):
    """GL029: Rust cargo cache optimization."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.WARNING)
        self.install_patterns = [
            r"\bcargo\s+build\b",
            r"\bcargo\s+test\b",
            r"\bcargo\s+install\b",
            r"\bcargo\s+check\b",
            r"\bcargo\s+run\b",
        ]
        self.cache_paths = [
            "target/",
            "~/.cargo/registry",
            "~/.cargo/git",
            ".cargo/",
        ]
        self.package_manager_name = "cargo"

    @property
    def rule_id(self) -> str:
        return "GL029"

    @property
    def description(self) -> str:
        return "Rust cargo builds should use cache optimization"


class GoCacheRule(PackageManagerCacheRule):
    """GL030: Go module cache optimization."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.WARNING)
        self.install_patterns = [
            r"\bgo\s+build\b",
            r"\bgo\s+mod\s+download\b",
            r"\bgo\s+get\b",
            r"\bgo\s+install\b",
            r"\bgo\s+test\b",
        ]
        self.cache_paths = [
            "~/go/pkg/mod",
            "~/.cache/go-build",
            "/go/pkg/mod",
            ".go-cache/",
        ]
        self.package_manager_name = "go"

    @property
    def rule_id(self) -> str:
        return "GL030"

    @property
    def description(self) -> str:
        return "Go builds should use module cache optimization"


class JavaCacheRule(PackageManagerCacheRule):
    """GL031: Java Maven/Gradle cache optimization."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.WARNING)
        self.install_patterns = [
            r"\bmvn\s+install\b",
            r"\bmvn\s+compile\b",
            r"\bmvn\s+package\b",
            r"\bgradle\s+build\b",
            r"\bgradle\s+assemble\b",
            r"\.\/gradlew\s+build\b",
            r"\.\/gradlew\s+assemble\b",
        ]
        self.cache_paths = [
            "~/.m2/repository",
            "~/.gradle/caches",
            ".m2/",
            ".gradle/",
        ]
        self.package_manager_name = "Maven/Gradle"

    @property
    def rule_id(self) -> str:
        return "GL031"

    @property
    def description(self) -> str:
        return "Java Maven/Gradle builds should use cache optimization"


class GeneralPackageManagerCacheRule(LintRule):
    """GL032: General package manager cache detection."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.INFO)

        # Common package manager patterns not covered by specific rules
        self.install_patterns = [
            # PHP
            r"\bcomposer\s+install\b",
            r"\bcomposer\s+update\b",
            # Ruby
            r"\bbundle\s+install\b",
            r"\bgem\s+install\b",
            # .NET
            r"\bdotnet\s+restore\b",
            r"\bnuget\s+install\b",
            # APT/YUM (system packages)
            r"\bapt-get\s+install\b",
            r"\bapt\s+install\b",
            r"\byum\s+install\b",
            r"\bdnf\s+install\b",
            # Alpine
            r"\bapk\s+add\b",
        ]

    @property
    def rule_id(self) -> str:
        return "GL032"

    @property
    def description(self) -> str:
        return "Consider caching for package manager operations"

    @property
    def category(self) -> str:
        return "cache_optimization"

    def _should_skip_job(self, job_name: str, job) -> bool:
        """Check if job should be skipped from caching analysis."""
        # Skip template jobs
        if job_name.startswith("."):
            return True

        # Skip if already has cache configured
        return hasattr(job, "cache") and job.cache

    def _extract_job_commands(self, job) -> list[str]:
        """Extract all commands from job scripts."""
        commands = []

        # Extract script commands
        if hasattr(job, "script") and job.script:
            if isinstance(job.script, list):
                commands.extend(job.script)
            elif isinstance(job.script, str):
                commands.append(job.script)

        if hasattr(job, "before_script") and job.before_script:
            if isinstance(job.before_script, list):
                commands.extend(job.before_script)
            elif isinstance(job.before_script, str):
                commands.append(job.before_script)

        return commands

    def _check_job_for_caching_opportunities(self, job_name: str, job, result) -> None:
        """Check a single job for caching opportunities."""
        if self._should_skip_job(job_name, job):
            return

        commands = self._extract_job_commands(job)

        # Check for package manager commands
        found_commands = []
        for command in commands:
            if isinstance(command, str):
                for pattern in self.install_patterns:
                    if re.search(pattern, command, re.IGNORECASE):
                        found_commands.append(command.strip())
                        break

        if found_commands:
            # Determine likely cache paths based on detected commands
            suggestions = []
            if any("composer" in cmd for cmd in found_commands):
                suggestions.append("Consider caching vendor/ directory for Composer")
            if any("bundle" in cmd or "gem" in cmd for cmd in found_commands):
                suggestions.append("Consider caching ~/.gem or vendor/bundle for Ruby")
            if any("dotnet" in cmd or "nuget" in cmd for cmd in found_commands):
                suggestions.append("Consider caching ~/.nuget/packages for .NET")
            if any(pm in cmd for cmd in found_commands for pm in ["apt-get", "apt", "yum", "dnf", "apk"]):
                suggestions.append("Consider using pre-built Docker images instead of installing system packages")

            suggestion = (
                "; ".join(suggestions)
                if suggestions
                else "Consider adding cache configuration for package dependencies"
            )

            self.add_violation(
                result=result,
                message="Job uses package manager commands that could benefit from caching",
                job_name=job_name,
                suggestion=suggestion,
            )

    def check(self, ci_config: GitLabCI, result) -> None:
        """Check for package manager usage without appropriate caching."""
        try:
            if not ci_config.jobs:
                return

            for job_name, job in ci_config.jobs.items():
                self._check_job_for_caching_opportunities(job_name, job, result)

        except Exception as e:
            logger.error("Error checking GL032 (GeneralPackageManagerCache): %s", e)
