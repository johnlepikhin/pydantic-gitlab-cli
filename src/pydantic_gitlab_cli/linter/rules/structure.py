"""Structure-related lint rules."""

from __future__ import annotations

import logging

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintResult, LintRule

logger = logging.getLogger(__name__)


class StagesStructureRule(LintRule):
    """Rule 02: All used stages must be listed in root stages array."""

    @property
    def rule_id(self) -> str:
        return "GL002"

    @property
    def description(self) -> str:
        return "All job stages must be declared in the root 'stages' array"

    @property
    def category(self) -> str:
        return "structure"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check that all job stages are declared in stages array."""
        logger.debug("Checking stages structure for %s", result.file_path)

        if not ci_config.jobs:
            logger.debug("No jobs found, skipping stages check")
            return

        # Get defined stages or use defaults
        if ci_config.stages:
            defined_stages: set[str] = set(ci_config.stages)
        else:
            # GitLab default stages
            defined_stages = {".pre", "build", "test", "deploy", ".post"}

        # Always include built-in stages
        defined_stages.update([".pre", ".post"])

        # Check each job's stage
        used_stages: set[str] = set()
        undefined_stages: set[str] = set()

        for job_name, job in ci_config.jobs.items():
            job_stage = job.stage if job.stage else "test"  # Default stage
            used_stages.add(job_stage)

            if job_stage not in defined_stages:
                undefined_stages.add(job_stage)
                self.add_violation(
                    result,
                    f"Job uses undefined stage '{job_stage}'",
                    job_name=job_name,
                    suggestion=f"Add '{job_stage}' to the stages array or use an existing stage: {', '.join(sorted(defined_stages))}",
                )

        # If we have explicit stages definition, check for unused stages
        if ci_config.stages:
            unused_stages = defined_stages - used_stages - {".pre", ".post"}  # Exclude built-ins
            if unused_stages:
                self.add_violation(
                    result,
                    f"Unused stages defined: {', '.join(sorted(unused_stages))}",
                    suggestion="Remove unused stages from the stages array or add jobs that use them",
                )

        logger.debug(
            "Stages structure check completed: %d used stages, %d undefined", len(used_stages), len(undefined_stages)
        )
