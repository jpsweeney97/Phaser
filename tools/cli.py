"""
Phaser CLI — Unified command-line interface for audit automation.

Usage:
    phaser <command> [options]

Commands:
    diff        Manifest capture and comparison
    contracts   Rule extraction and checking
    simulate    Dry-run audit execution
    branches    Branch-per-phase management
    ci          CI integration commands
    insights    Analytics and statistics
    reverse     Generate audit from git history
    negotiate   Customize phases before execution
    check       Run all contract checks (CI integration)
    version     Show version information
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import pyperclip

from tools.branches import cli as branches_cli
from tools.bridge import (
    validate_document,
    prepare_audit,
    execute_audit,
    ValidationError,
    ParseError,
    ExecutionError,
    PHASER_VERSION,
)
from tools.ci import cli as ci_cli
from tools.contracts import cli as contracts_cli
from tools.diff import cli as diff_cli
from tools.insights import cli as insights_cli
from tools.replay import cli as replay_cli
from tools.negotiate import cli as negotiate_cli
from tools.reverse import cli as reverse_cli
from tools.simulate import cli as simulate_cli


@click.group()
@click.version_option(version="1.5.0", prog_name="phaser")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """Phaser — Audit automation for Claude Code."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


# Register subcommand groups
cli.add_command(diff_cli, name="diff")
cli.add_command(contracts_cli, name="contracts")
cli.add_command(simulate_cli, name="simulate")
cli.add_command(branches_cli, name="branches")
cli.add_command(ci_cli, name="ci")
cli.add_command(insights_cli, name="insights")
cli.add_command(replay_cli, name="replay")
cli.add_command(reverse_cli, name="reverse")
cli.add_command(negotiate_cli, name="negotiate")


@cli.command()
@click.option("--root", type=click.Path(exists=True), default=".")
@click.option("--fail-on-error", is_flag=True, help="Exit 1 if any contract fails")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def check(ctx: click.Context, root: str, fail_on_error: bool, output_format: str) -> None:
    """
    Check all contracts against codebase.

    Designed for CI integration. Returns exit code 1 if any
    contracts fail and --fail-on-error is set.

    Examples:
        phaser check
        phaser check --fail-on-error
        phaser check --format json
    """
    from tools.contracts import check_all_contracts, format_check_results
    from tools.storage import PhaserStorage

    storage = PhaserStorage()
    results = check_all_contracts(storage, Path(root))

    if output_format == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        click.echo(format_check_results(results, verbose=ctx.obj.get("verbose", False)))

    if fail_on_error and any(not r.passed for r in results):
        raise SystemExit(1)

@cli.command()
@click.argument("root", type=click.Path(exists=True), default=".")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), default="yaml")
def manifest(root: str, output: str | None, output_format: str) -> None:
    """
    Capture manifest of directory.

    Alias for 'phaser diff capture'.

    Examples:
        phaser manifest .
        phaser manifest ~/Projects/MyApp -o manifest.yaml
    """
    import yaml

    from tools.diff import capture_manifest

    m = capture_manifest(Path(root))

    if output_format == "yaml":
        content = yaml.dump(m.to_dict(), default_flow_style=False, sort_keys=False)
    else:
        content = json.dumps(m.to_dict(), indent=2)

    if output:
        Path(output).write_text(content)
        click.echo(f"Manifest saved to {output}")
    else:
        click.echo(content)

@cli.command()
def version() -> None:
    """Show version and feature information."""
    click.echo("Phaser v1.5.0")
    click.echo()
    click.echo("Features:")
    click.echo("  * Storage & Events (Learning Loop)")
    click.echo("  * Audit Diffs")
    click.echo("  * Audit Contracts")
    click.echo("  * Simulation")
    click.echo("  * Branch-per-phase")
    click.echo("  * CI Integration")
    click.echo("  * Insights & Analytics")
    click.echo("  * Reverse Audit")
    click.echo("  * Phase Negotiation")

@cli.command()
@click.option("--global", "global_", is_flag=True, help="Show global .phaser/ location")
@click.option("--project", is_flag=True, help="Show project .phaser/ location")
def info(global_: bool, project: bool) -> None:
    """Show Phaser configuration info."""
    from tools.storage import get_global_phaser_dir, get_project_phaser_dir

    if global_ or not project:
        global_dir = get_global_phaser_dir()
        click.echo(f"Global storage: {global_dir}")
        click.echo(f"  Exists: {global_dir.exists()}")

    if project or not global_:
        project_dir = get_project_phaser_dir()
        if project_dir:
            click.echo(f"Project storage: {project_dir}")
            click.echo(f"  Exists: {project_dir.exists()}")
        else:
            click.echo("Project storage: Not in a project with .phaser/")


# =============================================================================
# Bridge Commands
# =============================================================================


@cli.command()
@click.argument("audit_file", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def validate(audit_file: str, strict: bool, output_json: bool) -> None:
    """
    Validate an audit document without executing.

    Checks document structure, phase sections, and content rules.
    """
    audit_path = Path(audit_file)
    content = audit_path.read_text()

    result = validate_document(content, audit_path)

    # In strict mode, warnings become errors
    if strict and result.warnings:
        result.valid = False
        result.errors.extend(result.warnings)
        result.warnings = []

    if output_json:
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        # Console output
        click.echo(f"\nPhaser v{PHASER_VERSION} — Document Validation\n")
        click.echo(f"Validating {audit_path.name}...\n")

        click.echo("Document Structure")
        if result.document_title:
            click.echo(f"  ✓ Document header: {result.document_title}")
        else:
            click.echo("  ⚠ Missing document header")

        if result.phase_count > 0:
            click.echo(f"  ✓ {result.phase_count} phases detected ({result.phase_range})")
        else:
            click.echo("  ✗ No phases detected")

        # Show errors
        if result.errors:
            click.echo("\nErrors")
            for err in result.errors:
                phase_str = f"Phase {err.phase}: " if err.phase else ""
                click.echo(f"  ✗ {phase_str}{err.message}")

        # Show warnings
        if result.warnings:
            click.echo("\nWarnings")
            for warn in result.warnings:
                phase_str = f"Phase {warn.phase}: " if warn.phase else ""
                click.echo(f"  ⚠ {phase_str}{warn.message}")

        # Token estimates
        if result.token_estimates:
            click.echo("\nToken Estimates")
            for key, value in result.token_estimates.items():
                if key != "total":
                    phase_num = key.replace("phase_", "")
                    status = "✓" if value < 20000 else ("⚠" if value < 25000 else "✗")
                    click.echo(f"  Phase {phase_num}: {value:,} tokens {status}")
            if "total" in result.token_estimates:
                click.echo(f"  Total: {result.token_estimates['total']:,} tokens")

        # Summary
        click.echo(f"\nSummary")
        click.echo(f"  Errors:   {len(result.errors)}")
        click.echo(f"  Warnings: {len(result.warnings)}")

        if result.valid:
            if result.warnings:
                click.echo("\n✓ Document is valid (with warnings)")
            else:
                click.echo("\n✓ Document is valid")
        else:
            click.echo("\n✗ Validation failed. Fix errors before execution.")

    # Exit code
    raise SystemExit(0 if result.valid else 1)


@cli.command()
@click.argument("audit_file", type=click.Path(exists=True))
@click.option("--project", type=click.Path(), default=".", help="Target project directory")
@click.option("--output-dir", type=click.Path(), default="audit-phases", help="Phase files directory")
@click.option("--no-clipboard", is_flag=True, help="Don't copy prompt to clipboard")
@click.option("--print-prompt", is_flag=True, help="Print prompt to stdout")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--skip-validation", is_flag=True, help="Skip document validation")
@click.option("--force", is_flag=True, help="Overwrite existing audit-phases/")
def prepare(
    audit_file: str,
    project: str,
    output_dir: str,
    no_clipboard: bool,
    print_prompt: bool,
    dry_run: bool,
    skip_validation: bool,
    force: bool,
) -> None:
    """
    Prepare an audit document for Claude Code execution.

    Validates, parses, and splits the audit document into phase files,
    then generates the execution prompt.
    """
    audit_path = Path(audit_file).resolve()
    project_path = Path(project).resolve()

    click.echo(f"\nPhaser v{PHASER_VERSION} — Audit Bridge\n")

    if dry_run:
        click.echo(f"[DRY RUN] Would prepare {audit_path.name}")
        click.echo(f"[DRY RUN] Project: {project_path}")
        click.echo(f"[DRY RUN] Output: {project_path / output_dir}")
        return

    try:
        result = prepare_audit(
            audit_path=audit_path,
            project_dir=project_path,
            output_dir=Path(output_dir),
            skip_validation=skip_validation,
            force=force,
        )

        # Validation results
        if not skip_validation:
            click.echo(f"Validating {audit_path.name}...")
            if result.validation.errors:
                for err in result.validation.errors:
                    click.echo(f"  ✗ {err.message}")
            if result.validation.warnings:
                for warn in result.validation.warnings:
                    click.echo(f"  ⚠ {warn.message}")
            click.echo(f"Validation: {len(result.validation.errors)} errors, {len(result.validation.warnings)} warnings\n")

        # Files created
        click.echo("Preparing files...")
        click.echo(f"  ✓ Created {result.meta_dir.name}/phaser-version")
        click.echo(f"  ✓ Created {result.meta_dir.name}/baseline-tests")
        click.echo(f"  ✓ Created {result.setup_file.relative_to(project_path)}")
        for pf in result.phase_files:
            click.echo(f"  ✓ Created {pf.relative_to(project_path)}")
        click.echo(f"  ✓ Copied AUDIT.md to project root\n")

        # Prompt handling
        if not no_clipboard:
            try:
                pyperclip.copy(result.prompt)
                click.echo("✓ Execution prompt copied to clipboard")
            except Exception:
                click.echo("⚠ Could not copy to clipboard (pyperclip not available)")
                print_prompt = True

        if print_prompt:
            click.echo("\n--- EXECUTION PROMPT ---")
            click.echo(result.prompt)
            click.echo("--- END PROMPT ---\n")

    except (ParseError, ValidationError, FileExistsError) as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1)


@cli.command("execute")
@click.argument("audit_file", type=click.Path(exists=True))
@click.option("--project", type=click.Path(), default=".", help="Target project directory")
@click.option("--output-dir", type=click.Path(), default="audit-phases", help="Phase files directory")
@click.option("--no-permissions", is_flag=True, help="Don't use --dangerously-skip-permissions")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--skip-validation", is_flag=True, help="Skip document validation")
@click.option("--force", is_flag=True, help="Overwrite existing audit-phases/")
def execute_cmd(
    audit_file: str,
    project: str,
    output_dir: str,
    no_permissions: bool,
    dry_run: bool,
    skip_validation: bool,
    force: bool,
) -> None:
    """
    Prepare and execute an audit document with Claude Code.

    Validates, parses, splits, generates the prompt, and launches
    Claude Code to execute autonomously.
    """
    audit_path = Path(audit_file).resolve()
    project_path = Path(project).resolve()

    click.echo(f"\nPhaser v{PHASER_VERSION} — Audit Bridge\n")

    if dry_run:
        click.echo(f"[DRY RUN] Would execute {audit_path.name}")
        click.echo(f"[DRY RUN] Project: {project_path}")
        click.echo(f"[DRY RUN] Output: {project_path / output_dir}")
        click.echo(f"[DRY RUN] Skip permissions: {not no_permissions}")
        return

    try:
        # First prepare
        result = prepare_audit(
            audit_path=audit_path,
            project_dir=project_path,
            output_dir=Path(output_dir),
            skip_validation=skip_validation,
            force=force,
        )

        # Show validation results
        if not skip_validation:
            click.echo(f"Validating {audit_path.name}...")
            if result.validation.warnings:
                for warn in result.validation.warnings:
                    click.echo(f"  ⚠ {warn.message}")
            click.echo(f"Validation: {len(result.validation.errors)} errors, {len(result.validation.warnings)} warnings ✓\n")

        # Show files created
        click.echo("Preparing files...")
        click.echo(f"  ✓ Created {result.setup_file.relative_to(project_path)}")
        for pf in result.phase_files:
            click.echo(f"  ✓ Created {pf.relative_to(project_path)}")
        click.echo(f"  ✓ Copied AUDIT.md to project root\n")

        # Check Claude Code
        import shutil
        if not shutil.which("claude"):
            click.echo("✗ Claude Code not found. Install from https://claude.ai/code", err=True)
            raise SystemExit(1)

        # Launch Claude Code
        click.echo("Launching Claude Code...")
        click.echo("  Passing prompt via stdin...\n")

        from tools.bridge import launch_claude_code
        process = launch_claude_code(
            prompt=result.prompt,
            project_dir=result.project_dir,
            skip_permissions=not no_permissions,
        )

        click.echo("Claude Code is running. Execution will proceed autonomously.")
        click.echo("Upon completion, EXECUTION_REPORT.md will be generated.")

    except (ParseError, ValidationError, ExecutionError, FileExistsError) as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1)


def main() -> None:
    """Entry point for the phaser command."""
    cli(obj={})

if __name__ == "__main__":
    main()
