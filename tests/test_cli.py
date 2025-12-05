"""Tests for the unified phaser CLI."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from tools.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self, runner: CliRunner) -> None:
        """CLI shows help text."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Phaser" in result.output

    def test_cli_version(self, runner: CliRunner) -> None:
        """CLI version command shows version."""
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "1.5.0" in result.output

    def test_cli_version_option(self, runner: CliRunner) -> None:
        """CLI --version option shows version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.5.0" in result.output

    def test_cli_verbose_flag(self, runner: CliRunner) -> None:
        """CLI accepts --verbose flag."""
        result = runner.invoke(cli, ["--verbose", "version"])
        assert result.exit_code == 0

    def test_cli_quiet_flag(self, runner: CliRunner) -> None:
        """CLI accepts --quiet flag."""
        result = runner.invoke(cli, ["--quiet", "version"])
        assert result.exit_code == 0


class TestSubcommands:
    """Test subcommand availability."""

    def test_diff_help(self, runner: CliRunner) -> None:
        """Diff subcommand shows help."""
        result = runner.invoke(cli, ["diff", "--help"])
        assert result.exit_code == 0
        assert "capture" in result.output.lower() or "manifest" in result.output.lower()

    def test_contracts_help(self, runner: CliRunner) -> None:
        """Contracts subcommand shows help."""
        result = runner.invoke(cli, ["contracts", "--help"])
        assert result.exit_code == 0

    def test_simulate_help(self, runner: CliRunner) -> None:
        """Simulate subcommand shows help."""
        result = runner.invoke(cli, ["simulate", "--help"])
        assert result.exit_code == 0

    def test_branches_help(self, runner: CliRunner) -> None:
        """Branches subcommand shows help."""
        result = runner.invoke(cli, ["branches", "--help"])
        assert result.exit_code == 0


class TestCheckCommand:
    """Test the check command for CI integration."""

    def test_check_no_contracts(self, runner: CliRunner, temp_dir: Path) -> None:
        """Check command succeeds with no contracts."""
        result = runner.invoke(cli, ["check", "--root", str(temp_dir)])
        assert result.exit_code == 0

    def test_check_json_format(self, runner: CliRunner, temp_dir: Path) -> None:
        """Check command outputs JSON when requested."""
        result = runner.invoke(cli, ["check", "--root", str(temp_dir), "--format", "json"])
        assert result.exit_code == 0
        assert "[" in result.output  # JSON array

    def test_check_text_format(self, runner: CliRunner, temp_dir: Path) -> None:
        """Check command outputs text by default."""
        result = runner.invoke(cli, ["check", "--root", str(temp_dir)])
        assert result.exit_code == 0


class TestManifestCommand:
    """Test the manifest command."""

    def test_manifest_capture(self, runner: CliRunner, temp_dir: Path) -> None:
        """Manifest command captures directory state."""
        (temp_dir / "test.txt").write_text("hello")
        result = runner.invoke(cli, ["manifest", str(temp_dir)])
        assert result.exit_code == 0
        assert "test.txt" in result.output

    def test_manifest_yaml_format(self, runner: CliRunner, temp_dir: Path) -> None:
        """Manifest command outputs YAML by default."""
        (temp_dir / "file.py").write_text("print('hi')")
        result = runner.invoke(cli, ["manifest", str(temp_dir)])
        assert result.exit_code == 0
        assert "file.py" in result.output

    def test_manifest_json_format(self, runner: CliRunner, temp_dir: Path) -> None:
        """Manifest command outputs JSON when requested."""
        (temp_dir / "file.py").write_text("print('hi')")
        result = runner.invoke(cli, ["manifest", str(temp_dir), "--format", "json"])
        assert result.exit_code == 0
        assert "{" in result.output  # JSON object


class TestInfoCommand:
    """Test the info command."""

    def test_info_global(self, runner: CliRunner) -> None:
        """Info command shows global storage."""
        result = runner.invoke(cli, ["info", "--global"])
        assert result.exit_code == 0
        assert "Global storage" in result.output

    def test_info_project(self, runner: CliRunner) -> None:
        """Info command shows project storage."""
        result = runner.invoke(cli, ["info", "--project"])
        assert result.exit_code == 0

    def test_info_default(self, runner: CliRunner) -> None:
        """Info command shows both by default."""
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "Global storage" in result.output
