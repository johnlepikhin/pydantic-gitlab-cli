"""Configuration system for GitLab CI linter."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic import BaseModel, Field, validator

from .base import LintLevel

# Handle tomllib/tomli imports for TOML support
try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    # Python < 3.11
    try:
        import tomli as tomllib  # type: ignore[import-untyped]
    except ImportError:
        tomllib = None

logger = logging.getLogger(__name__)


class RuleConfig(BaseModel):
    """Configuration for a single rule."""

    enabled: bool = True
    level: LintLevel = LintLevel.ERROR
    options: dict[str, Any] = Field(default_factory=dict)

    @validator("level", pre=True)
    def validate_level(cls, v: Any) -> LintLevel:  # noqa: N805
        """Convert string levels to enum."""
        if isinstance(v, str):
            level_str = v.upper()
            if level_str == "ERROR":
                return LintLevel.ERROR
            if level_str == "WARNING":
                return LintLevel.WARNING
            if level_str == "INFO":
                return LintLevel.INFO
            logger.warning(f"Invalid level '{v}', using ERROR")
            return LintLevel.ERROR
        if isinstance(v, LintLevel):
            return v
        # Default case - return ERROR for invalid values
        logger.warning(f"Invalid level type '{type(v)}', using ERROR")
        return LintLevel.ERROR


class LinterConfig(BaseModel):
    """Main linter configuration."""

    # Global settings
    strict_mode: bool = False
    max_violations: int | None = None
    fail_on_warnings: bool = False

    # Rule configurations
    rules: dict[str, RuleConfig] = Field(default_factory=dict)

    # Categories to enable/disable
    categories: dict[str, bool] = Field(default_factory=dict)

    # Files to include/exclude
    include_patterns: list[str] = Field(default_factory=lambda: ["*.gitlab-ci.yml", ".gitlab-ci.yml"])
    exclude_patterns: list[str] = Field(default_factory=list)

    @validator("rules", pre=True)
    def validate_rules(cls, v: Any) -> dict[str, RuleConfig]:  # noqa: N805
        """Validate and normalize rule configurations."""
        if not isinstance(v, dict):
            return {}

        normalized = {}
        for rule_id, config in v.items():
            if isinstance(config, dict):
                # RuleConfig validator will handle level conversion
                normalized[rule_id] = RuleConfig(**config)
            elif isinstance(config, bool):
                # Simple boolean config
                normalized[rule_id] = RuleConfig(enabled=config)
            else:
                logger.warning(f"Invalid config for rule {rule_id}: {config}")
                normalized[rule_id] = RuleConfig()

        return normalized


class ConfigLoader:
    """Loads and manages linter configuration."""

    DEFAULT_CONFIG_FILES: ClassVar[list[str]] = [
        ".gitlab-ci-lint.yml",
        ".gitlab-ci-lint.yaml",
        ".gitlab-ci-lint.json",
        "pyproject.toml",  # Support for pyproject.toml [tool.gitlab-ci-lint] section
    ]

    def __init__(self) -> None:
        self.config: LinterConfig | None = None
        self._config_path: Path | None = None

    def load_config(self, config_path: str | Path | None = None) -> LinterConfig:
        """
        Load configuration from file or use defaults.

        Args:
            config_path: Explicit path to config file, or None to auto-discover

        Returns:
            Loaded configuration
        """
        if config_path:
            config_path = Path(config_path)
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")

            self.config = self._load_from_file(config_path)
            self._config_path = config_path

        else:
            # Auto-discover config file
            self.config = self._auto_discover_config()

        if not self.config:
            logger.info("No configuration file found, using defaults")
            self.config = LinterConfig()

        # Apply default rule configurations
        self._apply_default_rules()

        logger.info(f"Loaded configuration with {len(self.config.rules)} rule configurations")
        return self.config

    def _auto_discover_config(self) -> LinterConfig | None:
        """Auto-discover configuration file in current directory."""
        current_dir = Path.cwd()

        for config_file in self.DEFAULT_CONFIG_FILES:
            config_path = current_dir / config_file
            if config_path.exists():
                logger.info(f"Found configuration file: {config_path}")
                self._config_path = config_path
                return self._load_from_file(config_path)

        return None

    def _load_from_file(self, config_path: Path) -> LinterConfig:
        """Load configuration from a specific file."""
        try:
            with config_path.open(encoding="utf-8") as f:
                if config_path.suffix in [".yml", ".yaml"]:
                    data = yaml.safe_load(f)
                elif config_path.suffix == ".json":
                    data = json.load(f)
                elif config_path.name == "pyproject.toml":
                    if tomllib is None:
                        raise ImportError("TOML support requires 'tomli' package for Python < 3.11")

                    with config_path.open("rb") as toml_file:
                        toml_data = tomllib.load(toml_file)
                        data = toml_data.get("tool", {}).get("gitlab-ci-lint", {})
                else:
                    raise ValueError(f"Unsupported config file format: {config_path.suffix}")

            return LinterConfig(**data)

        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise

    def _apply_default_rules(self) -> None:
        """Apply default configurations for rules not explicitly configured."""
        if not self.config:
            return

        # Default rule configurations
        default_rules = {
            # High priority errors
            "GL001": RuleConfig(enabled=True, level=LintLevel.ERROR),
            "GL002": RuleConfig(enabled=True, level=LintLevel.ERROR),
            "GL004": RuleConfig(enabled=True, level=LintLevel.ERROR),
            "GL005": RuleConfig(enabled=True, level=LintLevel.ERROR),
            "GL012": RuleConfig(enabled=True, level=LintLevel.ERROR),
            "GL013": RuleConfig(enabled=True, level=LintLevel.ERROR),
            "GL020": RuleConfig(enabled=True, level=LintLevel.ERROR),
            "GL022": RuleConfig(enabled=True, level=LintLevel.ERROR),
            # Warnings
            "GL003": RuleConfig(enabled=True, level=LintLevel.WARNING),
            "GL006": RuleConfig(enabled=True, level=LintLevel.WARNING),
            "GL007": RuleConfig(enabled=True, level=LintLevel.WARNING),
            "GL009": RuleConfig(enabled=True, level=LintLevel.WARNING),
            "GL010": RuleConfig(enabled=True, level=LintLevel.WARNING),
            "GL016": RuleConfig(enabled=True, level=LintLevel.WARNING),
            "GL018": RuleConfig(enabled=True, level=LintLevel.WARNING),
            "GL019": RuleConfig(enabled=True, level=LintLevel.WARNING),
            # Info/optional
            "GL008": RuleConfig(enabled=True, level=LintLevel.INFO),
            "GL011": RuleConfig(enabled=True, level=LintLevel.INFO),
            "GL014": RuleConfig(enabled=True, level=LintLevel.INFO),
            "GL015": RuleConfig(enabled=True, level=LintLevel.INFO),
            "GL017": RuleConfig(enabled=True, level=LintLevel.INFO),
            # Parallel matrix limit
            "GL033": RuleConfig(enabled=True, level=LintLevel.ERROR),
        }

        # Apply defaults for rules not explicitly configured
        for rule_id, default_config in default_rules.items():
            if rule_id not in self.config.rules:
                self.config.rules[rule_id] = default_config

    def get_rule_config(self, rule_id: str) -> RuleConfig:
        """
        Get configuration for a specific rule.

        Args:
            rule_id: Rule identifier

        Returns:
            Rule configuration
        """
        if not self.config:
            return RuleConfig()

        return self.config.rules.get(rule_id, RuleConfig())

    def is_rule_enabled(self, rule_id: str, category: str | None = None) -> bool:
        """
        Check if a rule is enabled based on configuration.

        Args:
            rule_id: Rule identifier
            category: Rule category (optional)

        Returns:
            True if rule should be enabled
        """
        if not self.config:
            return True

        # Check category-level setting first
        if category and category in self.config.categories and not self.config.categories[category]:
            return False

        # Check rule-specific setting
        rule_config = self.get_rule_config(rule_id)
        return rule_config.enabled

    def save_config(self, output_path: str | Path | None = None) -> Path:
        """
        Save current configuration to file.

        Args:
            output_path: Path to save config, or None to use current config path

        Returns:
            Path where config was saved
        """
        if not self.config:
            raise ValueError("No configuration loaded")

        if output_path:
            save_path = Path(output_path)
        elif self._config_path:
            save_path = self._config_path
        else:
            save_path = Path.cwd() / ".gitlab-ci-lint.yml"

        # Convert config to dict for serialization
        config_dict = self.config.dict()

        # Convert enum values to strings
        for _rule_id, rule_config in config_dict["rules"].items():
            if isinstance(rule_config["level"], str):
                rule_config["level"] = rule_config["level"].lower()

        try:
            with save_path.open("w", encoding="utf-8") as f:
                if save_path.suffix == ".json":
                    json.dump(config_dict, f, indent=2)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)

            logger.info(f"Configuration saved to {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Failed to save config to {save_path}: {e}")
            raise


def create_default_config() -> str:
    """Create a default configuration file content."""
    config = {
        "strict_mode": False,
        "fail_on_warnings": False,
        "max_violations": None,
        "categories": {"security": True, "quality": True, "optimization": True, "structure": True},
        "rules": {
            # Critical errors
            "GL001": {"enabled": True, "level": "error"},
            "GL002": {"enabled": True, "level": "error"},
            "GL004": {"enabled": True, "level": "error"},
            "GL005": {"enabled": True, "level": "error"},
            "GL012": {"enabled": True, "level": "error"},
            "GL013": {"enabled": True, "level": "error"},
            "GL020": {"enabled": True, "level": "error"},
            "GL022": {"enabled": True, "level": "error"},
            # Warnings
            "GL003": {"enabled": True, "level": "warning"},
            "GL006": {"enabled": True, "level": "warning"},
            "GL007": {"enabled": True, "level": "warning"},
            "GL009": {"enabled": True, "level": "warning"},
            "GL010": {"enabled": True, "level": "warning"},
            # Optional optimizations (can be disabled for faster linting)
            "GL008": {"enabled": False, "level": "info"},  # Key ordering
            "GL011": {"enabled": False, "level": "info"},  # Interruptible
            "GL014": {"enabled": False, "level": "info"},  # Variable optimization
            "GL015": {"enabled": False, "level": "info"},  # Parallelization
            "GL017": {"enabled": False, "level": "info"},  # Job reuse
            # Parallel matrix limit check
            "GL033": {"enabled": True, "level": "error"},  # Matrix job limit
        },
        "include_patterns": ["*.gitlab-ci.yml", ".gitlab-ci.yml"],
        "exclude_patterns": ["**/node_modules/**", "**/vendor/**"],
    }

    return yaml.dump(config, default_flow_style=False, indent=2)
