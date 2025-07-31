"""Docker-related lint rules."""

from __future__ import annotations

import logging
import re

from pydantic_gitlab import GitLabCI
from pydantic_gitlab.services import GitLabCIImage, GitLabCIImageObject

from pydantic_gitlab_cli.linter.base import LintResult, LintRule

logger = logging.getLogger(__name__)


class DockerLatestTagRule(LintRule):
    """Rule 05: Prohibit :latest tag; require fixed version (semantic or digest)."""

    @property
    def rule_id(self) -> str:
        return "GL005"

    @property
    def description(self) -> str:
        return "Docker images must not use ':latest' tag; use fixed version or digest"

    @property
    def category(self) -> str:
        return "docker"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check for prohibited :latest Docker tags."""
        logger.debug("Checking Docker image tags for %s", result.file_path)

        # Check default image
        if ci_config.default and ci_config.default.image:
            self._check_image(ci_config.default.image, result, "default")

        # Check job images and services
        for job_name, job in ci_config.jobs.items():
            # Check job image
            if job.image:
                self._check_image(job.image, result, f"job '{job_name}'")

            # Check job services
            if job.services:
                for i, service in enumerate(job.services):
                    service_name = f"job '{job_name}' service {i}"
                    if isinstance(service, str):
                        self._check_image_string(service, result, service_name)
                    else:
                        self._check_image(service.name, result, service_name)

        logger.debug("Docker image tags check completed for %s", result.file_path)

    def _check_image(self, image: str | GitLabCIImage | GitLabCIImageObject, result: LintResult, context: str) -> None:
        """Check a single image specification."""
        if isinstance(image, str):
            self._check_image_string(image, result, context)
        elif hasattr(image, "name"):
            self._check_image_string(image.name, result, context)
        else:
            logger.warning("Unknown image type: %s", type(image))

    def _check_image_string(self, image_str: str, result: LintResult, context: str) -> None:
        """Check a Docker image string for :latest tag."""
        if not image_str:
            return

        # Skip variable references - we can't validate them statically
        if "$" in image_str:
            logger.debug("Skipping variable-based image: %s", image_str)
            return

        # Check for explicit :latest tag
        if image_str.endswith(":latest"):
            self.add_violation(
                result,
                f"Image in {context} uses prohibited ':latest' tag: {image_str}",
                suggestion=f"Replace with specific version, e.g., '{image_str.replace(':latest', ':3.11')}'",
            )
            return

        # Check for images without any tag (implicit :latest)
        # Pattern: registry/image or just image (no tag)
        if ":" not in image_str.split("/")[-1]:  # No tag in the image name part
            # Some exceptions for official images that have default tags
            official_exceptions = {
                "scratch",  # Special base image
                "alpine",  # Often has a default
            }

            image_name = image_str.split("/")[-1]
            if image_name not in official_exceptions:
                self.add_violation(
                    result,
                    f"Image in {context} has no tag (implicit :latest): {image_str}",
                    suggestion=f"Add specific version tag, e.g., '{image_str}:3.11'",
                )

        # Check for digest format (sha256:...)
        if "@sha256:" in image_str:
            logger.debug("Image uses digest format (good): %s", image_str)
            return

        # Check for semantic versioning pattern
        version_pattern = r":v?\d+(\.\d+)*(-[\w\.-]+)?$"
        if re.search(version_pattern, image_str):
            logger.debug("Image uses version tag (good): %s", image_str)
            return
