"""Tests for linter rules."""

from pathlib import Path

from pydantic_gitlab_cli.linter.engine import LintEngine
from pydantic_gitlab_cli.linter.rules import (
    DockerLatestTagRule,
    GoCacheRule,
    JavaCacheRule,
    JobNamingRule,
    NodeCacheRule,
    PythonCacheRule,
    RustCacheRule,
    SecretsInCodeRule,
    StagesStructureRule,
    YamlSyntaxRule,
)


class TestLinterRules:
    """Test suite for individual linter rules."""

    def test_yaml_syntax_rule_valid(self):
        """Test YamlSyntaxRule with valid YAML."""
        rule = YamlSyntaxRule()
        engine = LintEngine()
        engine.register_rules([rule])

        valid_file = Path("tests/fixtures/valid-simple.gitlab-ci.yml")
        results = engine.lint_files([valid_file])

        # Should not have YAML syntax errors
        yaml_violations = [v for result in results for v in result.violations if v.rule_id == "GL001"]
        assert len(yaml_violations) == 0

    def test_stages_structure_rule_unused_stages(self):
        """Test StagesStructureRule detects unused stages."""
        rule = StagesStructureRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with unused stages
        test_file = Path("tests/fixtures/cache-optimization-test.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect unused stages
        stage_violations = [v for result in results for v in result.violations if v.rule_id == "GL002"]
        assert len(stage_violations) > 0
        assert "Unused stages" in stage_violations[0].message

    def test_docker_latest_tag_rule_detects_latest(self):
        """Test DockerLatestTagRule detects :latest tag usage."""
        rule = DockerLatestTagRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with :latest tags
        test_file = Path("tests/fixtures/invalid-latest.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect :latest tag usage
        latest_violations = [v for result in results for v in result.violations if v.rule_id == "GL005"]
        assert len(latest_violations) > 0
        assert "latest" in latest_violations[0].message.lower()

    def test_docker_latest_tag_rule_allows_specific_versions(self):
        """Test DockerLatestTagRule allows specific versions."""
        rule = DockerLatestTagRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with specific versions
        test_file = Path("tests/fixtures/valid-simple.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should not detect violations for specific versions
        latest_violations = [v for result in results for v in result.violations if v.rule_id == "GL005"]
        assert len(latest_violations) == 0

    def test_job_naming_rule_detects_bad_names(self):
        """Test JobNamingRule detects invalid job names."""
        rule = JobNamingRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with bad job names
        test_file = Path("tests/fixtures/invalid-naming.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect naming violations
        naming_violations = [v for result in results for v in result.violations if v.rule_id == "GL022"]
        assert len(naming_violations) > 0

    def test_job_naming_rule_allows_good_names(self):
        """Test JobNamingRule allows valid snake_case names."""
        rule = JobNamingRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with good job names
        test_file = Path("tests/fixtures/valid-simple.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should not detect naming violations
        naming_violations = [v for result in results for v in result.violations if v.rule_id == "GL022"]
        assert len(naming_violations) == 0

    def test_secrets_rule_detects_hardcoded_secrets(self):
        """Test SecretsInCodeRule detects hardcoded secrets."""
        rule = SecretsInCodeRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with hardcoded secrets
        test_file = Path("tests/fixtures/invalid-security-simple.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect secret violations
        secret_violations = [v for result in results for v in result.violations if v.rule_id == "GL012"]
        assert len(secret_violations) > 0

    def test_python_cache_rule_detects_missing_cache(self):
        """Test PythonCacheRule detects pip usage without cache."""
        rule = PythonCacheRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with pip usage but no cache
        test_file = Path("tests/fixtures/cache-optimization-test.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect missing cache for Python jobs
        python_cache_violations = [v for result in results for v in result.violations if v.rule_id == "GL027"]
        assert len(python_cache_violations) > 0
        assert "pip" in python_cache_violations[0].message.lower()

    def test_node_cache_rule_detects_missing_cache(self):
        """Test NodeCacheRule detects npm usage without cache."""
        rule = NodeCacheRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with npm usage but no cache
        test_file = Path("tests/fixtures/cache-optimization-test.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect missing cache for Node jobs
        node_cache_violations = [v for result in results for v in result.violations if v.rule_id == "GL028"]
        assert len(node_cache_violations) > 0

    def test_node_cache_rule_allows_proper_cache(self):
        """Test NodeCacheRule allows jobs with proper npm cache."""
        rule = NodeCacheRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with proper Node.js cache
        test_file = Path("tests/fixtures/valid-simple.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should not detect violations for properly cached Node jobs
        node_cache_violations = [v for result in results for v in result.violations if v.rule_id == "GL028"]
        assert len(node_cache_violations) == 0

    def test_rust_cache_rule_detects_missing_cache(self):
        """Test RustCacheRule detects cargo usage without cache."""
        rule = RustCacheRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with cargo usage but no cache
        test_file = Path("tests/fixtures/cache-optimization-test.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect missing cache for Rust jobs
        rust_cache_violations = [v for result in results for v in result.violations if v.rule_id == "GL029"]
        assert len(rust_cache_violations) > 0
        assert "cargo" in rust_cache_violations[0].message.lower()

    def test_go_cache_rule_detects_missing_cache(self):
        """Test GoCacheRule detects go commands without cache."""
        rule = GoCacheRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with go commands but no cache
        test_file = Path("tests/fixtures/cache-optimization-test.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect missing cache for Go jobs
        go_cache_violations = [v for result in results for v in result.violations if v.rule_id == "GL030"]
        assert len(go_cache_violations) > 0
        assert "go" in go_cache_violations[0].message.lower()

    def test_java_cache_rule_detects_missing_cache(self):
        """Test JavaCacheRule detects Maven/Gradle usage without cache."""
        rule = JavaCacheRule()
        engine = LintEngine()
        engine.register_rules([rule])

        # File with Maven usage but no cache
        test_file = Path("tests/fixtures/cache-optimization-test.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should detect missing cache for Java jobs
        java_cache_violations = [v for result in results for v in result.violations if v.rule_id == "GL031"]
        assert len(java_cache_violations) > 0
        assert (
            "maven" in java_cache_violations[0].message.lower() or "gradle" in java_cache_violations[0].message.lower()
        )

    def test_perfect_file_has_no_violations(self):
        """Test that perfect configuration file has no violations."""
        engine = LintEngine()
        # Register a subset of rules to test against perfect file
        rules = [
            YamlSyntaxRule(),
            StagesStructureRule(),
            DockerLatestTagRule(),
            JobNamingRule(),
        ]
        engine.register_rules(rules)

        # Perfect file should have no violations for these rules
        test_file = Path("tests/fixtures/perfect.gitlab-ci.yml")
        results = engine.lint_files([test_file])

        # Should have no violations from our tested rules
        tested_rule_ids = {"GL001", "GL002", "GL005", "GL022"}
        tested_violations = [v for result in results for v in result.violations if v.rule_id in tested_rule_ids]
        assert len(tested_violations) == 0

    def test_multiple_files_processing(self):
        """Test that engine can process multiple files correctly."""
        engine = LintEngine()
        engine.register_rules([YamlSyntaxRule(), StagesStructureRule()])

        # Process multiple files
        files = [
            Path("tests/fixtures/valid-simple.gitlab-ci.yml"),
            Path("tests/fixtures/cache-optimization-test.gitlab-ci.yml"),
        ]
        results = engine.lint_files(files)

        # Should have results for both files
        assert len(results) == 2
        assert all(result.file_path in files for result in results)

    def test_rule_level_configuration(self):
        """Test that rule levels are correctly configured."""
        rules = [
            YamlSyntaxRule(),  # ERROR level
            PythonCacheRule(),  # WARNING level
        ]

        # Check rule levels
        assert rules[0].level.value == "error"
        assert rules[1].level.value == "warning"

    def test_rule_categories(self):
        """Test that rules have correct categories."""
        rules = [
            YamlSyntaxRule(),  # syntax
            StagesStructureRule(),  # structure
            SecretsInCodeRule(),  # security
            PythonCacheRule(),  # cache_optimization
            JobNamingRule(),  # naming
        ]

        expected_categories = ["syntax", "structure", "security", "cache_optimization", "naming"]
        actual_categories = [rule.category for rule in rules]

        assert actual_categories == expected_categories
