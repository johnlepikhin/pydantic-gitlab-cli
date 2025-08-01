"""Tests for main CLI functionality."""

from typer.testing import CliRunner

from pydantic_gitlab_cli.main import app

runner = CliRunner()


def test_version():
    """Test version command."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "pydantic-gitlab-cli version:" in result.stdout


def test_help():
    """Test help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "GitLab CI/CD configuration linter and analyzer" in result.stdout


def test_info_command():
    """Test info command."""
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "GitLab CI/CD Linter Info" in result.stdout


def test_hello_command():
    """Test hello command."""
    # The hello command doesn't exist in this app
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 2  # Invalid command
    assert "No such command" in result.stdout or "Usage" in result.stdout


def test_projects_subcommand():
    """Test projects subcommand exists."""
    result = runner.invoke(app, ["projects", "--help"])
    assert result.exit_code == 0
    assert "Manage GitLab projects" in result.stdout


def test_issues_subcommand():
    """Test issues subcommand exists."""
    result = runner.invoke(app, ["issues", "--help"])
    assert result.exit_code == 0
    assert "Manage GitLab issues" in result.stdout


def test_mr_subcommand():
    """Test mr subcommand exists."""
    result = runner.invoke(app, ["mr", "--help"])
    assert result.exit_code == 0
    assert "Manage GitLab merge requests" in result.stdout


def test_check_subcommand():
    """Test check subcommand exists."""
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    assert "Perform static checks on GitLab CI YAML files" in result.stdout
