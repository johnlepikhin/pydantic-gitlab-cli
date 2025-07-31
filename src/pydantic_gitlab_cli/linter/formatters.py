"""Output formatters for lint results."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import LintLevel, LintResult, LintViolation

logger = logging.getLogger(__name__)


class BaseFormatter:
    """Base class for output formatters."""

    def format(self, results: list[LintResult], **_kwargs: Any) -> str:
        """Format lint results."""
        raise NotImplementedError


class JSONFormatter(BaseFormatter):
    """JSON output formatter."""

    def format(self, results: list[LintResult], **_kwargs: Any) -> str:
        """Format results as JSON."""
        logger.debug("Formatting %d results as JSON", len(results))

        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "tool": {"name": "pydantic-gitlab-cli", "version": "0.1.0"},
            "summary": self._generate_summary(results),
            "results": [self._format_result(result) for result in results],
        }

        return json.dumps(output, indent=2, ensure_ascii=False)

    def _generate_summary(self, results: list[LintResult]) -> dict[str, Any]:
        """Generate summary statistics."""
        total_files = len(results)
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)
        total_info = sum(r.info_count for r in results)
        total_violations = sum(len(r.violations) for r in results)

        files_with_issues = sum(1 for r in results if r.violations or r.parse_error)

        return {
            "total_files": total_files,
            "files_with_issues": files_with_issues,
            "total_violations": total_violations,
            "errors": total_errors,
            "warnings": total_warnings,
            "info": total_info,
        }

    def _format_result(self, result: LintResult) -> dict[str, Any]:
        """Format a single lint result."""
        formatted: dict[str, Any] = {
            "file": str(result.file_path),
            "status": "error" if result.parse_error else "success" if not result.violations else "issues",
        }

        if result.parse_error:
            formatted["parse_error"] = result.parse_error

        if result.violations:
            formatted["violations"] = [self._format_violation(v) for v in result.violations]

        formatted["summary"] = {
            "errors": result.error_count,
            "warnings": result.warning_count,
            "info": result.info_count,
        }

        return formatted

    def _format_violation(self, violation: LintViolation) -> dict[str, Any]:
        """Format a single violation."""
        formatted: dict[str, Any] = {
            "rule_id": violation.rule_id,
            "level": violation.level.value.lower(),
            "message": violation.message,
        }

        if violation.line is not None:
            formatted["line"] = violation.line

        if violation.column is not None:
            formatted["column"] = violation.column

        if violation.job_name:
            formatted["job_name"] = violation.job_name

        if violation.suggestion:
            formatted["suggestion"] = violation.suggestion

        return formatted


class SARIFFormatter(BaseFormatter):
    """SARIF 2.1.0 output formatter."""

    def format(self, results: list[LintResult], **_kwargs: Any) -> str:
        """Format results as SARIF 2.1.0."""
        logger.debug("Formatting %d results as SARIF", len(results))

        # Group violations by rule for SARIF rules section
        rules_map = {}
        all_results = []

        for result in results:
            if result.parse_error:
                # Add parse error as a result
                all_results.append(
                    {
                        "ruleId": "PARSE_ERROR",
                        "level": "error",
                        "message": {"text": result.parse_error},
                        "locations": [{"physicalLocation": {"artifactLocation": {"uri": str(result.file_path)}}}],
                    }
                )

                # Ensure parse error rule is in rules map
                if "PARSE_ERROR" not in rules_map:
                    rules_map["PARSE_ERROR"] = {
                        "id": "PARSE_ERROR",
                        "name": "ParseError",
                        "shortDescription": {"text": "YAML parsing error"},
                        "fullDescription": {"text": "The YAML file could not be parsed"},
                        "help": {"text": "Fix YAML syntax errors"},
                        "properties": {"category": "syntax"},
                    }

            for violation in result.violations:
                # Add rule to rules map
                if violation.rule_id not in rules_map:
                    rules_map[violation.rule_id] = self._create_sarif_rule(violation)

                # Add result
                sarif_result = self._create_sarif_result(violation, result.file_path)
                all_results.append(sarif_result)

        # Build SARIF document
        sarif_doc = {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "pydantic-gitlab-cli",
                            "version": "0.1.0",
                            "informationUri": "https://github.com/johnlepikhin/pydantic-gitlab-cli",
                            "rules": list(rules_map.values()),
                        }
                    },
                    "results": all_results,
                    "invocation": {
                        "executionSuccessful": sum(r.error_count for r in results) == 0,
                        "startTimeUtc": datetime.now(timezone.utc).isoformat(),
                    },
                }
            ],
        }

        return json.dumps(sarif_doc, indent=2, ensure_ascii=False)

    def _create_sarif_rule(self, violation: LintViolation) -> dict[str, Any]:
        """Create a SARIF rule definition from a violation."""
        rule = {
            "id": violation.rule_id,
            "name": violation.rule_id.replace("GL", "GitLabRule"),
            "shortDescription": {"text": violation.message.split(".")[0]},
            "fullDescription": {"text": violation.message},
            "defaultConfiguration": {"level": self._map_level_to_sarif(violation.level)},
            "properties": {"category": "gitlab-ci"},
        }

        if violation.suggestion:
            rule["help"] = {"text": violation.suggestion}

        return rule

    def _create_sarif_result(self, violation: LintViolation, file_path: Path) -> dict[str, Any]:
        """Create a SARIF result from a violation."""
        result: dict[str, Any] = {
            "ruleId": violation.rule_id,
            "level": self._map_level_to_sarif(violation.level),
            "message": {"text": violation.message},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": str(file_path)}}}],
        }

        # Add line/column information if available
        if violation.line is not None:
            physical_location = result["locations"][0]["physicalLocation"]
            physical_location["region"] = {"startLine": violation.line}

            if violation.column is not None:
                physical_location["region"]["startColumn"] = violation.column

        # Add job context if available
        if violation.job_name:
            result["properties"] = {"job_name": violation.job_name}

        return result

    def _map_level_to_sarif(self, level: LintLevel) -> str:
        """Map lint level to SARIF level."""
        mapping = {LintLevel.ERROR: "error", LintLevel.WARNING: "warning", LintLevel.INFO: "note"}
        return mapping.get(level, "warning")


class JUnitFormatter(BaseFormatter):
    """JUnit XML output formatter for CI integration."""

    def format(self, results: list[LintResult], **_kwargs: Any) -> str:
        """Format results as JUnit XML."""
        logger.debug("Formatting %d results as JUnit XML", len(results))

        total_tests = sum(len(r.violations) + (1 if r.parse_error else 0) for r in results)
        total_failures = sum(r.error_count for r in results)
        total_errors = sum(1 for r in results if r.parse_error)

        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<testsuite name="GitLab CI Lint" tests="{total_tests}" failures="{total_failures}" errors="{total_errors}" time="0">',
        ]

        for result in results:
            file_name = result.file_path.name

            if result.parse_error:
                xml_lines.extend(
                    [
                        f'  <testcase classname="{file_name}" name="Parse" time="0">',
                        '    <error message="Parse Error" type="ParseError">',
                        f"      <![CDATA[{result.parse_error}]]>",
                        "    </error>",
                        "  </testcase>",
                    ]
                )

            for violation in result.violations:
                test_name = f"{violation.rule_id}"
                if violation.job_name:
                    test_name += f".{violation.job_name}"

                xml_lines.append(f'  <testcase classname="{file_name}" name="{test_name}" time="0">')

                if violation.level == LintLevel.ERROR:
                    xml_lines.extend(
                        [
                            f'    <failure message="{self._escape_xml(violation.message)}" type="{violation.rule_id}">',
                            f"      <![CDATA[{violation.message}",
                            f"Location: {result.file_path}" + (f":{violation.line}" if violation.line else ""),
                            f"Suggestion: {violation.suggestion or 'N/A'}]]>",
                            "    </failure>",
                        ]
                    )
                elif violation.level == LintLevel.WARNING:
                    # JUnit doesn't have warnings, so we use system-out
                    xml_lines.extend(
                        [
                            "    <system-out>",
                            f"      <![CDATA[WARNING: {violation.message}",
                            f"Location: {result.file_path}" + (f":{violation.line}" if violation.line else ""),
                            f"Suggestion: {violation.suggestion or 'N/A'}]]>",
                            "    </system-out>",
                        ]
                    )

                xml_lines.append("  </testcase>")

        xml_lines.append("</testsuite>")
        return "\n".join(xml_lines)

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )


class FormatterRegistry:
    """Registry for output formatters."""

    def __init__(self) -> None:
        self._formatters = {"json": JSONFormatter(), "sarif": SARIFFormatter(), "junit": JUnitFormatter()}

    def get_formatter(self, format_name: str) -> BaseFormatter | None:
        """Get formatter by name."""
        return self._formatters.get(format_name.lower())

    def list_formats(self) -> list[str]:
        """List available formats."""
        return list(self._formatters.keys())

    def register_formatter(self, name: str, formatter: BaseFormatter) -> None:
        """Register a custom formatter."""
        self._formatters[name.lower()] = formatter


# Global formatter registry
formatter_registry = FormatterRegistry()
