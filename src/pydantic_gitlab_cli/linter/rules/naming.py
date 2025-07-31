"""Naming-related lint rules."""

import logging
import re

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintResult, LintRule

logger = logging.getLogger(__name__)


class JobNamingRule(LintRule):
    """Rule 22: Job names must be snake_case; prohibit spaces, capitals, and /\\ symbols."""

    @property
    def rule_id(self) -> str:
        return "GL022"

    @property
    def description(self) -> str:
        return "Job names must use snake_case format without spaces, capitals, or /\\ symbols"

    @property
    def category(self) -> str:
        return "naming"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check job naming conventions."""
        logger.debug("Checking job naming for %s", result.file_path)

        if not ci_config.jobs:
            logger.debug("No jobs found, skipping naming check")
            return

        for job_name in ci_config.jobs:
            self._check_job_name(job_name, result)

        logger.debug("Job naming check completed for %s", result.file_path)

    def _check_job_name(self, job_name: str, result: LintResult) -> None:
        """Check a single job name against naming conventions."""
        issues = []
        suggestions = []

        # Check for spaces
        if " " in job_name:
            issues.append("contains spaces")
            suggestions.append("replace spaces with underscores")

        # Check for capital letters
        if job_name != job_name.lower():
            issues.append("contains capital letters")
            suggestions.append("use lowercase letters")

        # Check for prohibited symbols
        prohibited_chars = ["/", "\\", "-"]  # Dashes are often discouraged in favor of underscores
        found_prohibited = [char for char in prohibited_chars if char in job_name]
        if found_prohibited:
            issues.append(f"contains prohibited characters: {', '.join(found_prohibited)}")
            if "-" in found_prohibited:
                suggestions.append("replace dashes with underscores")
            if "/" in found_prohibited or "\\" in found_prohibited:
                suggestions.append("remove path-like separators")

        # Check if it follows snake_case pattern
        if (
            not re.match(r"^[a-z][a-z0-9_]*[a-z0-9]$|^[a-z]$", job_name) and not issues
        ):  # Only add this if no specific issues were found
            issues.append("does not follow snake_case pattern")
            suggestions.append("use snake_case format (lowercase_with_underscores)")

        # Check for double underscores or starting/ending with underscore
        if "__" in job_name:
            issues.append("contains double underscores")
            suggestions.append("use single underscores between words")

        if job_name.startswith("_") or job_name.endswith("_"):
            issues.append("starts or ends with underscore")
            suggestions.append("remove leading/trailing underscores")

        # Generate suggestion for proper name
        if issues:
            proper_name = self._suggest_proper_name(job_name)
            issue_text = "; ".join(issues)
            suggestion_text = f"Use snake_case format. Suggested: '{proper_name}'"

            self.add_violation(
                result, f"Job name '{job_name}' {issue_text}", job_name=job_name, suggestion=suggestion_text
            )

    def _suggest_proper_name(self, job_name: str) -> str:
        """Suggest a proper snake_case name."""
        # Convert to lowercase
        name = job_name.lower()

        # Replace spaces and prohibited characters with underscores
        name = re.sub(r"[^a-z0-9_]", "_", name)

        # Replace multiple underscores with single
        name = re.sub(r"_+", "_", name)

        # Remove leading/trailing underscores
        name = name.strip("_")

        # Ensure it's not empty
        if not name:
            name = "job"

        return name
