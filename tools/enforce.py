"""Hook-based contract enforcement for Phaser."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click

from tools.contract_loader import Contract, load_contracts
from tools.ignore_parser import filter_violations
from tools.tool_input import ProposedFile, reconstruct


@dataclass
class Violation:
    """A contract violation."""

    rule_id: str
    file_path: str
    line_number: Optional[int]
    matched_text: str
    message: str
    severity: str


@dataclass
class EnforceResult:
    """Result of enforcement check."""

    decision: str  # "allow" or "deny"
    reason: str
    violations: list[Violation] = field(default_factory=list)


def read_hook_input() -> dict:
    """Read and parse hook input from stdin."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON input: {e}")


def format_hook_output(result: EnforceResult, hook_event: str) -> dict:
    """Format result as Claude Code hook output."""
    if hook_event == "PreToolUse":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow" if result.decision == "allow" else "deny",
                "permissionDecisionReason": result.reason,
            }
        }
    elif hook_event == "PostToolUse":
        if result.decision == "allow":
            return {}
        return {
            "decision": "block",
            "reason": result.reason,
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": result.reason,
            },
        }
    return {}


def check_forbid_pattern(
    contract: Contract, content: str, file_path: str
) -> list[Violation]:
    """Check for forbidden patterns in content."""
    violations: list[Violation] = []
    pattern = contract.compiled_pattern
    if not pattern:
        return violations

    lines = content.splitlines()
    for line_num, line in enumerate(lines, start=1):
        for match in pattern.finditer(line):
            violations.append(
                Violation(
                    rule_id=contract.rule_id,
                    file_path=file_path,
                    line_number=line_num,
                    matched_text=match.group(),
                    message=contract.message,
                    severity=contract.severity,
                )
            )
    return violations


def check_require_pattern(
    contract: Contract, content: str, file_path: str
) -> list[Violation]:
    """Check that required pattern exists in content."""
    pattern = contract.compiled_pattern
    if not pattern:
        return []

    if not pattern.search(content):
        return [
            Violation(
                rule_id=contract.rule_id,
                file_path=file_path,
                line_number=None,
                matched_text="",
                message=contract.message,
                severity=contract.severity,
            )
        ]
    return []


def check_contract(contract: Contract, proposed: ProposedFile) -> list[Violation]:
    """Check a single contract against proposed file content."""
    if not contract.matches_file(proposed.path):
        return []

    if contract.type == "forbid_pattern":
        return check_forbid_pattern(contract, proposed.content, proposed.path)
    elif contract.type == "require_pattern":
        return check_require_pattern(contract, proposed.content, proposed.path)
    elif contract.type == "file_contains":
        return check_require_pattern(contract, proposed.content, proposed.path)
    elif contract.type == "file_not_contains":
        return check_forbid_pattern(contract, proposed.content, proposed.path)
    # file_exists and file_not_exists are not applicable to content checking
    return []


def check_all_contracts(
    contracts: list[Contract],
    proposed_files: list[ProposedFile],
    severity_filter: Optional[str] = None,
) -> list[Violation]:
    """Check all contracts against all proposed files."""
    violations: list[Violation] = []

    for proposed in proposed_files:
        for contract in contracts:
            if severity_filter and severity_filter != "all":
                if contract.severity != severity_filter:
                    continue
            file_violations = check_contract(contract, proposed)
            violations.extend(file_violations)

    return violations


@click.command("enforce")
@click.option("--stdin", is_flag=True, help="Read hook input from stdin")
@click.option(
    "--severity",
    type=click.Choice(["error", "warning", "all"]),
    default="all",
    help="Filter by severity",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["hook", "json", "text"]),
    default=None,
    help="Output format",
)
def enforce_command(
    stdin: bool, severity: str, output_format: Optional[str]
) -> None:
    """Check contracts against proposed file changes."""
    if not stdin:
        click.echo("Error: --stdin is required for hook integration", err=True)
        sys.exit(3)

    # Read input
    hook_input = read_hook_input()
    hook_event = hook_input.get("hook_event_name", "PreToolUse")
    cwd = hook_input.get("cwd", ".")

    # Reconstruct proposed state
    reconstruction = reconstruct(hook_input)
    if reconstruction.skipped:
        # Cannot check, allow by default
        output = format_hook_output(
            EnforceResult("allow", reconstruction.skip_reason or "Skipped"),
            hook_event,
        )
        if output:
            click.echo(json.dumps(output))
        sys.exit(0)

    # Load contracts
    load_result = load_contracts(project_root=Path(cwd))

    # Check contracts
    all_violations = check_all_contracts(
        load_result.contracts,
        reconstruction.files,
        severity_filter=severity,
    )

    # Apply ignore directives
    violations: list[Violation] = []
    for proposed in reconstruction.files:
        file_violations = [v for v in all_violations if v.file_path == proposed.path]
        kept, _ = filter_violations(file_violations, proposed.path, proposed.content)
        violations.extend(kept)

    # Build result
    if violations:
        # Format violation message
        v = violations[0]  # Report first violation
        reason = f"Contract violation: {v.rule_id}"
        if v.line_number:
            reason += f" at line {v.line_number}"
        reason += f". {v.message}"

        result = EnforceResult("deny", reason, violations)
    else:
        result = EnforceResult("allow", "All contracts passed")

    # Output
    output = format_hook_output(result, hook_event)
    if output:
        click.echo(json.dumps(output))

    sys.exit(0)


HOOK_CONFIG = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": "phaser enforce check --stdin --severity error",
                        "timeout": 60,
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": "phaser enforce check --stdin --severity warning",
                        "timeout": 60,
                    }
                ],
            }
        ],
    }
}


@click.command("install")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "local"]),
    default="project",
    help="Where to install hooks",
)
@click.option("--dry-run", is_flag=True, help="Print config without writing")
@click.option("--force", is_flag=True, help="Overwrite existing hooks")
def install_command(scope: str, dry_run: bool, force: bool) -> None:
    """Install hook configuration for Claude Code."""
    # Determine target file
    if scope == "user":
        settings_path = Path.home() / ".claude" / "settings.json"
    elif scope == "project":
        settings_path = Path(".claude") / "settings.json"
    else:  # local
        settings_path = Path(".claude") / "settings.local.json"

    if dry_run:
        click.echo(f"Would write to: {settings_path}")
        click.echo(json.dumps(HOOK_CONFIG, indent=2))
        return

    # Create directory if needed
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing or create new
    existing: dict = {}
    if settings_path.exists():
        with open(settings_path) as f:
            existing = json.load(f)

    # Check for existing hooks
    if "hooks" in existing and not force:
        click.echo("Hooks already configured. Use --force to overwrite.", err=True)
        sys.exit(1)

    # Merge
    existing["hooks"] = HOOK_CONFIG["hooks"]

    # Write
    with open(settings_path, "w") as f:
        json.dump(existing, f, indent=2)

    click.echo(f"Installed hooks to {settings_path}")


if __name__ == "__main__":
    enforce_command()
