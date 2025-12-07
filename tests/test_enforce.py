"""Tests for phaser enforce command."""

import json
import subprocess
import sys

import pytest


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
