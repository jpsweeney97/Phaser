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
    check       Run all contract checks (CI integration)
    version     Show version information
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from tools.branches import cli as branches_cli
from tools.ci import cli as ci_cli
from tools.contracts import cli as contracts_cli
from tools.diff import cli as diff_cli
from tools.insights import cli as insights_cli
from tools.simulate import cli as simulate_cli


@click.group()
@click.version_option(version="1.3.0", prog_name="phaser")
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
    click.echo("Phaser v1.3.0")
    click.echo()
    click.echo("Features:")
    click.echo("  * Storage & Events (Learning Loop)")
    click.echo("  * Audit Diffs")
    click.echo("  * Audit Contracts")
    click.echo("  * Simulation")
    click.echo("  * Branch-per-phase")
    click.echo("  * CI Integration")
    click.echo("  * Insights & Analytics")
    click.echo()
    click.echo("Batch 2 (coming soon):")
    click.echo("  - Audit Replay")
    click.echo("  - Reverse Audit")
    click.echo("  - Phase Negotiation")


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


def main() -> None:
    """Entry point for the phaser command."""
    cli(obj={})


if __name__ == "__main__":
    main()
