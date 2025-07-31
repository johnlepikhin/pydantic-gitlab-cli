"""Include-related lint rules."""

import logging
import re

from pydantic_gitlab import GitLabCI
from pydantic_gitlab.include import GitLabCIInclude, GitLabCIIncludeProject, GitLabCIIncludeRemote

from pydantic_gitlab_cli.linter.base import LintResult, LintRule

logger = logging.getLogger(__name__)


class IncludeVersioningRule(LintRule):
    """Rule 04: Includes from other repos must contain ref: with tag/commit, not branch main/latest."""

    @property
    def rule_id(self) -> str:
        return "GL004"

    @property
    def description(self) -> str:
        return "External includes must use specific ref (tag/commit), not branch main/latest"

    @property
    def category(self) -> str:
        return "includes"

    def check(self, ci_config: GitLabCI, result: LintResult) -> None:
        """Check include versioning."""
        logger.debug("Checking include versioning for %s", result.file_path)

        if not ci_config.include:
            logger.debug("No includes found, skipping versioning check")
            return

        includes = ci_config.include
        if not isinstance(includes, list):
            includes = [includes]

        for i, include in enumerate(includes):
            self._check_single_include(include, result, i)

        logger.debug("Include versioning check completed for %s", result.file_path)

    def _check_single_include(self, include: GitLabCIInclude, result: LintResult, _index: int) -> None:
        """Check a single include for versioning issues."""

        # Check project includes
        if isinstance(include, GitLabCIIncludeProject) or hasattr(include, "project"):
            project = getattr(include, "project", None)
            file_path = getattr(include, "file", None)
            ref = getattr(include, "ref", None)

            if project and file_path:
                if not ref:
                    self.add_violation(
                        result,
                        f"Project include missing 'ref' specification: {project}",
                        suggestion="Add 'ref: v1.0.0' or 'ref: commit-hash' for reproducible builds",
                    )
                elif self._is_unstable_ref(ref):
                    self.add_violation(
                        result,
                        f"Project include uses unstable ref '{ref}': {project}",
                        suggestion="Use a specific tag (v1.0.0) or commit hash instead of branch name",
                    )

        # Check remote includes
        if isinstance(include, GitLabCIIncludeRemote) or hasattr(include, "remote"):
            remote_url = getattr(include, "remote", None)

            if remote_url:
                # Check if URL contains branch reference
                if self._has_unstable_branch_in_url(remote_url):
                    self.add_violation(
                        result,
                        f"Remote include uses unstable branch in URL: {remote_url}",
                        suggestion="Use a specific tag or commit hash in the URL",
                    )

                # Check for raw.githubusercontent.com without commit hash
                if "raw.githubusercontent.com" in remote_url and ("/main/" in remote_url or "/master/" in remote_url):
                    self.add_violation(
                        result,
                        f"GitHub raw include uses branch instead of commit: {remote_url}",
                        suggestion="Replace branch name with specific commit hash",
                    )

        # Check template includes (these are generally OK as they're maintained by GitLab)
        if hasattr(include, "template"):
            logger.debug("Template include found (generally safe): %s", include.template)

    def _is_unstable_ref(self, ref: str) -> bool:
        """Check if a ref is considered unstable (branch name)."""
        unstable_patterns = [
            "main",
            "master",
            "develop",
            "dev",
            "latest",
            # Pattern for branch-like names (not semantic versions or commit hashes)
        ]

        # If it looks like a semantic version, it's stable
        if re.match(r"^v?\d+\.\d+(\.\d+)?(-[\w\.-]+)?$", ref):
            return False

        # If it's a commit hash (40 hex chars), it's stable
        if re.match(r"^[a-f0-9]{40}$", ref):
            return False

        # If it's a short commit hash (7-12 hex chars), it's stable
        if re.match(r"^[a-f0-9]{7,12}$", ref):
            return False

        # Check against known unstable names
        if ref.lower() in unstable_patterns:
            return True

        # If it contains branch-like patterns
        if any(pattern in ref.lower() for pattern in ["branch", "head", "tip"]):
            return True

        # If it looks like a branch name (contains dashes/underscores but no version numbers)
        return bool(re.match(r"^[a-zA-Z][\w\-_]*$", ref) and not re.search(r"\d", ref))

    def _has_unstable_branch_in_url(self, url: str) -> bool:
        """Check if URL contains unstable branch references."""
        unstable_patterns = [
            "/main/",
            "/master/",
            "/develop/",
            "/dev/",
            "/latest/",
            "/heads/main",
            "/heads/master",
            "/heads/develop",
        ]

        return any(pattern in url.lower() for pattern in unstable_patterns)
