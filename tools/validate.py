"""
Validation tool for refined Phaser templates.

Parses evaluation suites from CONTEXT_refined.md and phase files,
runs check cases, and reports compliance.

Usage:
    phaser verify suite <file>           # Run evaluation suite from file
    phaser verify phase <phase_file>     # Verify a specific phase
    phaser verify context <context_file> # Inspect CONTEXT scenarios
    phaser verify all <audit_dir>        # Run all verifications for an audit
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import click


# Note: Classes are named Check* instead of Test* to avoid pytest collection warnings.
# pytest treats any class starting with "Test" as a test class.


class CheckType(Enum):
    """Types of check cases in evaluation suites."""

    EXISTENCE = "existence"
    NOT_EXISTS = "not_exists"
    CONTENT_PRESENT = "content_present"
    CONTENT_ABSENT = "content_absent"
    LINE_COUNT = "line_count"
    BUILD = "build"
    TEST = "test"
    NO_REFERENCES = "no_references"
    CUSTOM = "custom"


class CheckResult(Enum):
    """Result of a check case execution."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class CheckCase:
    """A single check case from an evaluation suite."""

    id: str
    check_type: CheckType
    command: str
    description: str
    timeout: int = 30
    expected_exit_code: int = 0


@dataclass
class CheckExecution:
    """Result of executing a check case."""

    check_case: CheckCase
    result: CheckResult = CheckResult.SKIP  # Default, will be set during execution
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    error_message: str = ""


@dataclass
class EvaluationSuite:
    """A collection of check cases parsed from a template."""

    source_file: str
    check_cases: list[CheckCase] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Complete validation report."""

    suite: EvaluationSuite
    executions: list[CheckExecution] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0

    @property
    def passed(self) -> int:
        """Count of checks that passed."""
        return sum(1 for e in self.executions if e.result == CheckResult.PASS)

    @property
    def failed(self) -> int:
        """Count of checks that failed."""
        return sum(1 for e in self.executions if e.result == CheckResult.FAIL)

    @property
    def skipped(self) -> int:
        """Count of checks that were skipped."""
        return sum(1 for e in self.executions if e.result == CheckResult.SKIP)

    @property
    def errors(self) -> int:
        """Count of checks that errored during execution."""
        return sum(1 for e in self.executions if e.result == CheckResult.ERROR)

    @property
    def total(self) -> int:
        """Total number of check executions."""
        return len(self.executions)

    @property
    def success(self) -> bool:
        """True if no failures or errors occurred."""
        return self.failed == 0 and self.errors == 0

    @property
    def duration_ms(self) -> int:
        """Total validation duration in milliseconds."""
        return int((self.end_time - self.start_time) * 1000)


# =============================================================================
# Parsing
# =============================================================================


def parse_evaluation_suite(content: str, source_file: str) -> EvaluationSuite:
    """Parse evaluation suite from template content."""
    suite = EvaluationSuite(source_file=source_file)

    # Find all <evaluation_suite> blocks
    suite_pattern = r"<evaluation_suite>(.*?)</evaluation_suite>"
    suite_matches = re.findall(suite_pattern, content, re.DOTALL)

    for suite_content in suite_matches:
        check_cases = parse_check_cases(suite_content)
        suite.check_cases.extend(check_cases)

    # Also parse standalone test_case blocks (for flexibility)
    standalone_pattern = r"<test_case\s+([^>]+)>(.*?)</test_case>"
    standalone_matches = re.findall(standalone_pattern, content, re.DOTALL)

    for attrs, case_content in standalone_matches:
        # Skip if already parsed in suite
        case_id = extract_attribute(attrs, "id")
        if any(cc.id == case_id for cc in suite.check_cases):
            continue
        check_case = parse_single_check_case(attrs, case_content)
        if check_case:
            suite.check_cases.append(check_case)

    return suite


def parse_check_cases(suite_content: str) -> list[CheckCase]:
    """Parse check cases from evaluation suite content."""
    check_cases = []

    # Pattern for test_case elements
    pattern = r"<test_case\s+([^>]+)>(.*?)</test_case>"
    matches = re.findall(pattern, suite_content, re.DOTALL)

    for attrs, case_content in matches:
        check_case = parse_single_check_case(attrs, case_content)
        if check_case:
            check_cases.append(check_case)

    return check_cases


def parse_single_check_case(attrs: str, case_content: str) -> Optional[CheckCase]:
    """Parse a single check case element."""
    case_id = extract_attribute(attrs, "id")
    case_type_str = extract_attribute(attrs, "type")

    if not case_id:
        return None

    # Map type string to enum
    type_mapping = {
        "existence": CheckType.EXISTENCE,
        "not_exists": CheckType.NOT_EXISTS,
        "content_present": CheckType.CONTENT_PRESENT,
        "content_absent": CheckType.CONTENT_ABSENT,
        "line_count": CheckType.LINE_COUNT,
        "build": CheckType.BUILD,
        "test": CheckType.TEST,
        "no_references": CheckType.NO_REFERENCES,
    }
    check_type = type_mapping.get(case_type_str, CheckType.CUSTOM)

    # Extract command
    command_match = re.search(r"<command>(.*?)</command>", case_content, re.DOTALL)
    command = command_match.group(1).strip() if command_match else ""

    # Extract description
    desc_match = re.search(r"<description>(.*?)</description>", case_content, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else f"Check case {case_id}"

    # Extract timeout if present
    timeout_match = re.search(r"<timeout>(\d+)</timeout>", case_content)
    timeout = int(timeout_match.group(1)) if timeout_match else 30

    return CheckCase(
        id=case_id,
        check_type=check_type,
        command=command,
        description=description,
        timeout=timeout,
    )


def extract_attribute(attrs: str, name: str) -> str:
    """Extract an attribute value from an attribute string."""
    pattern = rf'{name}=["\']([^"\']+)["\']'
    match = re.search(pattern, attrs)
    return match.group(1) if match else ""


# =============================================================================
# Execution
# =============================================================================


def run_check_case(check_case: CheckCase, working_dir: Optional[Path] = None) -> CheckExecution:
    """Execute a single check case and return the result."""
    execution = CheckExecution(check_case=check_case)

    if not check_case.command:
        execution.result = CheckResult.SKIP
        execution.error_message = "No command specified"
        return execution

    start_time = time.time()

    try:
        result = subprocess.run(
            check_case.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=check_case.timeout,
            cwd=working_dir,
        )

        execution.exit_code = result.returncode
        execution.stdout = result.stdout
        execution.stderr = result.stderr
        execution.duration_ms = int((time.time() - start_time) * 1000)

        # Determine result based on exit code
        if result.returncode == check_case.expected_exit_code:
            execution.result = CheckResult.PASS
        else:
            execution.result = CheckResult.FAIL
            execution.error_message = (
                f"Expected exit code {check_case.expected_exit_code}, "
                f"got {result.returncode}"
            )

    except subprocess.TimeoutExpired:
        execution.result = CheckResult.ERROR
        execution.error_message = f"Command timed out after {check_case.timeout}s"
        execution.duration_ms = check_case.timeout * 1000

    except Exception as e:
        execution.result = CheckResult.ERROR
        execution.error_message = str(e)
        execution.duration_ms = int((time.time() - start_time) * 1000)

    return execution


def run_evaluation_suite(
    suite: EvaluationSuite,
    working_dir: Optional[Path] = None,
    fail_fast: bool = False,
    verbose: bool = False,
) -> ValidationReport:
    """Run all check cases in an evaluation suite."""
    report = ValidationReport(suite=suite)
    report.start_time = time.time()

    for check_case in suite.check_cases:
        if verbose:
            click.echo(f"  Running: {check_case.id} - {check_case.description}...", nl=False)

        execution = run_check_case(check_case, working_dir)
        report.executions.append(execution)

        if verbose:
            if execution.result == CheckResult.PASS:
                click.echo(click.style(" âœ“", fg="green"))
            elif execution.result == CheckResult.FAIL:
                click.echo(click.style(" âœ—", fg="red"))
            elif execution.result == CheckResult.SKIP:
                click.echo(click.style(" â­", fg="yellow"))
            else:
                click.echo(click.style(" âš ", fg="yellow"))

        if fail_fast and execution.result in (CheckResult.FAIL, CheckResult.ERROR):
            break

    report.end_time = time.time()
    return report


# =============================================================================
# Formatting
# =============================================================================


def format_report_table(report: ValidationReport) -> str:
    """Format validation report as a table."""
    lines = []

    # Header
    lines.append(f"Validation Report: {report.suite.source_file}")
    lines.append("=" * 70)
    lines.append("")

    # Results table
    lines.append(f"{'ID':<8} {'Type':<16} {'Result':<8} {'Time':<8} Description")
    lines.append("-" * 70)

    for execution in report.executions:
        cc = execution.check_case
        result_str = execution.result.value.upper()

        # Color coding for terminal
        if execution.result == CheckResult.PASS:
            result_display = click.style(f"{result_str:<8}", fg="green")
        elif execution.result == CheckResult.FAIL:
            result_display = click.style(f"{result_str:<8}", fg="red")
        elif execution.result == CheckResult.SKIP:
            result_display = click.style(f"{result_str:<8}", fg="yellow")
        else:
            result_display = click.style(f"{result_str:<8}", fg="yellow")

        time_str = f"{execution.duration_ms}ms"
        lines.append(
            f"{cc.id:<8} {cc.check_type.value:<16} {result_display} {time_str:<8} {cc.description}"
        )

        # Show error details for failures
        if execution.result == CheckResult.FAIL and execution.error_message:
            lines.append(f"         â””â”€ {execution.error_message}")
        if execution.result == CheckResult.FAIL and execution.stderr:
            for stderr_line in execution.stderr.strip().split("\n")[:3]:
                lines.append(f"            {stderr_line}")

    # Summary
    lines.append("-" * 70)
    lines.append("")

    status = click.style("PASSED", fg="green") if report.success else click.style("FAILED", fg="red")
    lines.append(f"Status: {status}")
    lines.append(
        f"Results: {report.passed} passed, {report.failed} failed, "
        f"{report.skipped} skipped, {report.errors} errors"
    )
    lines.append(f"Duration: {report.duration_ms}ms")

    return "\n".join(lines)


def format_report_json(report: ValidationReport) -> str:
    """Format validation report as JSON."""
    import json

    data = {
        "source_file": report.suite.source_file,
        "success": report.success,
        "summary": {
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
            "errors": report.errors,
            "duration_ms": report.duration_ms,
        },
        "check_cases": [
            {
                "id": e.check_case.id,
                "type": e.check_case.check_type.value,
                "description": e.check_case.description,
                "command": e.check_case.command,
                "result": e.result.value,
                "exit_code": e.exit_code,
                "duration_ms": e.duration_ms,
                "error_message": e.error_message,
                "stdout": e.stdout[:500] if e.stdout else "",
                "stderr": e.stderr[:500] if e.stderr else "",
            }
            for e in report.executions
        ],
    }
    return json.dumps(data, indent=2)


def format_report_markdown(report: ValidationReport) -> str:
    """Format validation report as Markdown."""
    lines = []

    # Header
    lines.append("# Validation Report")
    lines.append("")
    lines.append(f"**Source:** `{report.suite.source_file}`")
    lines.append(f"**Status:** {'âœ… PASSED' if report.success else 'âŒ FAILED'}")
    lines.append(f"**Duration:** {report.duration_ms}ms")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Passed | {report.passed} |")
    lines.append(f"| Failed | {report.failed} |")
    lines.append(f"| Skipped | {report.skipped} |")
    lines.append(f"| Errors | {report.errors} |")
    lines.append(f"| **Total** | **{report.total}** |")
    lines.append("")

    # Results table
    lines.append("## Check Cases")
    lines.append("")
    lines.append("| ID | Type | Result | Time | Description |")
    lines.append("|:---|:-----|:-------|-----:|:------------|")

    for execution in report.executions:
        cc = execution.check_case
        result_emoji = {
            CheckResult.PASS: "âœ…",
            CheckResult.FAIL: "âŒ",
            CheckResult.SKIP: "â­ï¸",
            CheckResult.ERROR: "âš ï¸",
        }.get(execution.result, "â“")

        lines.append(
            f"| {cc.id} | {cc.check_type.value} | {result_emoji} {execution.result.value} | "
            f"{execution.duration_ms}ms | {cc.description} |"
        )

    # Failures detail
    failures = [e for e in report.executions if e.result in (CheckResult.FAIL, CheckResult.ERROR)]
    if failures:
        lines.append("")
        lines.append("## Failure Details")
        lines.append("")

        for execution in failures:
            cc = execution.check_case
            lines.append(f"### {cc.id}: {cc.description}")
            lines.append("")
            lines.append(f"**Command:** `{cc.command}`")
            lines.append("")
            if execution.error_message:
                lines.append(f"**Error:** {execution.error_message}")
                lines.append("")
            if execution.stderr:
                lines.append("**Stderr:**")
                lines.append("```")
                lines.append(execution.stderr.strip()[:500])
                lines.append("```")
                lines.append("")

    return "\n".join(lines)


# =============================================================================
# CLI Commands
# =============================================================================


@click.group("verify")
def cli() -> None:
    """Run verification checks from refined templates."""
    pass


@cli.command("suite")
@click.argument("file", type=click.Path(exists=True))
@click.option("--working-dir", "-C", type=click.Path(exists=True), help="Working directory for commands")
@click.option("--fail-fast", "-x", is_flag=True, help="Stop on first failure")
@click.option("--format", "-f", type=click.Choice(["table", "json", "markdown"]), default="table")
@click.option("--verbose", "-v", is_flag=True, help="Show progress for each check")
@click.option("--output", "-o", type=click.Path(), help="Write report to file")
def suite_command(
    file: str,
    working_dir: Optional[str],
    fail_fast: bool,
    format: str,
    verbose: bool,
    output: Optional[str],
) -> None:
    """Run evaluation suite from a template file.

    Parses <evaluation_suite> blocks from the file and executes all check cases.

    Example:
        phaser verify suite .audit/phases/02-extract-validation.md
    """
    file_path = Path(file)
    content = file_path.read_text()

    # Parse suite
    suite = parse_evaluation_suite(content, str(file_path))

    if not suite.check_cases:
        click.echo(f"No check cases found in {file}")
        sys.exit(0)

    click.echo(f"Found {len(suite.check_cases)} check case(s) in {file}")
    if verbose:
        click.echo("")

    # Run suite
    work_dir = Path(working_dir) if working_dir else None
    report = run_evaluation_suite(suite, work_dir, fail_fast, verbose)

    # Format output
    if format == "json":
        output_text = format_report_json(report)
    elif format == "markdown":
        output_text = format_report_markdown(report)
    else:
        output_text = format_report_table(report)

    # Output
    if output:
        Path(output).write_text(output_text)
        click.echo(f"\nReport written to {output}")
    else:
        click.echo("")
        click.echo(output_text)

    # Exit code
    sys.exit(0 if report.success else 1)


@cli.command("phase")
@click.argument("phase_file", type=click.Path(exists=True))
@click.option("--working-dir", "-C", type=click.Path(exists=True), help="Working directory")
@click.option("--verbose", "-v", is_flag=True, help="Show progress")
def phase_command(phase_file: str, working_dir: Optional[str], verbose: bool) -> None:
    """Check a phase file's verification commands.

    Runs all commands from the ## Verify section and <evaluation_suite> blocks.

    Example:
        phaser verify phase .audit/phases/02-extract-validation.md
    """
    file_path = Path(phase_file)
    content = file_path.read_text()

    # Parse evaluation suite
    suite = parse_evaluation_suite(content, str(file_path))

    # Also parse ## Verify section as fallback
    verify_commands = parse_verify_section(content)
    for i, cmd in enumerate(verify_commands):
        # Skip if already in suite
        if any(cc.command == cmd for cc in suite.check_cases):
            continue
        suite.check_cases.append(
            CheckCase(
                id=f"verify_{i + 1}",
                check_type=CheckType.CUSTOM,
                command=cmd,
                description=f"Verify command {i + 1}",
            )
        )

    if not suite.check_cases:
        click.echo(f"No verification commands found in {phase_file}")
        sys.exit(0)

    click.echo(f"Running {len(suite.check_cases)} verification(s) for {file_path.name}")
    if verbose:
        click.echo("")

    # Run
    work_dir = Path(working_dir) if working_dir else None
    report = run_evaluation_suite(suite, work_dir, fail_fast=False, verbose=verbose)

    # Output
    click.echo("")
    click.echo(format_report_table(report))

    sys.exit(0 if report.success else 1)


@cli.command("context")
@click.argument("context_file", type=click.Path(exists=True))
@click.option("--scenario", "-s", type=str, help="Run specific scenario by ID")
@click.option("--list", "list_scenarios", is_flag=True, help="List available scenarios")
def context_command(context_file: str, scenario: Optional[str], list_scenarios: bool) -> None:
    """Inspect CONTEXT file evaluation scenarios.

    Parses behavioral scenarios from <evaluation_suite> in CONTEXT files.

    Example:
        phaser verify context .audit/CONTEXT.md --list
        phaser verify context .audit/CONTEXT.md --scenario happy_path
    """
    file_path = Path(context_file)
    content = file_path.read_text()

    # Parse scenarios (test_case elements with type attribute)
    scenarios = parse_context_scenarios(content)

    if list_scenarios:
        click.echo(f"Scenarios in {file_path.name}:")
        click.echo("")
        for s in scenarios:
            click.echo(f"  {s['id']:<20} {s['type']:<12} {s['scenario']}")
        return

    if scenario:
        matching = [s for s in scenarios if s["id"] == scenario]
        if not matching:
            click.echo(f"Scenario '{scenario}' not found. Use --list to see available scenarios.")
            sys.exit(1)
        click.echo(f"Scenario: {matching[0]['id']}")
        click.echo(f"Type: {matching[0]['type']}")
        click.echo(f"Description: {matching[0]['scenario']}")
        click.echo("")
        click.echo("Expected behavior:")
        for exp in matching[0]["expected"]:
            click.echo(f"  - {exp}")
        click.echo("")
        click.echo(
            "Note: CONTEXT scenarios are behavioral specifications. "
            "Use 'phaser verify suite' to run executable check cases."
        )
        return

    # Default: show summary
    click.echo(f"Found {len(scenarios)} behavioral scenario(s) in {file_path.name}")
    click.echo("")
    click.echo("Use --list to see scenarios, --scenario <id> for details.")


@cli.command("all")
@click.argument("audit_dir", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Show progress")
@click.option("--format", "-f", type=click.Choice(["table", "json", "markdown"]), default="table")
def all_command(audit_dir: str, verbose: bool, format: str) -> None:
    """Run all checks for an audit directory.

    Checks CONTEXT.md and all phase files in the phases/ subdirectory.

    Example:
        phaser verify all .audit/
    """
    audit_path = Path(audit_dir)

    # Find files to validate
    files_to_validate = []

    context_file = audit_path / "CONTEXT.md"
    if context_file.exists():
        files_to_validate.append(context_file)

    phases_dir = audit_path / "phases"
    if phases_dir.exists():
        for phase_file in sorted(phases_dir.glob("*.md")):
            files_to_validate.append(phase_file)

    if not files_to_validate:
        click.echo(f"No files to validate in {audit_dir}")
        sys.exit(0)

    click.echo(f"Validating {len(files_to_validate)} file(s) in {audit_dir}")
    click.echo("")

    all_reports = []
    total_passed = 0
    total_failed = 0

    for file_path in files_to_validate:
        content = file_path.read_text()
        suite = parse_evaluation_suite(content, str(file_path))

        # Also include ## Verify section
        verify_commands = parse_verify_section(content)
        for i, cmd in enumerate(verify_commands):
            if any(cc.command == cmd for cc in suite.check_cases):
                continue
            suite.check_cases.append(
                CheckCase(
                    id=f"verify_{i + 1}",
                    check_type=CheckType.CUSTOM,
                    command=cmd,
                    description=f"Verify command {i + 1}",
                )
            )

        if not suite.check_cases:
            continue

        click.echo(f"  {file_path.name}: {len(suite.check_cases)} check(s)...", nl=False)

        report = run_evaluation_suite(suite, audit_path.parent, fail_fast=False, verbose=False)
        all_reports.append(report)

        total_passed += report.passed
        total_failed += report.failed

        if report.success:
            click.echo(click.style(" âœ“", fg="green"))
        else:
            click.echo(click.style(f" âœ— ({report.failed} failed)", fg="red"))

    # Summary
    click.echo("")
    click.echo("=" * 50)
    status = click.style("PASSED", fg="green") if total_failed == 0 else click.style("FAILED", fg="red")
    click.echo(f"Overall: {status}")
    click.echo(f"Total: {total_passed} passed, {total_failed} failed")

    sys.exit(0 if total_failed == 0 else 1)


# =============================================================================
# Helpers
# =============================================================================


def parse_verify_section(content: str) -> list[str]:
    """Parse commands from ## Verify section."""
    commands = []

    # Find ## Verify section
    verify_match = re.search(r"## Verify\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if not verify_match:
        return commands

    verify_content = verify_match.group(1)

    # Extract commands (lines that look like bash commands)
    for line in verify_content.split("\n"):
        line = line.strip()
        # Skip empty lines, comments, XML tags
        if not line or line.startswith("#") or line.startswith("<") or line.startswith("```"):
            continue
        # Skip markdown formatting
        if line.startswith("**") or line.startswith("-"):
            continue
        # This is likely a command
        commands.append(line)

    return commands


def parse_context_scenarios(content: str) -> list[dict]:
    """Parse behavioral scenarios from CONTEXT evaluation suite."""
    scenarios = []

    # Find test_case elements with scenario child
    pattern = r"<test_case\s+([^>]+)>\s*(.*?)\s*</test_case>"
    matches = re.findall(pattern, content, re.DOTALL)

    for attrs, case_content in matches:
        case_id = extract_attribute(attrs, "id")
        case_type = extract_attribute(attrs, "type")

        # Extract scenario
        scenario_match = re.search(r"<scenario>(.*?)</scenario>", case_content, re.DOTALL)
        scenario = scenario_match.group(1).strip() if scenario_match else ""

        # Extract expected behaviors
        expected = []
        expected_match = re.search(r"<expected>(.*?)</expected>", case_content, re.DOTALL)
        if expected_match:
            for line in expected_match.group(1).strip().split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    expected.append(line[1:].strip())

        if case_id and scenario:
            scenarios.append(
                {
                    "id": case_id,
                    "type": case_type,
                    "scenario": scenario,
                    "expected": expected,
                }
            )

    return scenarios


# =============================================================================
# Entry point for direct execution
# =============================================================================

if __name__ == "__main__":
    cli()
