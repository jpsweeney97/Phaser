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


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    def project_with_contracts(self, tmp_path: Path) -> Path:
        """Create a project with contracts and source files."""
        # Create contracts directory
        contracts_dir = tmp_path / ".claude" / "contracts"
        contracts_dir.mkdir(parents=True)

        # Add forbid_pattern contract
        (contracts_dir / "no-print.yaml").write_text(
            yaml.dump(
                {
                    "rule_id": "no-print",
                    "type": "forbid_pattern",
                    "pattern": r"print\(",
                    "file_glob": "**/*.py",
                    "message": "Use logging instead of print",
                    "severity": "error",
                }
            )
        )

        # Add require_pattern contract
        (contracts_dir / "require-docstring.yaml").write_text(
            yaml.dump(
                {
                    "rule_id": "require-docstring",
                    "type": "require_pattern",
                    "pattern": r'^\s*"""',
                    "file_glob": "**/*.py",
                    "message": "Python files must have docstrings",
                    "severity": "warning",
                }
            )
        )

        return tmp_path

    def test_clean_write_allows(self, project_with_contracts: Path) -> None:
        """Write with no violations should be allowed."""
        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(project_with_contracts / "clean.py"),
                "content": '"""Module docstring."""\n\nimport logging\nlogging.info("hello")\n',
            },
            "cwd": str(project_with_contracts),
        }

        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "error"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_violation_denies(self, project_with_contracts: Path) -> None:
        """Write with violation should be denied."""
        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(project_with_contracts / "bad.py"),
                "content": 'print("hello")\n',
            },
            "cwd": str(project_with_contracts),
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

    def test_ignore_suppresses_violation(self, project_with_contracts: Path) -> None:
        """Ignore directive should suppress violation."""
        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(project_with_contracts / "ignored.py"),
                "content": 'print("hello")  # phaser:ignore no-print\n',
            },
            "cwd": str(project_with_contracts),
        }

        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "error"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_edit_with_existing_file(self, project_with_contracts: Path) -> None:
        """Edit should reconstruct and check proposed state."""
        # Create existing file
        src_file = project_with_contracts / "existing.py"
        src_file.write_text('"""Doc."""\nimport logging\nlogging.info("hello")\n')

        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(src_file),
                "old_str": 'logging.info("hello")',
                "new_str": 'print("hello")',
            },
            "cwd": str(project_with_contracts),
        }

        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "error"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_posttooluse_format(self, project_with_contracts: Path) -> None:
        """PostToolUse should use different output format."""
        hook_input = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(project_with_contracts / "test.py"),
                "content": "x = 1\n",  # Missing docstring (warning)
            },
            "cwd": str(project_with_contracts),
        }

        proc = subprocess.run(
            [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "warning"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        output = json.loads(proc.stdout)
        assert "hookSpecificOutput" in output
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


class TestPerformance:
    """Performance tests."""

    def test_latency_reasonable(self, tmp_path: Path) -> None:
        """Verify enforcement completes in reasonable time."""
        import time

        # Create 20 contracts
        contracts_dir = tmp_path / ".claude" / "contracts"
        contracts_dir.mkdir(parents=True)

        for i in range(20):
            (contracts_dir / f"rule-{i}.yaml").write_text(
                yaml.dump(
                    {
                        "rule_id": f"rule-{i}",
                        "type": "forbid_pattern",
                        "pattern": f"forbidden_{i}",
                        "file_glob": "**/*.py",
                        "message": f"Rule {i} message",
                        "severity": "error" if i % 2 == 0 else "warning",
                    }
                )
            )

        hook_input = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "test.py"),
                "content": "x = 1\n" * 100,  # 100 lines
            },
            "cwd": str(tmp_path),
        }

        # Run multiple times and check average
        times: list[float] = []
        for _ in range(5):
            start = time.time()
            proc = subprocess.run(
                [sys.executable, "-m", "tools.cli", "enforce", "--stdin", "--severity", "error"],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
            )
            elapsed = time.time() - start
            times.append(elapsed)
            assert proc.returncode == 0

        avg_time = sum(times) / len(times)
        # Should complete in under 500ms on average (generous for CI)
        assert avg_time < 0.5, f"Average time {avg_time:.3f}s exceeds 500ms"
