"""Tests for phaser enforce command."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


class TestEnforceSkeleton:
    """Tests for Phase 1 skeleton."""

    def test_stdin_produces_valid_json(self, write_simple_input: dict) -> None:
        """Verify --stdin mode outputs valid hook JSON."""
        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin"],
            input=json.dumps(write_simple_input),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        output = json.loads(proc.stdout)
        assert "hookSpecificOutput" in output

    def test_pretooluse_output_format(self, write_simple_input: dict) -> None:
        """Verify PreToolUse output has correct structure."""
        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin"],
            input=json.dumps(write_simple_input),
            capture_output=True,
            text=True,
        )
        output = json.loads(proc.stdout)
        hook_output = output["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] in ("allow", "deny")
        assert "permissionDecisionReason" in hook_output

    def test_empty_input_succeeds(self) -> None:
        """Verify empty input doesn't crash."""
        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin"],
            input="{}",
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0

    def test_missing_stdin_flag_errors(self) -> None:
        """Verify missing --stdin flag produces error."""
        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce"],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 3


class TestEnforcement:
    """Tests for violation detection."""

    def test_forbid_pattern_finds_violation(self, tmp_path: Path) -> None:
        """Verify forbid_pattern contract detects violations."""
        # Create contract
        contracts_dir = tmp_path / ".claude" / "contracts"
        contracts_dir.mkdir(parents=True)
        (contracts_dir / "no-print.yaml").write_text(
            yaml.dump(
                {
                    "rule_id": "no-print",
                    "type": "forbid_pattern",
                    "pattern": r"print\(",
                    "file_glob": "**/*.py",
                    "message": "No print statements",
                    "severity": "error",
                }
            )
        )

        # Test input with violation
        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "test.py"),
                "content": "def main():\n    print('hello')\n",
            },
            "cwd": str(tmp_path),
        }

        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "error"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "no-print" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_clean_code_allows(self, tmp_path: Path) -> None:
        """Verify clean code passes enforcement."""
        # Create contract
        contracts_dir = tmp_path / ".claude" / "contracts"
        contracts_dir.mkdir(parents=True)
        (contracts_dir / "no-print.yaml").write_text(
            yaml.dump(
                {
                    "rule_id": "no-print",
                    "type": "forbid_pattern",
                    "pattern": r"print\(",
                    "file_glob": "**/*.py",
                    "message": "No print statements",
                    "severity": "error",
                }
            )
        )

        # Test input without violation
        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "test.py"),
                "content": "import logging\nlogging.info('hello')\n",
            },
            "cwd": str(tmp_path),
        }

        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "error"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_severity_filter(self, tmp_path: Path) -> None:
        """Verify severity filter works correctly."""
        # Create warning-level contract
        contracts_dir = tmp_path / ".claude" / "contracts"
        contracts_dir.mkdir(parents=True)
        (contracts_dir / "no-todo.yaml").write_text(
            yaml.dump(
                {
                    "rule_id": "no-todo",
                    "type": "forbid_pattern",
                    "pattern": "TODO",
                    "file_glob": "**/*.py",
                    "message": "No TODOs",
                    "severity": "warning",
                }
            )
        )

        # Test input with TODO
        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "test.py"),
                "content": "# TODO: fix this\n",
            },
            "cwd": str(tmp_path),
        }

        # With --severity error, warning should be ignored
        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "error"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

        # With --severity warning, should be caught
        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "warning"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
