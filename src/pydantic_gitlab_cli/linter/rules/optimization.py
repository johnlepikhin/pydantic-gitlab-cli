"""Optimization-related lint rules."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintLevel, LintResult, LintRule

logger = logging.getLogger(__name__)


class VariableOptimizationRule(LintRule):
    """Rule 14: Check for variable scope optimization and unused variables."""

    @property
    def rule_id(self) -> str:
        return "GL014"

    @property
    def description(self) -> str:
        return "Variables should be optimally scoped and unused variables removed"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check variable optimization."""
        logger.debug("Checking variable optimization in %s", result.file_path)

        global_vars = self._collect_global_variables(ci_config)
        job_vars, var_usage = self._analyze_variable_usage(ci_config)

        # Check for optimization opportunities
        self._check_unused_global_variables(global_vars, var_usage, result)
        self._check_single_use_global_variables(global_vars, var_usage, result)
        self._check_duplicate_job_variables(job_vars, result)

        logger.debug("Variable optimization check completed for %s", result.file_path)

    def _collect_global_variables(self, ci_config: GitLabCI) -> set[str]:
        """Collect all global variables."""
        global_vars = set()
        if ci_config.variables and ci_config.variables.variables:
            global_vars = set(ci_config.variables.variables.keys())
        return global_vars

    def _analyze_variable_usage(self, ci_config: GitLabCI) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Analyze variable usage across jobs."""
        job_vars: dict[str, set[str]] = {}
        var_usage: dict[str, set[str]] = {}  # var_name -> set of jobs using it

        for job_name, job in ci_config.jobs.items():
            job_vars[job_name] = self._collect_job_variables(job)
            self._track_variable_usage_in_job(job, job_name, var_usage)

        return job_vars, var_usage

    def _collect_job_variables(self, job) -> set[str]:
        """Collect variables defined in a job."""
        variables = set()
        if job.variables:
            if hasattr(job.variables, "variables"):
                var_dict = job.variables.variables or {}
            elif isinstance(job.variables, dict):
                var_dict = job.variables
            else:
                var_dict = {}
            variables.update(var_dict.keys())
        return variables

    def _track_variable_usage_in_job(self, job, job_name: str, var_usage: dict[str, set[str]]) -> None:
        """Track variable usage in job scripts."""
        all_scripts = []
        if job.script:
            all_scripts.extend(job.script)
        if job.before_script:
            all_scripts.extend(job.before_script)
        if job.after_script:
            all_scripts.extend(job.after_script)

        # Find variable references in scripts
        for script in all_scripts:
            var_refs = re.findall(r"\$\{?([A-Z_][A-Z0-9_]*)\}?", script, re.IGNORECASE)
            for var_ref in var_refs:
                if var_ref not in var_usage:
                    var_usage[var_ref] = set()
                var_usage[var_ref].add(job_name)

    def _check_unused_global_variables(
        self, global_vars: set[str], var_usage: dict[str, set[str]], result: LintResult
    ) -> None:
        """Check for unused global variables."""
        for global_var in global_vars:
            if global_var not in var_usage and not global_var.startswith("CI_"):
                original_level = self.level
                self.level = LintLevel.INFO
                self.add_violation(
                    result,
                    f"Global variable '{global_var}' appears to be unused",
                    suggestion="Remove unused global variables or ensure they are properly referenced",
                )
                self.level = original_level

    def _check_single_use_global_variables(
        self, global_vars: set[str], var_usage: dict[str, set[str]], result: LintResult
    ) -> None:
        """Check for global variables used in only one job."""
        for var_name, using_jobs in var_usage.items():
            if var_name in global_vars and len(using_jobs) == 1:
                job_name = next(iter(using_jobs))
                original_level = self.level
                self.level = LintLevel.INFO
                self.add_violation(
                    result,
                    f"Global variable '{var_name}' is only used in one job",
                    job_name=job_name,
                    suggestion=f"Consider moving variable '{var_name}' to job level for better scoping",
                )
                self.level = original_level

    def _check_duplicate_job_variables(self, job_vars: dict[str, set[str]], result: LintResult) -> None:
        """Check for variables duplicated across jobs."""
        var_definitions: dict[str, list[str]] = {}
        for job_name, vars_set in job_vars.items():
            for var_name in vars_set:
                if var_name not in var_definitions:
                    var_definitions[var_name] = []
                var_definitions[var_name].append(job_name)

        for var_name, job_list in var_definitions.items():
            if len(job_list) > 2:  # Variable defined in multiple jobs
                original_level = self.level
                self.level = LintLevel.INFO
                self.add_violation(
                    result,
                    f"Variable '{var_name}' is defined in multiple jobs: {', '.join(job_list)}",
                    suggestion=f"Consider moving '{var_name}' to global scope or use extends/anchors",
                )
                self.level = original_level


class ParallelizationRule(LintRule):
    """Rule 15: Check for parallelization opportunities and matrix optimization."""

    @property
    def rule_id(self) -> str:
        return "GL015"

    @property
    def description(self) -> str:
        return "Jobs should use parallelization opportunities like matrix builds"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check parallelization opportunities."""
        logger.debug("Checking parallelization opportunities in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            self._check_test_parallelization(job_name, job, result)
            self._check_matrix_opportunities(job_name, job, result)

        logger.debug("Parallelization check completed for %s", result.file_path)

    def _check_test_parallelization(self, job_name: str, job, result: LintResult) -> None:
        """Check if test jobs could benefit from parallelization."""
        is_test_job = any(keyword in job_name.lower() for keyword in ["test", "spec", "check"])

        if not (is_test_job and job.script):
            return

        parallel_indicators = []
        for script in job.script:
            indicators = self._find_parallel_test_opportunities(script)
            parallel_indicators.extend(indicators)

        if parallel_indicators:
            original_level = self.level
            self.level = LintLevel.INFO
            self.add_violation(
                result,
                f"Test job could benefit from parallelization: {'; '.join(parallel_indicators)}",
                job_name=job_name,
                suggestion="Consider enabling parallel test execution for faster CI times",
            )
            self.level = original_level

    def _find_parallel_test_opportunities(self, script: str) -> list[str]:
        """Find parallelization opportunities in a script."""
        indicators = []

        # Jest/Node.js testing
        if (
            re.search(r"npm\s+(?:run\s+)?test|yarn\s+test|jest", script, re.IGNORECASE)
            and "--maxWorkers" not in script
            and "--parallel" not in script
        ):
            indicators.append("Jest tests could use --maxWorkers")

        # pytest
        if (
            re.search(r"pytest|py\.test", script, re.IGNORECASE)
            and "-n" not in script
            and "--numprocesses" not in script
        ):
            indicators.append("pytest could use -n for parallel execution")

        # RSpec
        if re.search(r"rspec|bundle\s+exec\s+rspec", script, re.IGNORECASE) and "--parallel" not in script:
            indicators.append("RSpec could use parallel execution")

        # Go tests
        if re.search(r"go\s+test", script, re.IGNORECASE) and "-parallel" not in script:
            indicators.append("Go tests could use -parallel flag")

        return indicators

    def _check_matrix_opportunities(self, job_name: str, job, result: LintResult) -> None:
        """Check if jobs could benefit from matrix builds."""
        if not job.script or hasattr(job, "parallel"):
            return

        matrix_indicators = []
        for script in job.script:
            indicators = self._find_matrix_opportunities(script)
            matrix_indicators.extend(indicators)

        if matrix_indicators:
            original_level = self.level
            self.level = LintLevel.INFO
            self.add_violation(
                result,
                f"Job might benefit from matrix builds for: {', '.join(matrix_indicators)}",
                job_name=job_name,
                suggestion="Consider using 'parallel: matrix' for testing multiple configurations",
            )
            self.level = original_level

    def _find_matrix_opportunities(self, script: str) -> list[str]:
        """Find matrix build opportunities in a script."""
        indicators = []

        # Multiple version patterns
        if re.search(r"(node|python|ruby|php|java)[-_]?(\d+\.?\d*)", script, re.IGNORECASE):
            indicators.append("version testing")

        # Multiple environment patterns
        if re.search(r"(test|run).*--(env|environment)", script, re.IGNORECASE):
            indicators.append("environment testing")

        return indicators


class TimeoutOptimizationRule(LintRule):
    """Rule 16: Check for appropriate timeout settings."""

    @property
    def rule_id(self) -> str:
        return "GL016"

    @property
    def description(self) -> str:
        return "Jobs should have appropriate timeout settings to prevent hanging"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check timeout optimization."""
        logger.debug("Checking timeout optimization in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            # Check if job has timeout
            has_timeout = job.timeout is not None

            # Determine job type for timeout recommendations
            job_type = self._classify_job(job_name, job)

            if not has_timeout:
                # Recommend timeouts for certain job types
                if job_type in ["test", "build", "deploy"]:
                    recommended_timeout = {"test": "15 minutes", "build": "30 minutes", "deploy": "10 minutes"}.get(
                        job_type, "1 hour"
                    )

                    # Temporarily change level for this violation
                    original_level = self.level
                    self.level = LintLevel.INFO
                    self.add_violation(
                        result,
                        f"Job lacks timeout setting (type: {job_type})",
                        job_name=job_name,
                        suggestion=f"Consider adding 'timeout: {recommended_timeout}' to prevent hanging",
                    )
                    self.level = original_level
            else:
                # Check if timeout is appropriate
                timeout_str = str(job.timeout).lower()

                # Very long timeouts
                if any(long_duration in timeout_str for long_duration in ["hour", "hours", "h"]):
                    timeout_hours = self._extract_hours(timeout_str)
                    if timeout_hours and timeout_hours > 2:
                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.WARNING
                        self.add_violation(
                            result,
                            f"Job has very long timeout: {job.timeout}",
                            job_name=job_name,
                            suggestion="Consider optimizing job or breaking into smaller parts",
                        )
                        self.level = original_level

                # Very short timeouts for complex jobs
                if job_type in ["build", "deploy"] and "minute" in timeout_str:
                    timeout_minutes = self._extract_minutes(timeout_str)
                    if timeout_minutes and timeout_minutes < 5:
                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.WARNING
                        self.add_violation(
                            result,
                            f"Job has very short timeout for {job_type} job: {job.timeout}",
                            job_name=job_name,
                            suggestion=f"Consider longer timeout for {job_type} jobs",
                        )
                        self.level = original_level

        logger.debug("Timeout optimization check completed for %s", result.file_path)

    def _classify_job(self, job_name: str, _job) -> str:
        """Classify job type based on name and content."""
        name_lower = job_name.lower()

        if any(keyword in name_lower for keyword in ["test", "spec", "check", "lint"]):
            return "test"
        if any(keyword in name_lower for keyword in ["build", "compile", "package"]):
            return "build"
        if any(keyword in name_lower for keyword in ["deploy", "release", "publish"]):
            return "deploy"
        if any(keyword in name_lower for keyword in ["clean", "setup"]):
            return "utility"
        return "unknown"

    def _extract_hours(self, timeout_str: str) -> int | None:
        """Extract hours from timeout string."""
        match = re.search(r"(\d+)\s*h(?:our)?s?", timeout_str, re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _extract_minutes(self, timeout_str: str) -> int | None:
        """Extract minutes from timeout string."""
        match = re.search(r"(\d+)\s*m(?:in|inute)?s?", timeout_str, re.IGNORECASE)
        return int(match.group(1)) if match else None


class JobReuseRule(LintRule):
    """Rule 17: Check for job reuse opportunities using extends and anchors."""

    @property
    def rule_id(self) -> str:
        return "GL017"

    @property
    def description(self) -> str:
        return "Jobs should use extends/anchors to reduce duplication"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check job reuse opportunities."""
        logger.debug("Checking job reuse opportunities in %s", result.file_path)

        # Analyze job patterns for duplication
        job_patterns: dict[str, list[str]] = {}

        for job_name, job in ci_config.jobs.items():
            # Create pattern signature for job
            pattern = self._create_job_pattern(job)
            if pattern not in job_patterns:
                job_patterns[pattern] = []
            job_patterns[pattern].append(job_name)

        # Find duplicate patterns
        for _pattern, job_list in job_patterns.items():
            if len(job_list) > 2:  # 3 or more similar jobs
                # Check if any job uses extends
                uses_extends = any(
                    hasattr(ci_config.jobs[job_name], "extends") and ci_config.jobs[job_name].extends
                    for job_name in job_list
                )

                if not uses_extends:
                    # Temporarily change level for this violation
                    original_level = self.level
                    self.level = LintLevel.INFO
                    self.add_violation(
                        result,
                        f"Similar jobs could use extends/anchors: {', '.join(job_list)}",
                        suggestion="Consider creating a base job template with common configuration",
                    )
                    self.level = original_level

        # Check for common script patterns
        script_patterns: dict[str, list[str]] = {}

        for job_name, job in ci_config.jobs.items():
            if job.script:
                # Normalize scripts for comparison
                normalized_scripts = [script.strip().lower() for script in job.script]
                script_key = "|".join(normalized_scripts[:3])  # First 3 commands

                if len(script_key) > 20:  # Only for substantial scripts
                    if script_key not in script_patterns:
                        script_patterns[script_key] = []
                    script_patterns[script_key].append(job_name)

        # Find duplicate script patterns
        for _script_key, job_list in script_patterns.items():
            if len(job_list) > 2:
                # Temporarily change level for this violation
                original_level = self.level
                self.level = LintLevel.INFO
                self.add_violation(
                    result,
                    f"Jobs with similar scripts could share common steps: {', '.join(job_list)}",
                    suggestion="Consider using before_script, extends, or YAML anchors for common script patterns",
                )
                self.level = original_level

        logger.debug("Job reuse check completed for %s", result.file_path)

    def _create_job_pattern(self, job) -> str:
        """Create a pattern signature for job comparison."""
        pattern_parts = []

        if job.image:
            image_name = job.image
            if isinstance(image_name, dict) and "name" in image_name:
                image_name = image_name["name"]
            pattern_parts.append(f"image:{image_name}")

        if job.stage:
            pattern_parts.append(f"stage:{job.stage}")

        if job.services:
            services_count = len(job.services)
            pattern_parts.append(f"services:{services_count}")

        if job.before_script:
            pattern_parts.append(f"before_script:{len(job.before_script)}")

        if job.cache:
            pattern_parts.append("has_cache")

        if job.artifacts:
            pattern_parts.append("has_artifacts")

        return "|".join(pattern_parts)


class CachePolicyRule(LintRule):
    """Rule 18: Check cache policy optimization."""

    @property
    def rule_id(self) -> str:
        return "GL018"

    @property
    def description(self) -> str:
        return "Cache policies should be optimized for CI performance"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check cache policy optimization."""
        logger.debug("Checking cache policy optimization in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            if job.cache:
                cache_configs = job.cache if isinstance(job.cache, list) else [job.cache]

                for _i, cache_config in enumerate(cache_configs):
                    # Check cache policy
                    cache_policy = None
                    if hasattr(cache_config, "policy"):
                        cache_policy = cache_config.policy
                    elif isinstance(cache_config, dict) and "policy" in cache_config:
                        cache_policy = cache_config["policy"]

                    # Recommend appropriate policies
                    job_type = self._classify_job_type(job_name, job)

                    if not cache_policy:
                        recommended_policy = self._get_recommended_policy(job_type)
                        if recommended_policy:
                            # Temporarily change level for this violation
                            original_level = self.level
                            self.level = LintLevel.INFO
                            self.add_violation(
                                result,
                                f"Cache missing policy setting for {job_type} job",
                                job_name=job_name,
                                suggestion=f"Consider adding 'policy: {recommended_policy}' to cache configuration",
                            )
                            self.level = original_level
                    # Check if policy matches job type
                    elif job_type == "build" and cache_policy == "pull":
                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.WARNING
                        self.add_violation(
                            result,
                            "Build job uses 'pull' cache policy but should push cache",
                            job_name=job_name,
                            suggestion="Consider using 'policy: push' or 'policy: pull-push' for build jobs",
                        )
                        self.level = original_level

                    elif job_type == "test" and cache_policy == "push":
                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.INFO
                        self.add_violation(
                            result,
                            "Test job uses 'push' cache policy but typically only needs to pull",
                            job_name=job_name,
                            suggestion="Consider using 'policy: pull' for test jobs unless they generate cache",
                        )
                        self.level = original_level

        logger.debug("Cache policy optimization check completed for %s", result.file_path)

    def _classify_job_type(self, job_name: str, _job) -> str:
        """Classify job type for cache policy recommendations."""
        name_lower = job_name.lower()

        if any(keyword in name_lower for keyword in ["build", "compile", "install", "setup"]):
            return "build"
        if any(keyword in name_lower for keyword in ["test", "spec", "check", "lint"]):
            return "test"
        if any(keyword in name_lower for keyword in ["deploy", "release", "publish"]):
            return "deploy"
        return "unknown"

    def _get_recommended_policy(self, job_type: str) -> str | None:
        """Get recommended cache policy for job type."""
        recommendations = {
            "build": "pull-push",  # Build jobs should update cache
            "test": "pull",  # Test jobs typically only consume cache
            "deploy": "pull",  # Deploy jobs typically only consume cache
        }
        return recommendations.get(job_type)


class LintStageRule(LintRule):
    """Rule 19: Check for dedicated lint/quality stage optimization."""

    @property
    def rule_id(self) -> str:
        return "GL019"

    @property
    def description(self) -> str:
        return "Lint and quality checks should be optimized in dedicated stages"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check lint stage optimization."""
        logger.debug("Checking lint stage optimization in %s", result.file_path)

        lint_jobs = self._find_lint_jobs(ci_config)
        if not lint_jobs:
            return  # No lint jobs to optimize

        self._check_lint_stage_placement(lint_jobs, ci_config.stages or [], result)
        self._check_lint_fail_fast_config(lint_jobs, result)
        self._check_lint_job_optimization(lint_jobs, result)

        logger.debug("Lint stage optimization check completed for %s", result.file_path)

    def _find_lint_jobs(self, ci_config: GitLabCI) -> list[tuple[str, Any]]:
        """Find all lint/quality jobs."""
        lint_jobs = []
        for job_name, job in ci_config.jobs.items():
            if self._is_lint_job(job_name, job):
                lint_jobs.append((job_name, job))
        return lint_jobs

    def _check_lint_stage_placement(
        self, lint_jobs: list[tuple[str, Any]], stages: list[str], result: LintResult
    ) -> None:
        """Check if lint jobs are in appropriate early stages."""
        if not stages:
            return

        early_stages = stages[:2]  # First two stages
        for job_name, job in lint_jobs:
            job_stage = job.stage if job.stage else "test"
            if job_stage not in early_stages:
                original_level = self.level
                self.level = LintLevel.INFO
                self.add_violation(
                    result,
                    f"Lint job is in late stage '{job_stage}', consider moving earlier",
                    job_name=job_name,
                    suggestion="Move lint jobs to early stages (e.g., 'lint', 'quality') for faster feedback",
                )
                self.level = original_level

    def _check_lint_fail_fast_config(self, lint_jobs: list[tuple[str, Any]], result: LintResult) -> None:
        """Check fail-fast configuration for lint jobs."""
        for job_name, job in lint_jobs:
            allows_failure = hasattr(job, "allow_failure") and job.allow_failure
            if allows_failure:
                original_level = self.level
                self.level = LintLevel.WARNING
                self.add_violation(
                    result,
                    "Lint job allows failure, which reduces quality enforcement",
                    job_name=job_name,
                    suggestion="Consider setting 'allow_failure: false' for lint jobs to enforce quality",
                )
                self.level = original_level

    def _check_lint_job_optimization(self, lint_jobs: list[tuple[str, Any]], result: LintResult) -> None:
        """Check optimization opportunities for lint jobs."""
        for job_name, job in lint_jobs:
            suggestions = self._get_lint_optimization_suggestions(job)
            if suggestions:
                original_level = self.level
                self.level = LintLevel.INFO
                self.add_violation(
                    result,
                    f"Lint job could be optimized: {'; '.join(suggestions)}",
                    job_name=job_name,
                    suggestion="Optimize lint jobs for faster execution",
                )
                self.level = original_level

    def _get_lint_optimization_suggestions(self, job) -> list[str]:
        """Get optimization suggestions for a lint job."""
        suggestions = []

        # Check if uses minimal image
        if job.image:
            image_name = str(job.image).lower()
            if not any(keyword in image_name for keyword in ["alpine", "slim", "minimal"]):
                suggestions.append("consider using minimal image (e.g., alpine-based)")

        # Check for unnecessary artifacts in lint jobs
        if job.artifacts:
            suggestions.append("lint jobs typically don't need artifacts")

        # Check for unnecessary cache in simple lint jobs
        if job.cache and job.script:
            simple_lint_patterns = ["flake8", "pylint", "eslint", "rubocop", "golint"]
            if (
                any(pattern in " ".join(job.script).lower() for pattern in simple_lint_patterns)
                and len(job.script) <= 2
            ):
                suggestions.append("simple lint jobs might not need cache")

        return suggestions

    def _is_lint_job(self, job_name: str, job) -> bool:
        """Determine if job is a lint/quality job."""
        name_lower = job_name.lower()

        # Check job name
        if any(keyword in name_lower for keyword in ["lint", "format", "style", "quality", "check"]):
            return True

        # Check script content
        if job.script:
            script_content = " ".join(job.script).lower()
            lint_tools = [
                "pylint",
                "flake8",
                "black",
                "isort",
                "mypy",
                "eslint",
                "prettier",
                "tslint",
                "rubocop",
                "reek",
                "golint",
                "gofmt",
                "vet",
                "clippy",
                "rustfmt",
                "checkstyle",
                "spotbugs",
                "shellcheck",
                "hadolint",
            ]

            if any(tool in script_content for tool in lint_tools):
                return True

        return False


class ParallelMatrixLimitRule(LintRule):
    """GL033: Check that parallel:matrix doesn't generate more than 200 jobs."""

    @property
    def rule_id(self) -> str:
        return "GL033"

    @property
    def description(self) -> str:
        return "Parallel matrix configuration must not generate more than 200 jobs"

    @property
    def category(self) -> str:
        return "optimization"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check parallel matrix job generation limits."""
        logger.debug("Checking parallel matrix limits in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            if not hasattr(job, "parallel") or not job.parallel:
                continue

            logger.debug(f"Checking job {job_name}, parallel config: {job.parallel}")
            total_jobs = self._calculate_matrix_jobs(job.parallel)
            logger.debug(f"Job {job_name} will generate {total_jobs} jobs")

            if total_jobs > 200:
                self.add_violation(
                    result,
                    f"Parallel matrix will generate {total_jobs} jobs, exceeding GitLab's limit of 200",
                    job_name=job_name,
                    suggestion="Reduce the number of matrix combinations or split into multiple jobs",
                )

        logger.debug("Parallel matrix limit check completed for %s", result.file_path)

    def _calculate_matrix_jobs(self, parallel_config) -> int:
        """Calculate total number of jobs that will be generated by parallel:matrix."""
        if isinstance(parallel_config, int):
            # Simple parallel: N syntax
            return parallel_config

        # Check if it's a dict with matrix key
        if isinstance(parallel_config, dict) and "matrix" in parallel_config:
            matrix = parallel_config["matrix"]
            return self._calculate_matrix_combinations(matrix)

        # Check if parallel_config has matrix attribute (Pydantic model)
        if hasattr(parallel_config, "matrix") and parallel_config.matrix:
            return self._calculate_matrix_combinations(parallel_config.matrix)

        # Default case if we can't determine
        return 1

    def _calculate_matrix_combinations(self, matrix) -> int:
        """Calculate the number of combinations from a matrix configuration."""
        if not matrix:
            return 0

        # If matrix is a list of dicts (standard GitLab format)
        if isinstance(matrix, list):
            total_jobs = 0
            for matrix_item in matrix:
                if isinstance(matrix_item, dict):
                    # Calculate cartesian product for this matrix item
                    combinations = 1
                    for _var_name, values in matrix_item.items():
                        if isinstance(values, list):
                            combinations *= len(values)
                        elif isinstance(values, (str, int, float, bool)):
                            # Single value counts as 1
                            combinations *= 1
                    total_jobs += combinations
                else:
                    # If it's not a dict, count it as 1 job
                    total_jobs += 1
            return total_jobs

        # Fallback - assume 1 job
        return 1
