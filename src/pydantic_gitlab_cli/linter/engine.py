"""Lint engine for processing GitLab CI configurations."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError
from pydantic_gitlab import GitLabCI

from .base import LintLevel, LintResult, LintRule
from .config import ConfigLoader, LinterConfig

logger = logging.getLogger(__name__)


class LintEngine:
    """Engine for running lint rules against GitLab CI configurations."""

    def __init__(self, config: LinterConfig | str | Path | None = None):
        """
        Initialize the lint engine.

        Args:
            config: Configuration object, path to config file, or None for auto-discovery
        """
        self.rules: dict[str, LintRule] = {}
        self.config_loader = ConfigLoader()

        # Load configuration
        if isinstance(config, LinterConfig):
            self.config = config
        elif isinstance(config, (str, Path)):
            self.config = self.config_loader.load_config(config)
        else:
            self.config = self.config_loader.load_config()

        logger.info("Initialized lint engine with configuration")

    def register_rule(self, rule: LintRule) -> None:
        """
        Register a lint rule with the engine.

        Args:
            rule: Rule instance to register
        """
        if rule.rule_id in self.rules:
            logger.warning("Rule %s already registered, replacing with new instance", rule.rule_id)

        # Apply configuration to rule
        rule_config = self.config_loader.get_rule_config(rule.rule_id)
        rule.enabled = self.config_loader.is_rule_enabled(rule.rule_id, rule.category)
        rule.level = rule_config.level

        self.rules[rule.rule_id] = rule
        logger.debug(
            "Registered rule %s: %s (enabled=%s, level=%s)",
            rule.rule_id,
            rule.description,
            rule.enabled,
            rule.level.value,
        )

    def register_rules(self, rules: list[LintRule]) -> None:
        """
        Register multiple lint rules.

        Args:
            rules: List of rule instances to register
        """
        for rule in rules:
            self.register_rule(rule)

    def get_rule(self, rule_id: str) -> LintRule | None:
        """
        Get a rule by ID.

        Args:
            rule_id: Rule identifier

        Returns:
            Rule instance if found, None otherwise
        """
        return self.rules.get(rule_id)

    def list_rules(self) -> list[LintRule]:
        """
        Get list of all registered rules.

        Returns:
            List of all registered rules
        """
        return list(self.rules.values())

    def configure_rule(self, rule_id: str, enabled: bool, level: LintLevel | None = None) -> bool:
        """
        Configure a rule's enabled state and level.

        Args:
            rule_id: Rule identifier
            enabled: Whether rule should be enabled
            level: New level for the rule (optional)

        Returns:
            True if rule was configured, False if rule not found
        """
        rule = self.rules.get(rule_id)
        if not rule:
            logger.warning("Attempted to configure unknown rule: %s", rule_id)
            return False

        old_enabled = rule.enabled
        old_level = rule.level

        rule.enabled = enabled
        if level is not None:
            rule.level = level

        logger.info(
            "Configured rule %s: enabled %s->%s, level %s->%s",
            rule_id,
            old_enabled,
            enabled,
            old_level.value if old_level else None,
            rule.level.value,
        )

        return True

    def _parse_gitlab_ci_file(self, file_path: Path, strict: bool) -> tuple[GitLabCI | None, str | None]:
        """Parse GitLab CI file and return config or error message."""
        error_msg = None
        ci_config = None

        try:
            with file_path.open(encoding="utf-8") as f:
                yaml_content = f.read()

            # Parse YAML
            yaml_data = None
            try:
                yaml_data = yaml.safe_load(yaml_content)
                if yaml_data is None:
                    logger.warning("Empty YAML file: %s", file_path)
                    error_msg = "File is empty or contains only comments"
            except yaml.YAMLError as e:
                logger.error("YAML parsing failed for %s: %s", file_path, e)
                error_msg = f"YAML parsing error: {e}"

            # Parse with pydantic-gitlab if YAML parsing succeeded
            if error_msg is None and yaml_data is not None:
                try:
                    ci_config = GitLabCI(**yaml_data)
                    logger.debug("Successfully parsed GitLab CI config from %s", file_path)
                except ValidationError as e:
                    if strict:
                        logger.error("GitLab CI validation failed for %s: %s", file_path, e)
                        error_msg = f"GitLab CI validation error: {e}"
                    else:
                        # In non-strict mode, try to create a partial config
                        logger.warning("GitLab CI validation warnings for %s: %s", file_path, e)
                        # For now, still fail parsing - we can improve this later
                        error_msg = f"GitLab CI validation error: {e}"

        except FileNotFoundError:
            logger.error("File not found: %s", file_path)
            error_msg = f"File not found: {file_path}"
        except Exception as e:
            logger.error("Unexpected error reading %s: %s", file_path, e)
            error_msg = f"Unexpected error reading file: {e}"

        return ci_config, error_msg

    def lint_file(self, file_path: Path, strict: bool | None = None) -> LintResult:
        """
        Lint a single GitLab CI YAML file.

        Args:
            file_path: Path to the YAML file
            strict: Whether to use strict validation mode (overrides config)

        Returns:
            Lint result with any violations found
        """
        result = LintResult(file_path=file_path)

        # Use config strict mode if not explicitly provided
        if strict is None:
            strict = self.config.strict_mode

        logger.info("Linting file: %s (strict=%s)", file_path, strict)

        # Parse the file
        ci_config, parse_error = self._parse_gitlab_ci_file(file_path, strict)
        if parse_error:
            result.parse_error = parse_error
            return result

        # Run all enabled rules
        enabled_rules = [rule for rule in self.rules.values() if rule.enabled]
        logger.debug("Running %d enabled rules", len(enabled_rules))

        for rule in enabled_rules:
            try:
                if rule.is_applicable(ci_config):
                    logger.debug("Running rule %s", rule.rule_id)
                    rule.check(ci_config, result)
                else:
                    logger.debug("Skipping rule %s (not applicable)", rule.rule_id)

            except Exception as e:
                logger.error(
                    "Rule %s failed with error: %s",
                    rule.rule_id,
                    e,
                    extra={"rule_id": rule.rule_id, "file_path": str(file_path)},
                )
                # Add a violation for the rule failure
                result.add_violation(
                    rule_id=rule.rule_id,
                    level=LintLevel.ERROR,
                    message=f"Rule execution failed: {e}",
                )

        logger.info(
            "Completed linting %s: %d errors, %d warnings, %d info",
            file_path,
            result.error_count,
            result.warning_count,
            result.info_count,
        )

        return result

    def lint_files(self, file_paths: list[Path], strict: bool | None = None) -> list[LintResult]:
        """
        Lint multiple GitLab CI YAML files.

        Args:
            file_paths: List of paths to YAML files
            strict: Whether to use strict validation mode (overrides config)

        Returns:
            List of lint results, one per file
        """
        results = []

        logger.info("Linting %d files", len(file_paths))

        for file_path in file_paths:
            result = self.lint_file(file_path, strict=strict)
            results.append(result)

        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)
        total_info = sum(r.info_count for r in results)

        logger.info(
            "Completed linting %d files: %d errors, %d warnings, %d info",
            len(file_paths),
            total_errors,
            total_warnings,
            total_info,
        )

        # Apply configuration constraints
        return self._apply_config_constraints(results)

    def _apply_config_constraints(self, results: list[LintResult]) -> list[LintResult]:
        """Apply configuration constraints to results."""
        if not self.config:
            return results

        for result in results:
            # Apply max_violations limit
            if self.config.max_violations and len(result.violations) > self.config.max_violations:
                logger.info(f"Truncating violations for {result.file_path} to {self.config.max_violations}")
                result.violations = result.violations[: self.config.max_violations]

        return results

    def should_fail(self, results: list[LintResult]) -> bool:
        """
        Determine if linting should result in failure based on configuration.

        Args:
            results: List of lint results

        Returns:
            True if should fail (exit with error code)
        """
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)

        # Always fail on errors
        if total_errors > 0:
            return True

        # Fail on warnings if configured
        return bool(self.config.fail_on_warnings and total_warnings > 0)
