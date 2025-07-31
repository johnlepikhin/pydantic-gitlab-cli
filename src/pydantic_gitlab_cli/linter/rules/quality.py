"""Quality-related lint rules."""

from __future__ import annotations

import logging
import re

from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintLevel, LintResult, LintRule

logger = logging.getLogger(__name__)


class DockerImageSizeRule(LintRule):
    """Rule 06: Warn about large Docker images (>1GB)."""

    @property
    def rule_id(self) -> str:
        return "GL006"

    @property
    def description(self) -> str:
        return "Docker images should not be excessively large (>1GB)"

    @property
    def category(self) -> str:
        return "quality"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check for potentially large Docker images."""
        logger.debug("Checking Docker image sizes in %s", result.file_path)

        large_image_patterns = self._get_large_image_patterns()

        for job_name, job in ci_config.jobs.items():
            self._check_job_image(job, job_name, large_image_patterns, result)
            self._check_service_images(job, job_name, large_image_patterns, result)

        logger.debug("Docker image size check completed for %s", result.file_path)

    def _get_large_image_patterns(self) -> list[str]:
        """Get patterns for detecting large Docker images."""
        return [
            # Full OS distributions
            r"(?i)(ubuntu:(?!.*alpine)|debian:(?!.*slim)|centos:(?!.*minimal)|fedora:(?!.*minimal))",
            # Known large base images
            r"(?i)(microsoft/dotnet|mcr\.microsoft\.com/dotnet/(?!runtime-deps))",
            r"(?i)(openjdk:(?!.*-jre)|adoptopenjdk:(?!.*-jre))",
            r"(?i)(gradle:(?!.*-alpine)|maven:(?!.*-alpine))",
            # Database images (usually large)
            r"(?i)(postgres:(?!.*-alpine)|mysql:(?!.*)|mariadb:(?!.*)|oracle/database)",
            # IDE/development images
            r"(?i)(jupyter/|tensorflow/tensorflow(?!.*-cpu)|pytorch/pytorch)",
        ]

    def _check_job_image(self, job, job_name: str, large_image_patterns: list[str], result: LintResult) -> None:
        """Check if job uses a large Docker image."""
        if not job.image:
            return

        image_name = job.image
        if isinstance(image_name, dict) and "name" in image_name:
            image_name = image_name["name"]

        if isinstance(image_name, str):
            self._check_image_against_patterns(image_name, large_image_patterns, job_name, result, "image")

    def _check_service_images(self, job, job_name: str, large_image_patterns: list[str], result: LintResult) -> None:
        """Check if job services use large Docker images."""
        if not job.services:
            return

        for service in job.services:
            service_image = self._extract_service_image_name(service)
            if service_image:
                self._check_image_against_patterns(service_image, large_image_patterns, job_name, result, "service")

    def _extract_service_image_name(self, service) -> str | None:
        """Extract image name from service specification."""
        if isinstance(service, str):
            return service
        if hasattr(service, "name"):
            return service.name
        if isinstance(service, dict) and "name" in service:
            return service["name"]
        return None

    def _check_image_against_patterns(
        self, image_name: str, patterns: list[str], job_name: str, result: LintResult, image_type: str
    ) -> None:
        """Check image name against large image patterns."""
        for pattern in patterns:
            if re.search(pattern, image_name):
                original_level = self.level
                self.level = LintLevel.WARNING
                self.add_violation(
                    result,
                    f"Potentially large Docker {image_type} detected: {image_name}",
                    job_name=job_name,
                    suggestion="Consider using Alpine-based or slim variants for smaller images",
                )
                self.level = original_level
                break  # Only report once per image


class PackageInstallationRule(LintRule):
    """Rule 07: Check for package installation in scripts (should be in Dockerfile)."""

    @property
    def rule_id(self) -> str:
        return "GL007"

    @property
    def description(self) -> str:
        return "Package installation should be done in Dockerfile, not in CI scripts"

    @property
    def category(self) -> str:
        return "quality"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check for package installation in scripts."""
        logger.debug("Checking package installation in scripts in %s", result.file_path)

        # Package installation patterns
        install_patterns = [
            r"(?i)apt-get\s+(?:update|install)",
            r"(?i)apt\s+install",
            r"(?i)yum\s+install",
            r"(?i)dnf\s+install",
            # Alpine
            r"(?i)apk\s+(?:add|update)",
            # Python packages
            r"(?i)pip\s+install(?!\s+\-e)",  # Allow pip install -e for local development
            r"(?i)pip3\s+install(?!\s+\-e)",
            # Node.js packages (global)
            r"(?i)npm\s+install\s+\-g",
            r"(?i)yarn\s+global\s+add",
            # Ruby gems (system-wide)
            r"(?i)gem\s+install(?!\s+\-\-user\-install)",
        ]

        for job_name, job in ci_config.jobs.items():
            script_sections = []

            if job.script:
                script_sections.extend([("script", cmd) for cmd in job.script])
            if job.before_script:
                script_sections.extend([("before_script", cmd) for cmd in job.before_script])
            if job.after_script:
                script_sections.extend([("after_script", cmd) for cmd in job.after_script])

            for section_name, script_command in script_sections:
                for pattern in install_patterns:
                    if re.search(pattern, script_command):
                        # Skip if it's clearly for testing or temporary purposes
                        if any(keyword in script_command.lower() for keyword in ["test", "temp", "cache"]):
                            continue

                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.WARNING
                        self.add_violation(
                            result,
                            f"Package installation detected in {section_name}: {script_command.strip()}",
                            job_name=job_name,
                            suggestion="Move package installation to Dockerfile for better caching and reproducibility",
                        )
                        self.level = original_level

        logger.debug("Package installation check completed for %s", result.file_path)


class KeyOrderRule(LintRule):
    """Rule 08: Check for proper key ordering in job definitions."""

    @property
    def rule_id(self) -> str:
        return "GL008"

    @property
    def description(self) -> str:
        return "Job keys should follow recommended ordering for better readability"

    @property
    def category(self) -> str:
        return "quality"

    def _get_recommended_key_order(self) -> list[str]:
        """Get recommended key order for GitLab CI jobs."""
        return [
            "extends",
            "stage",
            "image",
            "services",
            "variables",
            "before_script",
            "script",
            "after_script",
            "environment",
            "when",
            "allow_failure",
            "timeout",
            "dependencies",
            "needs",
            "rules",
            "only",
            "except",
            "cache",
            "artifacts",
            "coverage",
            "retry",
        ]

    def _check_job_key_order(self, job_name: str, job, result: LintResult, order_map: dict[str, int]) -> None:
        """Check key ordering for a single job."""
        job_keys = self._extract_existing_job_keys(job)

        if len(job_keys) <= 3:  # Skip jobs with very few keys
            return

        ordered_keys = sorted(job_keys, key=lambda k: order_map.get(k, 999))

        if job_keys != ordered_keys:
            current_order = " → ".join(job_keys)
            recommended_order = " → ".join(ordered_keys)

            self.add_violation(
                result,
                f"Job '{job_name}' keys are not in recommended order",
                job_name=job_name,
                suggestion=f"Reorder keys: {recommended_order} (current: {current_order})",
            )

    def _extract_existing_job_keys(self, job) -> list[str]:
        """Extract list of keys that exist in this job."""
        job_keys = []

        # Define key mapping with conditions
        key_checks = [
            ("extends", lambda j: hasattr(j, "extends") and j.extends),
            ("stage", lambda j: hasattr(j, "stage") and j.stage),
            ("image", lambda j: hasattr(j, "image") and j.image),
            ("services", lambda j: hasattr(j, "services") and j.services),
            ("variables", lambda j: hasattr(j, "variables") and j.variables),
            ("before_script", lambda j: hasattr(j, "before_script") and j.before_script),
            ("script", lambda j: hasattr(j, "script") and j.script),
            ("after_script", lambda j: hasattr(j, "after_script") and j.after_script),
            ("environment", lambda j: hasattr(j, "environment") and j.environment),
            ("when", lambda j: hasattr(j, "when") and j.when),
            ("allow_failure", lambda j: hasattr(j, "allow_failure") and j.allow_failure is not None),
            ("timeout", lambda j: hasattr(j, "timeout") and j.timeout),
            ("dependencies", lambda j: hasattr(j, "dependencies") and j.dependencies),
            ("needs", lambda j: hasattr(j, "needs") and j.needs),
            ("rules", lambda j: hasattr(j, "rules") and j.rules),
            ("only", lambda j: hasattr(j, "only") and j.only),
            ("except", lambda j: hasattr(j, "except_") and j.except_),
            ("cache", lambda j: hasattr(j, "cache") and j.cache),
            ("artifacts", lambda j: hasattr(j, "artifacts") and j.artifacts),
            ("coverage", lambda j: hasattr(j, "coverage") and j.coverage),
            ("retry", lambda j: hasattr(j, "retry") and j.retry),
        ]

        for key_name, check_func in key_checks:
            if check_func(job):
                job_keys.append(key_name)

        return job_keys

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check job key ordering."""
        logger.debug("Checking job key ordering in %s", result.file_path)

        recommended_order = self._get_recommended_key_order()
        order_map = {key: i for i, key in enumerate(recommended_order)}

        for job_name, job in ci_config.jobs.items():
            self._check_job_key_order(job_name, job, result, order_map)

        logger.debug("Key ordering check completed for %s", result.file_path)


class CacheRule(LintRule):
    """Rule 09: Check cache configuration (key requirements)."""

    @property
    def rule_id(self) -> str:
        return "GL009"

    @property
    def description(self) -> str:
        return "Cache configuration must have appropriate key and paths"

    @property
    def category(self) -> str:
        return "quality"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check cache configuration."""
        logger.debug("Checking cache configuration in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            if job.cache:
                cache_configs = job.cache if isinstance(job.cache, list) else [job.cache]

                for i, cache_config in enumerate(cache_configs):
                    f"cache {i}" if len(cache_configs) > 1 else "cache"

                    # Check if cache has a key
                    cache_key = None
                    if hasattr(cache_config, "key"):
                        cache_key = cache_config.key
                    elif isinstance(cache_config, dict) and "key" in cache_config:
                        cache_key = cache_config["key"]

                    if not cache_key:
                        self.add_violation(
                            result,
                            "Cache configuration missing key",
                            job_name=job_name,
                            suggestion="Add cache key for better cache isolation and performance",
                        )
                        continue

                    # Check if cache key is too generic
                    if isinstance(cache_key, str):
                        generic_keys = ["cache", "build", "deps", "dependencies"]
                        if cache_key.lower() in generic_keys:
                            # Temporarily change level for this violation
                            original_level = self.level
                            self.level = LintLevel.WARNING
                            self.add_violation(
                                result,
                                f"Cache key is too generic: '{cache_key}'",
                                job_name=job_name,
                                suggestion="Use more specific cache keys like '$CI_COMMIT_REF_SLUG-deps' or file-based keys",
                            )
                            self.level = original_level

                    # Check if cache has paths
                    cache_paths = None
                    if hasattr(cache_config, "paths"):
                        cache_paths = cache_config.paths
                    elif isinstance(cache_config, dict) and "paths" in cache_config:
                        cache_paths = cache_config["paths"]

                    if not cache_paths:
                        self.add_violation(
                            result,
                            "Cache configuration missing paths",
                            job_name=job_name,
                            suggestion="Specify cache paths to define what should be cached",
                        )

        logger.debug("Cache configuration check completed for %s", result.file_path)


class ArtifactsExpirationRule(LintRule):
    """Rule 10: Check artifacts expiration settings."""

    @property
    def rule_id(self) -> str:
        return "GL010"

    @property
    def description(self) -> str:
        return "Artifacts should have appropriate expiration settings to save storage"

    @property
    def category(self) -> str:
        return "quality"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check artifacts expiration."""
        logger.debug("Checking artifacts expiration in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            if job.artifacts:
                expire_in = None
                if hasattr(job.artifacts, "expire_in"):
                    expire_in = job.artifacts.expire_in
                elif isinstance(job.artifacts, dict) and "expire_in" in job.artifacts:
                    expire_in = job.artifacts["expire_in"]

                if not expire_in:
                    # Check if this is a release or deployment job (might need longer retention)
                    is_release_job = any(
                        keyword in job_name.lower() for keyword in ["release", "deploy", "production", "publish"]
                    )

                    if not is_release_job:
                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.WARNING
                        self.add_violation(
                            result,
                            "Artifacts missing expiration setting",
                            job_name=job_name,
                            suggestion="Add 'expire_in' to artifacts configuration (e.g., '1 week', '30 days')",
                        )
                        self.level = original_level
                else:
                    # Check for very long expiration periods
                    expire_str = str(expire_in).lower()
                    if any(long_period in expire_str for long_period in ["year", "years", "never"]):
                        # Temporarily change level for this violation
                        original_level = self.level
                        self.level = LintLevel.INFO
                        self.add_violation(
                            result,
                            f"Artifacts have very long expiration: {expire_in}",
                            job_name=job_name,
                            suggestion="Consider shorter expiration periods to save storage costs",
                        )
                        self.level = original_level

        logger.debug("Artifacts expiration check completed for %s", result.file_path)


class InterruptibleFailFastRule(LintRule):
    """Rule 11: Check for fail-fast behavior with interruptible jobs."""

    @property
    def rule_id(self) -> str:
        return "GL011"

    @property
    def description(self) -> str:
        return "Long-running jobs should be interruptible for fail-fast behavior"

    @property
    def category(self) -> str:
        return "quality"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check for interruptible configuration."""
        logger.debug("Checking interruptible configuration in %s", result.file_path)

        for job_name, job in ci_config.jobs.items():
            # Check for jobs that might benefit from being interruptible
            is_long_running = False

            # Check timeout (if explicitly set to long duration)
            if job.timeout:
                timeout_str = str(job.timeout).lower()
                if any(long_duration in timeout_str for long_duration in ["hour", "hours", "h"]):
                    is_long_running = True

            # Check for test jobs (typically good candidates for interruption)
            is_test_job = any(keyword in job_name.lower() for keyword in ["test", "spec", "check", "lint", "verify"])

            # Check for build jobs that might be long-running
            is_build_job = any(keyword in job_name.lower() for keyword in ["build", "compile", "package"])

            if is_long_running or is_test_job or is_build_job:
                # Check if job is marked as interruptible
                is_interruptible = False
                if hasattr(job, "interruptible"):
                    is_interruptible = job.interruptible
                elif hasattr(job, "interruptible") and job.interruptible is not None:
                    is_interruptible = bool(job.interruptible)

                # Skip deployment/release jobs (should not be interrupted)
                is_deployment = any(
                    keyword in job_name.lower() for keyword in ["deploy", "release", "publish", "production"]
                )

                if not is_interruptible and not is_deployment:
                    job_type = "test" if is_test_job else "build" if is_build_job else "long-running"

                    # Temporarily change level for this violation
                    original_level = self.level
                    self.level = LintLevel.INFO
                    self.add_violation(
                        result,
                        f"Consider making {job_type} job interruptible for fail-fast behavior",
                        job_name=job_name,
                        suggestion="Add 'interruptible: true' to allow cancellation when new commits are pushed",
                    )
                    self.level = original_level

        logger.debug("Interruptible configuration check completed for %s", result.file_path)
