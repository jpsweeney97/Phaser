"""Tests for the validate module."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from tools.validate import (
    CheckCase,
    CheckType,
    CheckResult,
    CheckExecution,
    EvaluationSuite,
    ValidationReport,
    parse_evaluation_suite,
    parse_check_cases,
    parse_single_check_case,
    extract_attribute,
    run_check_case,
    run_evaluation_suite,
    parse_verify_section,
    parse_context_scenarios,
    format_report_table,
    format_report_json,
    format_report_markdown,
    cli,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_evaluation_suite():
    """Sample evaluation suite XML content."""
    return """
<evaluation_suite>
    <test_case id="1" type="existence">
        <command>test -f /tmp/test_file</command>
        <description>File exists</description>
    </test_case>
    
    <test_case id="2" type="content_present">
        <command>grep -q "pattern" /tmp/test_file</command>
        <description>Pattern present</description>
    </test_case>
    
    <test_case id="3" type="build">
        <command>echo "build success"</command>
        <description>Build succeeds</description>
    </test_case>
</evaluation_suite>
"""


@pytest.fixture
def sample_phase_content():
    """Sample phase file with verify section."""
    return """
# Phase 2: Extract Validation

## Context

Test phase for validation.

## Goal

Extract validation logic.

## Files

| Path | Operation |
|------|-----------|
| `src/validation.py` | create |

## Plan

1. Create file
2. Add content

## Verify

test -f src/validation.py
grep -q "class Validator" src/validation.py
python -m py_compile src/validation.py

## Acceptance Criteria

- [ ] File created
- [ ] Class defined

## Rollback

rm -f src/validation.py
"""


@pytest.fixture
def sample_context_content():
    """Sample CONTEXT file with behavioral scenarios."""
    return """
# Audit Context

<evaluation_suite>
    <test_case id="happy_path" type="happy_path">
        <scenario>User executes 3-phase audit with no failures</scenario>
        <expected>
            - Each phase marked [x] in order
            - Final verification passes
            - Archive created
        </expected>
    </test_case>
    
    <test_case id="skip_middle" type="edge">
        <scenario>User skips phase 2 of 3</scenario>
        <expected>
            - Phase 2 marked [SKIPPED]
            - Phases 1, 3 execute normally
        </expected>
    </test_case>
</evaluation_suite>
"""


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# Parsing Tests
# =============================================================================


class TestExtractAttribute:
    """Tests for extract_attribute function."""

    def test_extract_existing_attribute(self):
        attrs = 'id="test_1" type="existence"'
        assert extract_attribute(attrs, "id") == "test_1"
        assert extract_attribute(attrs, "type") == "existence"

    def test_extract_missing_attribute(self):
        attrs = 'id="test_1"'
        assert extract_attribute(attrs, "type") == ""

    def test_extract_single_quotes(self):
        attrs = "id='test_1' type='build'"
        assert extract_attribute(attrs, "id") == "test_1"
        assert extract_attribute(attrs, "type") == "build"

    def test_extract_empty_string(self):
        assert extract_attribute("", "id") == ""


class TestParseSingleCheckCase:
    """Tests for parse_single_check_case function."""

    def test_parse_complete_check_case(self):
        attrs = 'id="1" type="existence"'
        content = """
            <command>test -f file.txt</command>
            <description>Check file exists</description>
        """
        result = parse_single_check_case(attrs, content)

        assert result is not None
        assert result.id == "1"
        assert result.check_type == CheckType.EXISTENCE
        assert result.command == "test -f file.txt"
        assert result.description == "Check file exists"
        assert result.timeout == 30  # default

    def test_parse_with_timeout(self):
        attrs = 'id="2" type="build"'
        content = """
            <command>make build</command>
            <description>Build project</description>
            <timeout>60</timeout>
        """
        result = parse_single_check_case(attrs, content)

        assert result is not None
        assert result.timeout == 60

    def test_parse_missing_id(self):
        attrs = 'type="existence"'
        content = "<command>test -f file</command>"
        result = parse_single_check_case(attrs, content)

        assert result is None

    def test_parse_unknown_type(self):
        attrs = 'id="1" type="unknown_type"'
        content = "<command>echo test</command>"
        result = parse_single_check_case(attrs, content)

        assert result is not None
        assert result.check_type == CheckType.CUSTOM


class TestParseEvaluationSuite:
    """Tests for parse_evaluation_suite function."""

    def test_parse_valid_suite(self, sample_evaluation_suite):
        suite = parse_evaluation_suite(sample_evaluation_suite, "test.md")

        assert suite.source_file == "test.md"
        assert len(suite.check_cases) == 3

    def test_parse_check_types(self, sample_evaluation_suite):
        suite = parse_evaluation_suite(sample_evaluation_suite, "test.md")

        assert suite.check_cases[0].check_type == CheckType.EXISTENCE
        assert suite.check_cases[1].check_type == CheckType.CONTENT_PRESENT
        assert suite.check_cases[2].check_type == CheckType.BUILD

    def test_parse_empty_content(self):
        suite = parse_evaluation_suite("", "empty.md")

        assert suite.source_file == "empty.md"
        assert len(suite.check_cases) == 0

    def test_parse_no_suite_block(self):
        content = "# Just some markdown\n\nNo evaluation suite here."
        suite = parse_evaluation_suite(content, "nosuite.md")

        assert len(suite.check_cases) == 0

    def test_parse_multiple_suites(self):
        content = """
<evaluation_suite>
    <test_case id="1" type="existence">
        <command>test -f a</command>
        <description>A exists</description>
    </test_case>
</evaluation_suite>

Some text in between.

<evaluation_suite>
    <test_case id="2" type="existence">
        <command>test -f b</command>
        <description>B exists</description>
    </test_case>
</evaluation_suite>
"""
        suite = parse_evaluation_suite(content, "multi.md")

        assert len(suite.check_cases) == 2


class TestParseVerifySection:
    """Tests for parse_verify_section function."""

    def test_parse_verify_commands(self, sample_phase_content):
        commands = parse_verify_section(sample_phase_content)

        assert len(commands) == 3
        assert "test -f src/validation.py" in commands
        assert 'grep -q "class Validator" src/validation.py' in commands
        assert "python -m py_compile src/validation.py" in commands

    def test_parse_no_verify_section(self):
        content = "# Phase 1\n\n## Goal\n\nDo something"
        commands = parse_verify_section(content)

        assert len(commands) == 0

    def test_skip_comments_and_empty_lines(self):
        content = """
## Verify

# This is a comment
test -f file

   
another_command
"""
        commands = parse_verify_section(content)

        assert len(commands) == 2
        assert "test -f file" in commands
        assert "another_command" in commands


class TestParseContextScenarios:
    """Tests for parse_context_scenarios function."""

    def test_parse_scenarios(self, sample_context_content):
        scenarios = parse_context_scenarios(sample_context_content)

        assert len(scenarios) == 2

    def test_scenario_content(self, sample_context_content):
        scenarios = parse_context_scenarios(sample_context_content)

        happy = next(s for s in scenarios if s["id"] == "happy_path")
        assert happy["type"] == "happy_path"
        assert "3-phase audit" in happy["scenario"]
        assert len(happy["expected"]) == 3

    def test_no_scenarios(self):
        content = "# Context\n\nJust text."
        scenarios = parse_context_scenarios(content)

        assert len(scenarios) == 0


# =============================================================================
# Execution Tests
# =============================================================================


class TestRunCheckCase:
    """Tests for run_check_case function."""

    def test_passing_command(self, temp_dir):
        check_case = CheckCase(
            id="1",
            check_type=CheckType.CUSTOM,
            command="echo hello",
            description="Echo test",
        )

        execution = run_check_case(check_case, temp_dir)

        assert execution.result == CheckResult.PASS
        assert execution.exit_code == 0
        assert "hello" in execution.stdout

    def test_failing_command(self, temp_dir):
        check_case = CheckCase(
            id="2",
            check_type=CheckType.EXISTENCE,
            command="test -f nonexistent_file_12345",
            description="Check missing file",
        )

        execution = run_check_case(check_case, temp_dir)

        assert execution.result == CheckResult.FAIL
        assert execution.exit_code != 0

    def test_command_timeout(self, temp_dir):
        check_case = CheckCase(
            id="3",
            check_type=CheckType.CUSTOM,
            command="sleep 10",
            description="Slow command",
            timeout=1,
        )

        execution = run_check_case(check_case, temp_dir)

        assert execution.result == CheckResult.ERROR
        assert "timed out" in execution.error_message

    def test_empty_command(self, temp_dir):
        check_case = CheckCase(
            id="4",
            check_type=CheckType.CUSTOM,
            command="",
            description="Empty command",
        )

        execution = run_check_case(check_case, temp_dir)

        assert execution.result == CheckResult.SKIP

    def test_command_with_working_dir(self, temp_dir):
        # Create a file in temp dir
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        check_case = CheckCase(
            id="5",
            check_type=CheckType.EXISTENCE,
            command="test -f test.txt",
            description="Check file in working dir",
        )

        execution = run_check_case(check_case, temp_dir)

        assert execution.result == CheckResult.PASS


class TestRunEvaluationSuite:
    """Tests for run_evaluation_suite function."""

    def test_run_all_passing(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="1", check_type=CheckType.CUSTOM, command="true", description="Pass 1"),
                CheckCase(id="2", check_type=CheckType.CUSTOM, command="true", description="Pass 2"),
            ],
        )

        report = run_evaluation_suite(suite, temp_dir)

        assert report.success
        assert report.passed == 2
        assert report.failed == 0

    def test_run_with_failures(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="1", check_type=CheckType.CUSTOM, command="true", description="Pass"),
                CheckCase(id="2", check_type=CheckType.CUSTOM, command="false", description="Fail"),
            ],
        )

        report = run_evaluation_suite(suite, temp_dir)

        assert not report.success
        assert report.passed == 1
        assert report.failed == 1

    def test_fail_fast_mode(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="1", check_type=CheckType.CUSTOM, command="false", description="Fail first"),
                CheckCase(id="2", check_type=CheckType.CUSTOM, command="true", description="Should not run"),
            ],
        )

        report = run_evaluation_suite(suite, temp_dir, fail_fast=True)

        assert not report.success
        assert len(report.executions) == 1  # Stopped after first failure

    def test_report_duration(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="1", check_type=CheckType.CUSTOM, command="true", description="Quick"),
            ],
        )

        report = run_evaluation_suite(suite, temp_dir)

        assert report.duration_ms >= 0
        assert report.start_time > 0
        assert report.end_time >= report.start_time


# =============================================================================
# Formatting Tests
# =============================================================================


class TestFormatReportJson:
    """Tests for format_report_json function."""

    def test_json_structure(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="1", check_type=CheckType.EXISTENCE, command="true", description="Test"),
            ],
        )
        report = run_evaluation_suite(suite, temp_dir)

        json_output = format_report_json(report)
        data = json.loads(json_output)

        assert "source_file" in data
        assert "success" in data
        assert "summary" in data
        assert "check_cases" in data

    def test_json_summary(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="1", check_type=CheckType.CUSTOM, command="true", description="Pass"),
                CheckCase(id="2", check_type=CheckType.CUSTOM, command="false", description="Fail"),
            ],
        )
        report = run_evaluation_suite(suite, temp_dir)

        json_output = format_report_json(report)
        data = json.loads(json_output)

        assert data["summary"]["total"] == 2
        assert data["summary"]["passed"] == 1
        assert data["summary"]["failed"] == 1


class TestFormatReportMarkdown:
    """Tests for format_report_markdown function."""

    def test_markdown_structure(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="1", check_type=CheckType.EXISTENCE, command="true", description="Test"),
            ],
        )
        report = run_evaluation_suite(suite, temp_dir)

        md_output = format_report_markdown(report)

        assert "# Validation Report" in md_output
        assert "## Summary" in md_output
        assert "## Check Cases" in md_output
        assert "| ID |" in md_output

    def test_markdown_failure_details(self, temp_dir):
        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(id="fail_1", check_type=CheckType.CUSTOM, command="false", description="Fail"),
            ],
        )
        report = run_evaluation_suite(suite, temp_dir)

        md_output = format_report_markdown(report)

        assert "## Failure Details" in md_output
        assert "fail_1" in md_output


# =============================================================================
# CLI Tests
# =============================================================================


class TestCLISuiteCommand:
    """Tests for the 'validate suite' CLI command."""

    def test_suite_command_success(self, temp_dir):
        # Create a test file with passing tests
        test_file = temp_dir / "test_suite.md"
        test_file.write_text("""
<evaluation_suite>
    <test_case id="1" type="custom">
        <command>true</command>
        <description>Always passes</description>
    </test_case>
</evaluation_suite>
""")

        runner = CliRunner()
        result = runner.invoke(cli, ["suite", str(test_file)])

        assert result.exit_code == 0
        assert "PASSED" in result.output

    def test_suite_command_failure(self, temp_dir):
        test_file = temp_dir / "test_suite.md"
        test_file.write_text("""
<evaluation_suite>
    <test_case id="1" type="custom">
        <command>false</command>
        <description>Always fails</description>
    </test_case>
</evaluation_suite>
""")

        runner = CliRunner()
        result = runner.invoke(cli, ["suite", str(test_file)])

        assert result.exit_code == 1
        assert "FAILED" in result.output

    def test_suite_command_json_format(self, temp_dir):
        test_file = temp_dir / "test_suite.md"
        test_file.write_text("""
<evaluation_suite>
    <test_case id="1" type="custom">
        <command>true</command>
        <description>Test</description>
    </test_case>
</evaluation_suite>
""")

        runner = CliRunner()
        result = runner.invoke(cli, ["suite", str(test_file), "--format", "json"])

        assert result.exit_code == 0
        # Find the JSON object in output (starts with '{')
        json_start = result.output.find('{')
        assert json_start != -1, "No JSON found in output"
        data = json.loads(result.output[json_start:])
        assert "success" in data

    def test_suite_command_no_tests(self, temp_dir):
        test_file = temp_dir / "empty.md"
        test_file.write_text("# No tests here")

        runner = CliRunner()
        result = runner.invoke(cli, ["suite", str(test_file)])

        assert result.exit_code == 0
        assert "No check cases found" in result.output


class TestCLIPhaseCommand:
    """Tests for the 'validate phase' CLI command."""

    def test_phase_command(self, temp_dir, sample_phase_content):
        # Create test file
        test_file = temp_dir / "phase.md"
        test_file.write_text(sample_phase_content)

        # Create the file that verify section checks for
        src_dir = temp_dir / "src"
        src_dir.mkdir()
        (src_dir / "validation.py").write_text("class Validator:\n    pass")

        runner = CliRunner()
        result = runner.invoke(cli, ["phase", str(test_file), "-C", str(temp_dir)])

        # Should have found verify commands
        assert "verification" in result.output.lower()


class TestCLIContextCommand:
    """Tests for the 'validate context' CLI command."""

    def test_context_list_scenarios(self, temp_dir, sample_context_content):
        test_file = temp_dir / "CONTEXT.md"
        test_file.write_text(sample_context_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["context", str(test_file), "--list"])

        assert result.exit_code == 0
        assert "happy_path" in result.output
        assert "skip_middle" in result.output

    def test_context_show_scenario(self, temp_dir, sample_context_content):
        test_file = temp_dir / "CONTEXT.md"
        test_file.write_text(sample_context_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["context", str(test_file), "--scenario", "happy_path"])

        assert result.exit_code == 0
        assert "3-phase audit" in result.output
        assert "Expected behavior" in result.output

    def test_context_unknown_scenario(self, temp_dir, sample_context_content):
        test_file = temp_dir / "CONTEXT.md"
        test_file.write_text(sample_context_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["context", str(test_file), "--scenario", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output


# =============================================================================
# ValidationReport Tests
# =============================================================================


class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_report_properties(self):
        suite = EvaluationSuite(source_file="test.md")
        report = ValidationReport(suite=suite)

        # Add some executions
        report.executions = [
            CheckExecution(
                check_case=CheckCase(id="1", check_type=CheckType.CUSTOM, command="", description=""),
                result=CheckResult.PASS,
            ),
            CheckExecution(
                check_case=CheckCase(id="2", check_type=CheckType.CUSTOM, command="", description=""),
                result=CheckResult.PASS,
            ),
            CheckExecution(
                check_case=CheckCase(id="3", check_type=CheckType.CUSTOM, command="", description=""),
                result=CheckResult.FAIL,
            ),
            CheckExecution(
                check_case=CheckCase(id="4", check_type=CheckType.CUSTOM, command="", description=""),
                result=CheckResult.SKIP,
            ),
        ]

        assert report.passed == 2
        assert report.failed == 1
        assert report.skipped == 1
        assert report.errors == 0
        assert report.total == 4
        assert not report.success  # Has failures

    def test_report_success(self):
        suite = EvaluationSuite(source_file="test.md")
        report = ValidationReport(suite=suite)
        report.executions = [
            CheckExecution(
                check_case=CheckCase(id="1", check_type=CheckType.CUSTOM, command="", description=""),
                result=CheckResult.PASS,
            ),
        ]

        assert report.success

    def test_report_duration(self):
        suite = EvaluationSuite(source_file="test.md")
        report = ValidationReport(suite=suite)
        report.start_time = 100.0
        report.end_time = 100.5

        assert report.duration_ms == 500


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the complete validation workflow."""

    def test_full_workflow(self, temp_dir):
        """Test parsing, running, and reporting a complete suite."""
        # Create a realistic phase file
        phase_file = temp_dir / "phase.md"
        phase_file.write_text("""
# Phase 1: Setup

## Context

Initial setup phase.

## Goal

Create configuration files.

## Files

| Path | Operation |
|------|-----------|
| `config.yaml` | create |

## Plan

1. Create config file

## Verify

<evaluation_suite>
    <test_case id="config_exists" type="existence">
        <command>test -f config.yaml</command>
        <description>Config file exists</description>
    </test_case>
    
    <test_case id="config_valid" type="content_present">
        <command>grep -q "version:" config.yaml</command>
        <description>Config has version</description>
    </test_case>
</evaluation_suite>

## Acceptance Criteria

- [ ] Config file created
- [ ] Version specified

## Rollback

rm -f config.yaml
""")

        # Create the config file to make tests pass
        (temp_dir / "config.yaml").write_text("version: 1.0\n")

        # Parse
        content = phase_file.read_text()
        suite = parse_evaluation_suite(content, str(phase_file))

        assert len(suite.check_cases) == 2

        # Run
        report = run_evaluation_suite(suite, temp_dir)

        assert report.success
        assert report.passed == 2

        # Format
        json_output = format_report_json(report)
        data = json.loads(json_output)

        assert data["success"] is True
        assert data["summary"]["passed"] == 2

    def test_real_file_operations(self, temp_dir):
        """Test with actual file operations."""
        # Create test file
        test_file = temp_dir / "data.txt"
        test_file.write_text("hello world\nline two\n")

        suite = EvaluationSuite(
            source_file="test.md",
            check_cases=[
                CheckCase(
                    id="exists",
                    check_type=CheckType.EXISTENCE,
                    command="test -f data.txt",
                    description="File exists",
                ),
                CheckCase(
                    id="content",
                    check_type=CheckType.CONTENT_PRESENT,
                    command='grep -q "hello" data.txt',
                    description="Contains hello",
                ),
                CheckCase(
                    id="lines",
                    check_type=CheckType.LINE_COUNT,
                    command="[ $(wc -l < data.txt) -eq 2 ]",
                    description="Has 2 lines",
                ),
                CheckCase(
                    id="no_error",
                    check_type=CheckType.CONTENT_ABSENT,
                    command='! grep -q "error" data.txt',
                    description="No error keyword",
                ),
            ],
        )

        report = run_evaluation_suite(suite, temp_dir)

        assert report.success
        assert report.passed == 4
