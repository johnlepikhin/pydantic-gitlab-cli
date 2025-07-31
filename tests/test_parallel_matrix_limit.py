"""Tests for ParallelMatrixLimitRule."""

import pytest
from pydantic_gitlab import GitLabCI

from pydantic_gitlab_cli.linter.base import LintResult
from pydantic_gitlab_cli.linter.rules.optimization import ParallelMatrixLimitRule


@pytest.fixture
def rule():
    """Create rule instance."""
    return ParallelMatrixLimitRule()


@pytest.fixture
def result():
    """Create result instance."""
    return LintResult(file_path="test.yml")


def test_simple_parallel_within_limit(rule, result):
    """Test simple parallel configuration within limit."""
    ci_config = GitLabCI(jobs={"test": {"script": ["echo test"], "parallel": 10}})

    rule.check(ci_config, result)
    assert len(result.violations) == 0


def test_simple_parallel_exceeds_limit(rule, result):
    """Test simple parallel configuration exceeding limit."""
    ci_config = GitLabCI(jobs={"test": {"script": ["echo test"], "parallel": 201}})

    rule.check(ci_config, result)
    assert len(result.violations) == 1
    assert "exceeding GitLab's limit of 200" in result.violations[0].message


def test_simple_parallel_approaching_limit(rule, result):
    """Test simple parallel configuration approaching limit - should not trigger."""
    ci_config = GitLabCI(jobs={"test": {"script": ["echo test"], "parallel": 180}})

    rule.check(ci_config, result)
    assert len(result.violations) == 0  # No violation for values <= 200


def test_simple_parallel_at_limit(rule, result):
    """Test simple parallel configuration at exactly 200 - should not trigger."""
    ci_config = GitLabCI(jobs={"test": {"script": ["echo test"], "parallel": 200}})

    rule.check(ci_config, result)
    assert len(result.violations) == 0  # No violation for exactly 200


def test_matrix_list_within_limit(rule, result):
    """Test matrix list configuration within limit."""
    ci_config = GitLabCI(
        jobs={
            "test": {
                "script": ["echo test"],
                "parallel": {
                    "matrix": [{"VAR1": "a", "VAR2": "1"}, {"VAR1": "b", "VAR2": "2"}, {"VAR1": "c", "VAR2": "3"}]
                },
            }
        }
    )

    rule.check(ci_config, result)
    assert len(result.violations) == 0


def test_matrix_list_exceeds_limit(rule, result):
    """Test matrix list configuration exceeding limit."""
    # Create a list with 201 combinations
    matrix_list = []
    for i in range(201):
        matrix_list.append({"VAR1": f"value_{i}"})

    ci_config = GitLabCI(jobs={"test": {"script": ["echo test"], "parallel": {"matrix": matrix_list}}})

    rule.check(ci_config, result)
    assert len(result.violations) == 1
    assert "will generate 201 jobs" in result.violations[0].message


def test_matrix_dict_cartesian_product(rule, result):
    """Test matrix dict with cartesian product."""
    ci_config = GitLabCI(
        jobs={
            "test": {
                "script": ["echo test"],
                "parallel": {
                    "matrix": {
                        "VERSION": ["1", "2", "3", "4", "5"],  # 5 values
                        "OS": ["linux", "windows", "mac"],  # 3 values
                        "ARCH": ["x86", "arm"],  # 2 values
                        # Total: 5 * 3 * 2 = 30 jobs
                    }
                },
            }
        }
    )

    rule.check(ci_config, result)
    assert len(result.violations) == 0


def test_matrix_dict_exceeds_limit(rule, result):
    """Test matrix dict configuration exceeding limit."""
    ci_config = GitLabCI(
        jobs={
            "test": {
                "script": ["echo test"],
                "parallel": {
                    "matrix": {
                        "VERSION": [str(i) for i in range(10)],  # 10 values
                        "OS": ["linux", "windows", "mac", "bsd"],  # 4 values
                        "ARCH": ["x86", "arm", "ppc", "s390"],  # 4 values
                        "CONFIG": ["debug", "release"],  # 2 values
                        # Total: 10 * 4 * 4 * 2 = 320 jobs
                    }
                },
            }
        }
    )

    rule.check(ci_config, result)
    assert len(result.violations) == 1
    assert "will generate 320 jobs" in result.violations[0].message
    assert "exceeding GitLab's limit of 200" in result.violations[0].message


def test_no_parallel_config(rule, result):
    """Test job without parallel configuration."""
    ci_config = GitLabCI(jobs={"test": {"script": ["echo test"]}})

    rule.check(ci_config, result)
    assert len(result.violations) == 0


def test_empty_matrix(rule, result):
    """Test empty matrix configuration."""
    ci_config = GitLabCI(jobs={"test": {"script": ["echo test"], "parallel": {"matrix": []}}})

    rule.check(ci_config, result)
    assert len(result.violations) == 0
