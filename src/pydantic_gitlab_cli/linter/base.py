"""Base classes for GitLab CI linting."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from pydantic import BaseModel
from pydantic_gitlab import GitLabCI

logger = logging.getLogger(__name__)


class LintLevel(str, Enum):
    """Lint violation severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LintViolation(BaseModel):
    """A single linting violation."""

    rule_id: str
    level: LintLevel
    message: str
    file_path: Path | None = None
    line: int | None = None
    column: int | None = None
    job_name: str | None = None
    suggestion: str | None = None

    def __str__(self) -> str:
        """String representation of violation."""
        location_parts = []
        if self.file_path:
            location_parts.append(str(self.file_path))
        if self.line is not None:
            location_parts.append(f"line {self.line}")
        if self.column is not None:
            location_parts.append(f"col {self.column}")
        if self.job_name:
            location_parts.append(f"job '{self.job_name}'")

        location = ":".join(location_parts) if location_parts else "unknown"
        return f"[{self.level.value}] {self.rule_id}: {self.message} ({location})"


class LintResult(BaseModel):
    """Result of linting a single file."""

    file_path: Path
    violations: list[LintViolation] = []
    parse_error: str | None = None

    @property
    def error_count(self) -> int:
        """Count of error-level violations."""
        return len([v for v in self.violations if v.level == LintLevel.ERROR])

    @property
    def warning_count(self) -> int:
        """Count of warning-level violations."""
        return len([v for v in self.violations if v.level == LintLevel.WARNING])

    @property
    def info_count(self) -> int:
        """Count of info-level violations."""
        return len([v for v in self.violations if v.level == LintLevel.INFO])

    @property
    def has_errors(self) -> bool:
        """True if there are any error-level violations."""
        return self.error_count > 0

    def add_violation(
        self,
        rule_id: str,
        level: LintLevel,
        message: str,
        line: int | None = None,
        column: int | None = None,
        job_name: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        """Add a violation to the result."""
        violation = LintViolation(
            rule_id=rule_id,
            level=level,
            message=message,
            file_path=self.file_path,
            line=line,
            column=column,
            job_name=job_name,
            suggestion=suggestion,
        )
        self.violations.append(violation)

        logger.debug(
            "Added violation: %s [%s] %s",
            rule_id,
            level.value,
            message,
            extra={
                "rule_id": rule_id,
                "level": level.value,
                "file_path": str(self.file_path),
                "job_name": job_name,
            },
        )


class LintRule(ABC):
    """Abstract base class for lint rules."""

    def __init__(self, enabled: bool = True, level: LintLevel = LintLevel.ERROR):
        """Initialize rule."""
        self.enabled = enabled
        self.level = level
        logger.debug("Initialized rule %s: enabled=%s, level=%s", self.rule_id, enabled, level.value)

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this rule checks."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """Category this rule belongs to (syntax, structure, security, etc.)."""
        pass

    @abstractmethod
    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """
        Check the GitLab CI configuration for violations of this rule.

        Args:
            ci_config: Parsed GitLab CI configuration
            result: Result object to add violations to
        """
        pass

    def is_applicable(self, _ci_config: GitLabCI) -> bool:
        """
        Check if this rule is applicable to the given configuration.

        By default, all rules are applicable. Override for conditional rules.

        Args:
            ci_config: Parsed GitLab CI configuration

        Returns:
            True if rule should be applied, False otherwise
        """
        return True

    def add_violation(
        self,
        result: LintResult,
        message: str,
        line: int | None = None,
        column: int | None = None,
        job_name: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        """
        Helper method to add a violation with this rule's ID and level.

        Args:
            result: Result object to add violation to
            message: Violation message
            line: Line number (optional)
            column: Column number (optional)
            job_name: Job name if violation is job-specific (optional)
            suggestion: Suggested fix (optional)
        """
        result.add_violation(
            rule_id=self.rule_id,
            level=self.level,
            message=message,
            line=line,
            column=column,
            job_name=job_name,
            suggestion=suggestion,
        )

    def __str__(self) -> str:
        """String representation of rule."""
        return f"{self.rule_id}: {self.description}"
