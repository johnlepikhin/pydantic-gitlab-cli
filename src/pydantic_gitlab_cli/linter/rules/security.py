"""Security-related lint rules."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintResult, LintRule

logger = logging.getLogger(__name__)


class SecretsInCodeRule(LintRule):
    """Rule 12: Prohibit secrets/keys in script, variables, rules; use protected variables."""

    @property
    def rule_id(self) -> str:
        return "GL012"

    @property
    def description(self) -> str:
        return "Secrets/keys must not be hardcoded in scripts, variables, or rules"

    @property
    def category(self) -> str:
        return "security"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check for hardcoded secrets in configuration."""
        logger.debug("Checking for hardcoded secrets in %s", result.file_path)

        # Common secret patterns
        secret_patterns = [
            (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?[^\s"\']{8,}["\']?', "password"),
            (r'(?i)(api[-_]?key|apikey)\s*[:=]\s*["\']?[^\s"\']{16,}["\']?', "API key"),
            (r'(?i)(secret[-_]?key|secretkey)\s*[:=]\s*["\']?[^\s"\']{16,}["\']?', "secret key"),
            (r'(?i)(access[-_]?token|accesstoken)\s*[:=]\s*["\']?[^\s"\']{20,}["\']?', "access token"),
            (r'(?i)(private[-_]?key|privatekey)\s*[:=]\s*["\']?[^\s"\']{32,}["\']?', "private key"),
            (r"(?i)-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "private key block"),
            (r"(?i)(bearer\s+[a-zA-Z0-9]{20,})", "bearer token"),
            (r"(?i)(basic\s+[a-zA-Z0-9+/]{16,}={0,2})", "basic auth"),
            # Common cloud provider patterns
            (r"AKIA[0-9A-Z]{16}", "AWS access key"),
            (r"(?i)ghp_[a-zA-Z0-9]{36}", "GitHub personal access token"),
            (r"(?i)glpat-[a-zA-Z0-9_\-]{20}", "GitLab personal access token"),
        ]

        # Check global variables
        if ci_config.variables and ci_config.variables.variables:
            self._check_variables_dict(ci_config.variables.variables, result, "global variables", secret_patterns)

        # Check job configurations
        for job_name, job in ci_config.jobs.items():
            context = f"job '{job_name}'"

            # Check job variables
            if job.variables:
                if hasattr(job.variables, "variables") and job.variables.variables:
                    self._check_variables_dict(job.variables.variables, result, context, secret_patterns)
                elif isinstance(job.variables, dict):
                    self._check_variables_dict(job.variables, result, context, secret_patterns)

            # Check scripts
            if job.script:
                self._check_script_list(job.script, result, context, secret_patterns)

            if job.before_script:
                self._check_script_list(job.before_script, result, context + " before_script", secret_patterns)

            if job.after_script:
                self._check_script_list(job.after_script, result, context + " after_script", secret_patterns)

            # Check rules
            if job.rules:
                for i, rule in enumerate(job.rules):
                    if hasattr(rule, "variables") and rule.variables:
                        self._check_variables_dict(rule.variables, result, f"{context} rule {i}", secret_patterns)

        logger.debug("Secrets check completed for %s", result.file_path)

    def _check_variables_dict(
        self, variables: dict[str, Any], result: LintResult, context: str, patterns: list[tuple[str, str]]
    ) -> None:
        """Check variables dictionary for secrets."""
        for var_name, var_value in variables.items():
            var_str = f"{var_name}={var_value}"

            # Skip variable references
            if isinstance(var_value, str) and "$" in var_value:
                continue

            for pattern, secret_type in patterns:
                if re.search(pattern, var_str):
                    self.add_violation(
                        result,
                        f"Potential {secret_type} detected in {context}: {var_name}",
                        suggestion="Use GitLab protected variables or CI/CD secrets for sensitive data",
                    )

    def _check_script_list(
        self, scripts: list[str], result: LintResult, context: str, patterns: list[tuple[str, str]]
    ) -> None:
        """Check script commands for secrets."""
        for script in scripts:
            for pattern, secret_type in patterns:
                if re.search(pattern, script):
                    self.add_violation(
                        result,
                        f"Potential {secret_type} detected in {context} script",
                        suggestion="Use GitLab protected variables or CI/CD secrets for sensitive data",
                    )


class ProtectedContextRule(LintRule):
    """Rule 13: Jobs using protected variables/environments must run only on protected branches/tags."""

    @property
    def rule_id(self) -> str:
        return "GL013"

    @property
    def description(self) -> str:
        return "Jobs with protected variables/environments must run only on protected branches"

    @property
    def category(self) -> str:
        return "security"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check protected variable usage."""
        logger.debug("Checking protected context usage in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            self._check_job_protected_context(job_name, job, result)

        logger.debug("Protected context check completed for %s", result.file_path)

    def _check_job_protected_context(self, job_name: str, job: Any, result: LintResult) -> None:
        """Check a single job for protected context usage."""
        context_details: list[str] = []

        # Check for protected environment
        self._check_protected_environment(job, context_details)

        # Check for protected variable usage
        self._check_protected_variables(job, context_details)

        # If job has protected context, ensure it has protection rules
        if context_details and not self._has_protected_branch_rules(job):
            context_str = ", ".join(context_details)
            self.add_violation(
                result,
                f"Job uses protected context ({context_str}) but lacks protected branch restriction",
                job_name=job_name,
                suggestion='Add rule: if: $CI_COMMIT_REF_PROTECTED == "true"',
            )

    def _check_protected_environment(self, job: Any, context_details: list[str]) -> None:
        """Check if job uses protected environment."""
        if not job.environment:
            return

        env_name = self._extract_environment_name(job.environment)
        if env_name and self._is_protected_environment(env_name):
            context_details.append(f"environment '{env_name}'")

    def _extract_environment_name(self, environment: Any) -> str | None:
        """Extract environment name from environment configuration."""
        if isinstance(environment, str):
            return environment
        if hasattr(environment, "name"):
            return str(environment.name)
        return None

    def _is_protected_environment(self, env_name: str) -> bool:
        """Check if environment name indicates a protected environment."""
        protected_keywords = ["prod", "production", "staging", "deploy"]
        return any(keyword in env_name.lower() for keyword in protected_keywords)

    def _check_protected_variables(self, job: Any, context_details: list[str]) -> None:
        """Check if job uses protected variables."""
        if not job.variables:
            return

        variables = self._extract_job_variables(job)
        for var_name in variables:
            if self._is_protected_variable(var_name):
                context_details.append(f"variable '{var_name}'")

    def _extract_job_variables(self, job: Any) -> dict[str, Any]:
        """Extract variables from job configuration."""
        if hasattr(job.variables, "variables"):
            return job.variables.variables or {}
        if isinstance(job.variables, dict):
            return job.variables
        return {}

    def _is_protected_variable(self, var_name: str) -> bool:
        """Check if variable name indicates a protected variable."""
        protected_keywords = ["SECRET", "TOKEN", "KEY", "PASSWORD", "DEPLOY"]
        return any(keyword in var_name.upper() for keyword in protected_keywords)

    def _has_protected_branch_rules(self, job: Any) -> bool:
        """Check if job has protected branch rules."""
        # Check new rules syntax
        if job.rules and self._check_rules_for_protection(job.rules):
            return True

        # Check legacy only syntax
        return self._check_only_for_protection(job)

    def _check_rules_for_protection(self, rules: Any) -> bool:
        """Check if rules contain protected branch conditions."""
        return any(self._rule_has_protected_condition(rule) for rule in rules)

    def _rule_has_protected_condition(self, rule: Any) -> bool:
        """Check if a rule has protected branch condition."""
        condition = None
        if hasattr(rule, "if_condition") and rule.if_condition:
            condition = rule.if_condition
        elif hasattr(rule, "if") and getattr(rule, "if"):
            condition = getattr(rule, "if")

        return bool(condition and "$CI_COMMIT_REF_PROTECTED" in condition and '"true"' in condition)

    def _check_only_for_protection(self, job: Any) -> bool:
        """Check legacy 'only' rules for protection."""
        if not (job.only and isinstance(job.only, list)):
            return False

        protected_patterns = ["main", "master", "production", "release"]
        return any(pattern in job.only for pattern in protected_patterns)


class CiDebugTraceRule(LintRule):
    """Rule 20: Prohibit CI_DEBUG_TRACE == "true" in permanent configuration."""

    @property
    def rule_id(self) -> str:
        return "GL020"

    @property
    def description(self) -> str:
        return "CI_DEBUG_TRACE must not be permanently enabled in configuration"

    @property
    def category(self) -> str:
        return "security"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check for permanently enabled CI_DEBUG_TRACE."""
        logger.debug("Checking CI_DEBUG_TRACE usage in %s", result.file_path)

        # Check global variables
        if ci_config.variables and ci_config.variables.variables:
            self._check_debug_trace_in_variables(ci_config.variables.variables, result, "global variables")

        # Check job variables
        for job_name, job in ci_config.jobs.items():
            if job.variables:
                variables: dict[str, Any] = {}
                if hasattr(job.variables, "variables"):
                    variables = job.variables.variables or {}
                elif isinstance(job.variables, dict):
                    variables = job.variables

                self._check_debug_trace_in_variables(variables, result, f"job '{job_name}'")

            # Check rules variables
            if job.rules:
                for i, rule in enumerate(job.rules):
                    if hasattr(rule, "variables") and rule.variables:
                        self._check_debug_trace_in_variables(rule.variables, result, f"job '{job_name}' rule {i}")

        logger.debug("CI_DEBUG_TRACE check completed for %s", result.file_path)

    def _check_debug_trace_in_variables(self, variables: dict[str, Any], result: LintResult, context: str) -> None:
        """Check variables for CI_DEBUG_TRACE."""
        for var_name, var_value in variables.items():
            if var_name == "CI_DEBUG_TRACE" and str(var_value).lower() in ["true", "1"]:
                self.add_violation(
                    result,
                    f"CI_DEBUG_TRACE is permanently enabled in {context}",
                    suggestion="Remove CI_DEBUG_TRACE or set it conditionally for debugging only",
                )
