"""Dependency-related lint rules."""

from __future__ import annotations

import logging

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintLevel, LintResult, LintRule

logger = logging.getLogger(__name__)


class JobDependenciesRule(LintRule):
    """Rule 03: Check for cycles, unreachable jobs, and unnecessary waiting in dependencies."""

    @property
    def rule_id(self) -> str:
        return "GL003"

    @property
    def description(self) -> str:
        return "Job dependencies must not have cycles or unreachable jobs"

    @property
    def category(self) -> str:
        return "dependencies"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check job dependencies for cycles and reachability."""
        logger.debug("Checking job dependencies for %s", result.file_path)

        if not ci_config.jobs:
            logger.debug("No jobs found, skipping dependencies check")
            return

        job_names = set(ci_config.jobs.keys())
        dependencies, needs_dependencies = self._build_dependency_graph(ci_config, job_names, result)

        # Check for cycles in dependencies
        self._check_cycles(dependencies, result, "dependencies")
        self._check_cycles(needs_dependencies, result, "needs")

        # Check for unreachable jobs (jobs that no other job depends on and are not in first stage)
        self._check_unreachable_jobs(ci_config, dependencies, needs_dependencies, result)

        # Check for unnecessary stage-based waiting when needs could be used
        self._check_stage_optimization(ci_config, needs_dependencies, result)

        logger.debug("Job dependencies check completed for %s", result.file_path)

    def _build_dependency_graph(
        self, ci_config: GitLabCI, job_names: set[str], result: LintResult
    ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Build dependency graphs for traditional dependencies and needs."""
        dependencies: dict[str, set[str]] = {}
        needs_dependencies: dict[str, set[str]] = {}

        for job_name, job in ci_config.jobs.items():
            dependencies[job_name] = set()
            needs_dependencies[job_name] = set()

            self._process_traditional_dependencies(job, job_name, job_names, dependencies, result)
            self._process_needs_dependencies(job, job_name, job_names, needs_dependencies, result)

        return dependencies, needs_dependencies

    def _process_traditional_dependencies(
        self, job, job_name: str, job_names: set[str], dependencies: dict[str, set[str]], result: LintResult
    ) -> None:
        """Process traditional job dependencies."""
        if job.dependencies:
            for dep in job.dependencies:
                if dep not in job_names:
                    self.add_violation(
                        result,
                        f"Job depends on non-existent job '{dep}'",
                        job_name=job_name,
                        suggestion=f"Remove dependency '{dep}' or create the missing job",
                    )
                else:
                    dependencies[job_name].add(dep)

    def _process_needs_dependencies(
        self, job, job_name: str, job_names: set[str], needs_dependencies: dict[str, set[str]], result: LintResult
    ) -> None:
        """Process needs-based job dependencies."""
        if job.needs:
            for need in job.needs:
                need_job = self._extract_need_job_name(need)
                if need_job and need_job not in job_names:
                    self.add_violation(
                        result,
                        f"Job needs non-existent job '{need_job}'",
                        job_name=job_name,
                        suggestion=f"Remove need '{need_job}' or create the missing job",
                    )
                elif need_job:
                    needs_dependencies[job_name].add(need_job)

    def _extract_need_job_name(self, need) -> str | None:
        """Extract job name from needs specification."""
        if isinstance(need, str):
            return need
        if hasattr(need, "job"):
            return need.job
        return None

    def _check_cycles(self, deps: dict[str, set[str]], result: LintResult, dep_type: str) -> None:
        """Check for circular dependencies."""

        def has_cycle(job: str, path: set[str]) -> bool:
            if job in path:
                return True
            path.add(job)
            for dep in deps.get(job, set()):
                if has_cycle(dep, path):
                    return True
            path.remove(job)
            return False

        for job_name in deps:
            if has_cycle(job_name, set()):
                self.add_violation(
                    result,
                    f"Circular dependency detected in {dep_type}",
                    job_name=job_name,
                    suggestion=f"Review and fix circular {dep_type} chain",
                )

    def _check_unreachable_jobs(
        self,
        ci_config: GitLabCI,
        dependencies: dict[str, set[str]],
        needs_dependencies: dict[str, set[str]],
        result: LintResult,
    ) -> None:
        """Check for jobs that might be unreachable."""
        all_stages = ci_config.get_all_stages()
        first_stage = all_stages[0] if all_stages else "build"

        # Find jobs in first stage (these are always reachable)
        first_stage_jobs = set()
        for job_name, job in ci_config.jobs.items():
            job_stage = job.stage if job.stage else "test"
            if job_stage in (first_stage, ".pre"):
                first_stage_jobs.add(job_name)

        # Find all jobs that are dependencies of other jobs
        referenced_jobs = set()
        for deps in dependencies.values():
            referenced_jobs.update(deps)
        for deps in needs_dependencies.values():
            referenced_jobs.update(deps)

        # Check for potentially unreachable jobs
        for job_name, job in ci_config.jobs.items():
            if (
                job_name not in first_stage_jobs
                and job_name not in referenced_jobs
                and job.when not in ["manual", "delayed"]  # Manual jobs are intentionally not auto-triggered
                and not (job.rules and any(getattr(rule, "when", None) == "manual" for rule in job.rules))
            ):
                job_stage = job.stage if job.stage else "test"
                # Temporarily change level for this violation
                original_level = self.level
                self.level = LintLevel.WARNING
                self.add_violation(
                    result,
                    "Job may be unreachable (not in first stage and not referenced by other jobs)",
                    job_name=job_name,
                    suggestion="Ensure job is properly connected via dependencies, needs, or stage ordering",
                )
                self.level = original_level

    def _check_stage_optimization(
        self, ci_config: GitLabCI, needs_dependencies: dict[str, set[str]], result: LintResult
    ) -> None:
        """Check if stage-based waiting could be optimized with needs."""
        if not ci_config.stages or len(ci_config.stages) <= 2:
            return  # Not much to optimize with few stages

        # Find jobs that could potentially use needs instead of stage ordering
        stage_jobs: dict[str, list[str]] = {}
        for job_name, job in ci_config.jobs.items():
            job_stage = job.stage if job.stage else "test"
            if job_stage not in stage_jobs:
                stage_jobs[job_stage] = []
            stage_jobs[job_stage].append(job_name)

        # Look for jobs in later stages that don't use needs
        stages = ci_config.stages or []
        for i, stage in enumerate(stages[1:], 1):  # Skip first stage
            stage_job_list = stage_jobs.get(stage, [])
            for job_name in stage_job_list:
                if not needs_dependencies.get(job_name):
                    # This job relies on stage ordering but could potentially use needs
                    prev_stage_jobs = []
                    for j in range(i):
                        prev_stage_jobs.extend(stage_jobs.get(stages[j], []))

                    if len(prev_stage_jobs) > 3:  # Only suggest if there are many previous jobs
                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.INFO
                        self.add_violation(
                            result,
                            "Job relies on stage ordering but could use 'needs' for faster execution",
                            job_name=job_name,
                            suggestion="Consider using 'needs' to specify exact job dependencies instead of stage ordering",
                        )
                        self.level = original_level
