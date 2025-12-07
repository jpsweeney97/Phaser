"""Hook-based contract enforcement for Phaser."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Optional

import click


@dataclass
class EnforceResult:
    """Result of enforcement check."""

    decision: str  # "allow" or "deny"
    reason: str
    violations: list = field(default_factory=list)


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

    # Determine hook event
    hook_event = hook_input.get("hook_event_name", "PreToolUse")

    # Skeleton: always allow
    result = EnforceResult(
        decision="allow", reason="Phaser enforce connected (skeleton mode)"
    )

    # Format and output
    output = format_hook_output(result, hook_event)
    if output:
        click.echo(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    enforce_command()
