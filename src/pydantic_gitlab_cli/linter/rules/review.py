"""Review Apps related lint rules."""

from __future__ import annotations

import logging

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintLevel, LintRule

logger = logging.getLogger(__name__)


class ReviewAppsRule(LintRule):
    """GL021: Review Apps validation - environments with review/$CI_COMMIT_REF_SLUG must have on_stop."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.WARNING)

    @property
    def rule_id(self) -> str:
        return "GL021"

    @property
    def description(self) -> str:
        return "Review Apps environment must have on_stop action defined"

    @property
    def category(self) -> str:
        return "review"

    def check(self, ci_config: GitLabCI, result) -> None:
        """Check if review apps have proper on_stop configuration."""
        try:
            if not ci_config.jobs:
                return

            for job_name, job in ci_config.jobs.items():
                self._check_job_review_app_config(job_name, job, result)

        except Exception as e:
            logger.error("Error checking GL021 (ReviewApps): %s", e)

    def _check_job_review_app_config(self, job_name: str, job, result) -> None:
        """Check a single job for review app configuration."""
        # Skip template jobs (starting with .)
        if job_name.startswith("."):
            return

        # Check if job has environment configuration
        if not hasattr(job, "environment") or not job.environment:
            return

        environment = job.environment
        env_name = self._extract_environment_name(environment)

        if not env_name or not self._is_review_app(env_name):
            return

        if not self._has_on_stop_config(environment):
            self.add_violation(
                result=result,
                message=f"Review app environment '{env_name}' should have on_stop action to clean up resources",
                job_name=job_name,
                suggestion="Add on_stop: job_name to environment configuration",
            )

    def _extract_environment_name(self, environment) -> str | None:
        """Extract environment name from environment configuration."""
        if isinstance(environment, str):
            return environment
        if isinstance(environment, dict):
            return environment.get("name")
        if hasattr(environment, "name"):
            return environment.name
        return None

    def _is_review_app(self, env_name: str) -> bool:
        """Check if environment name indicates a review app."""
        return "review/" in env_name or "$CI_COMMIT_REF_SLUG" in env_name

    def _has_on_stop_config(self, environment) -> bool:
        """Check if environment has on_stop configuration."""
        if isinstance(environment, dict):
            return "on_stop" in environment and environment["on_stop"]
        if hasattr(environment, "on_stop"):
            return environment.on_stop is not None
        return False


class StagesCompletenessRule(LintRule):
    """GL023: Each stage must contain at least one active job."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.WARNING)

    @property
    def rule_id(self) -> str:
        return "GL023"

    @property
    def description(self) -> str:
        return "Each stage must contain at least one active job"

    @property
    def category(self) -> str:
        return "structure"

    def check(self, ci_config: GitLabCI, result) -> None:
        """Check if all stages have at least one active job."""
        try:
            stages = self._get_defined_stages(ci_config)
            if not stages:
                return

            stage_job_count = self._count_active_jobs_per_stage(ci_config, stages)
            self._report_empty_stages(stage_job_count, result)

        except Exception as e:
            logger.error("Error checking GL023 (StagesCompleteness): %s", e)

    def _get_defined_stages(self, ci_config: GitLabCI) -> list:
        """Get list of defined stages."""
        if hasattr(ci_config, "stages") and ci_config.stages:
            return ci_config.stages
        # Default GitLab stages if none specified
        return ["build", "test", "deploy"]

    def _count_active_jobs_per_stage(self, ci_config: GitLabCI, stages: list) -> dict:
        """Count active jobs per stage."""
        stage_job_count = dict.fromkeys(stages, 0)

        if not ci_config.jobs:
            return stage_job_count

        for job_name, job in ci_config.jobs.items():
            if job_name.startswith("."):  # Skip template jobs
                continue

            job_stage = self._get_job_stage(job)
            if self._is_job_active(job) and job_stage in stage_job_count:
                stage_job_count[job_stage] += 1

        return stage_job_count

    def _get_job_stage(self, job) -> str:
        """Get job stage with default fallback."""
        if hasattr(job, "stage") and job.stage:
            return job.stage
        return "test"  # Default stage

    def _is_job_active(self, job) -> bool:
        """Check if job is potentially active (not disabled by rules)."""
        # Check 'only: - never'
        if hasattr(job, "only") and job.only and isinstance(job.only, list) and "never" in job.only:
            return False

        # Check if all rules have 'when: never'
        if hasattr(job, "rules") and job.rules:
            return not self._all_rules_are_never(job.rules)

        return True

    def _all_rules_are_never(self, rules) -> bool:
        """Check if all rules have 'when: never'."""
        for rule in rules:
            if isinstance(rule, dict):
                if rule.get("when") != "never":
                    return False
            elif hasattr(rule, "when") and rule.when != "never":
                return False
        return True

    def _report_empty_stages(self, stage_job_count: dict, result) -> None:
        """Report empty stages as violations."""
        for stage, count in stage_job_count.items():
            if count == 0:
                self.add_violation(
                    result=result,
                    message=f"Stage '{stage}' has no active jobs - consider removing unused stages",
                    suggestion=f"Remove stage '{stage}' from stages list or add jobs to this stage",
                )


class AllowFailureValidityRule(LintRule):
    """GL024: allow_failure should specify expected exit_codes."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.INFO)

    @property
    def rule_id(self) -> str:
        return "GL024"

    @property
    def description(self) -> str:
        return "allow_failure should specify expected exit_codes for better control"

    @property
    def category(self) -> str:
        return "quality"

    def check(self, ci_config: GitLabCI, result) -> None:
        """Check if allow_failure configurations specify exit_codes."""
        try:
            if not ci_config.jobs:
                return

            for job_name, job in ci_config.jobs.items():
                # Skip template jobs
                if job_name.startswith("."):
                    continue

                # Check allow_failure configuration
                allow_failure = None
                if hasattr(job, "allow_failure"):
                    allow_failure = job.allow_failure

                if allow_failure is None:
                    continue

                # If allow_failure is just boolean true, suggest using exit_codes
                if allow_failure is True:
                    self.add_violation(
                        result=result,
                        message="Job uses allow_failure without specifying exit_codes",
                        job_name=job_name,
                        suggestion="Use allow_failure: { exit_codes: [1, 2] } to specify which exit codes are acceptable",
                    )
                elif isinstance(allow_failure, dict) and "exit_codes" not in allow_failure:
                    self.add_violation(
                        result=result,
                        message="Job uses allow_failure without specifying exit_codes",
                        job_name=job_name,
                        suggestion="Add exit_codes: [1, 2] to allow_failure configuration",
                    )

        except Exception as e:
            logger.error("Error checking GL024 (AllowFailureValidity): %s", e)


class RulesOptimizationRule(LintRule):
    """GL025: Check for duplicate or conflicting rules conditions."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.INFO)

    @property
    def rule_id(self) -> str:
        return "GL025"

    @property
    def description(self) -> str:
        return "Rules optimization - check for duplicate or conflicting conditions"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result) -> None:
        """Check for duplicate or conflicting rules in jobs."""
        try:
            if not ci_config.jobs:
                return

            for job_name, job in ci_config.jobs.items():
                self._check_job_rules(job_name, job, result)

        except Exception as e:
            logger.error("Error checking GL025 (RulesOptimization): %s", e)

    def _check_job_rules(self, job_name: str, job, result) -> None:
        """Check rules for a single job."""
        # Skip template jobs
        if job_name.startswith("."):
            return

        rules = self._get_job_rules(job)
        if len(rules) < 2:
            return

        conditions = self._extract_rule_conditions(rules)
        self._check_duplicate_conditions(conditions, job_name, result)
        self._check_conflicting_branch_conditions(conditions, job_name, result)

    def _get_job_rules(self, job) -> list:
        """Get rules from a job."""
        if hasattr(job, "rules") and job.rules:
            return job.rules
        return []

    def _extract_rule_conditions(self, rules) -> list:
        """Extract conditions from rules."""
        conditions = []
        for rule in rules:
            condition = self._get_rule_condition(rule)
            if condition:
                conditions.append(condition)
        return conditions

    def _get_rule_condition(self, rule) -> str | None:
        """Extract condition from a single rule."""
        if isinstance(rule, dict):
            return rule.get("if")
        if hasattr(rule, "if"):
            # Access using getattr to avoid keyword conflict
            return getattr(rule, "if")
        return None

    def _check_duplicate_conditions(self, conditions: list, job_name: str, result) -> None:
        """Check for duplicate rule conditions."""
        seen_conditions = set()
        for condition in conditions:
            if condition in seen_conditions:
                self.add_violation(
                    result=result,
                    message=f"Duplicate rule condition found: {condition}",
                    job_name=job_name,
                    suggestion="Remove duplicate rule conditions to simplify job configuration",
                )
            seen_conditions.add(condition)

    def _check_conflicting_branch_conditions(self, conditions: list, job_name: str, result) -> None:
        """Check for potentially conflicting branch conditions."""
        branch_conditions = [c for c in conditions if "$CI_COMMIT_REF_NAME" in c or "$CI_COMMIT_BRANCH" in c]

        if len(branch_conditions) <= 1:
            return

        # Look for obvious conflicts like main vs develop
        has_main = any("main" in c or "master" in c for c in branch_conditions)
        has_develop = any("develop" in c or "dev" in c for c in branch_conditions)

        if has_main and has_develop:
            self.add_violation(
                result=result,
                message="Potentially conflicting branch conditions in rules",
                job_name=job_name,
                suggestion="Review rule conditions to ensure they don't conflict",
            )


class ResourceMonitoringRule(LintRule):
    """GL026: Remind about metrics collection for long-running pipelines."""

    def __init__(self):
        super().__init__(enabled=True, level=LintLevel.INFO)

    @property
    def rule_id(self) -> str:
        return "GL026"

    @property
    def description(self) -> str:
        return "Consider enabling pipeline monitoring for resource optimization"

    @property
    def category(self) -> str:
        return "monitoring"

    def check(self, ci_config: GitLabCI, result) -> None:
        """Check if pipeline might benefit from monitoring setup."""
        try:
            if not ci_config.jobs:
                return

            # Count jobs and estimate complexity
            job_count = 0
            has_long_running_indicators = False

            for job_name, job in ci_config.jobs.items():
                # Skip template jobs
                if job_name.startswith("."):
                    continue

                job_count += 1

                # Look for indicators of potentially long-running jobs
                # Check for deployment, build, test jobs
                job_lower = job_name.lower()
                if any(
                    keyword in job_lower for keyword in ["deploy", "build", "compile", "test", "e2e", "integration"]
                ):
                    has_long_running_indicators = True

                # Check for timeout configuration (indicating potentially long jobs)
                if hasattr(job, "timeout") and job.timeout:
                    try:
                        # Parse timeout (could be "30m", "1h", etc.)
                        timeout_str = job.timeout
                        if "h" in timeout_str or ("m" in timeout_str and int(timeout_str.replace("m", "")) > 15):
                            has_long_running_indicators = True
                    except (ValueError, AttributeError):
                        pass

            # If pipeline has many jobs or indicators of long-running processes
            if job_count >= 5 or has_long_running_indicators:
                # Check if monitoring is already mentioned
                monitoring_mentioned = False

                # Check variables for monitoring-related configs
                if hasattr(ci_config, "variables") and ci_config.variables:
                    var_str = str(ci_config.variables).lower()
                    if any(keyword in var_str for keyword in ["exporter", "metric", "monitor", "prometheus"]):
                        monitoring_mentioned = True

                if not monitoring_mentioned:
                    self.add_violation(
                        result=result,
                        message="Consider enabling pipeline monitoring for performance insights",
                        suggestion="Set up pipeline exporter or runner exporter to collect metrics for optimization",
                    )

        except Exception as e:
            logger.error("Error checking GL026 (ResourceMonitoring): %s", e)
