"""Tests for check command functionality."""

from typer.testing import CliRunner

from pydantic_gitlab_cli.main import app

runner = CliRunner()


def test_check_command_help():
    """Test check command help."""
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    assert "Perform static checks on GitLab CI YAML files" in result.stdout
