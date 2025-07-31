"""Syntax-related lint rules."""

import logging

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintResult, LintRule

logger = logging.getLogger(__name__)


class YamlSyntaxRule(LintRule):
    """Rule 01: YAML parsing without duplicate keys; must validate with GitLab linter."""

    @property
    def rule_id(self) -> str:
        return "GL001"

    @property
    def description(self) -> str:
        return "YAML must parse correctly without duplicate keys and validate with GitLab linter"

    @property
    def category(self) -> str:
        return "syntax"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """
        Check YAML syntax and structure.

        Note: Basic YAML parsing is handled by the engine before rules run.
        This rule performs additional GitLab-specific validations.
        """
        logger.debug("Checking YAML syntax for %s", result.file_path)

        # Check for required structure elements
        if not ci_config.jobs and not ci_config.stages:
            self.add_violation(
                result,
                "GitLab CI file must contain at least one job or stages definition",
                suggestion="Add at least one job definition or stages list",
            )
            return

        # Check for common GitLab CI structure issues
        if ci_config.jobs:
            for job_name, job in ci_config.jobs.items():
                # Check for jobs without script, trigger, or extends
                if not any(
                    [
                        job.script,
                        job.trigger,
                        job.extends,
                        hasattr(job, "run"),  # GitLab 16.0+ run keyword
                    ]
                ):
                    self.add_violation(
                        result,
                        "Job must have at least one of: script, trigger, extends, or run",
                        job_name=job_name,
                        suggestion="Add a 'script' section with commands to execute",
                    )

        # Validate stage references
        if ci_config.stages and ci_config.jobs:
            defined_stages = set(ci_config.stages)
            # Add default stages that are always available
            defined_stages.update([".pre", ".post"])

            for job_name, job in ci_config.jobs.items():
                if job.stage and job.stage not in defined_stages:
                    self.add_violation(
                        result,
                        f"Job references undefined stage '{job.stage}'",
                        job_name=job_name,
                        suggestion=f"Add '{job.stage}' to the stages list or use one of: {', '.join(sorted(defined_stages))}",
                    )

        logger.debug("YAML syntax check completed for %s", result.file_path)
