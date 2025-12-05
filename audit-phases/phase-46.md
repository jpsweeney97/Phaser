## Phase 46: CLI Integration

### Context

The negotiate CLI is implemented but needs to be registered with the main phaser command.

### Goal

Integrate `phaser negotiate` into the main CLI and ensure version consistency.

### Files

**Modify: `tools/cli.py`**

```python
# Add import (after existing imports around line 5-10)
from tools.negotiate import cli as negotiate_cli

# Add command registration (after other add_command calls)
cli.add_command(negotiate_cli, name="negotiate")
```

The full modified file should look like:

```python
"""Phaser CLI - Unified command-line interface."""

import click

from tools.reverse import cli as reverse_cli
from tools.branches import cli as branches_cli
from tools.contracts import cli as contracts_cli
from tools.diff import cli as diff_cli
from tools.simulate import cli as simulate_cli
from tools.negotiate import cli as negotiate_cli


@click.group()
@click.version_option(version="1.5.0", prog_name="phaser")
def cli():
    """Phaser - Audit automation for Claude Code."""
    pass


@cli.command()
def version():
    """Show version information."""
    click.echo("Phaser v1.5.0")
    click.echo("")
    click.echo("Features:")
    click.echo("  - Branch-per-Phase Mode")
    click.echo("  - Contract Enforcement")
    click.echo("  - Manifest Diffing")
    click.echo("  - Dry-Run Simulation")
    click.echo("  - Reverse Audit")
    click.echo("  - Phase Negotiation")


# Register subcommands
cli.add_command(reverse_cli, name="reverse")
cli.add_command(branches_cli, name="branches")
cli.add_command(contracts_cli, name="contracts")
cli.add_command(diff_cli, name="diff")
cli.add_command(simulate_cli, name="simulate")
cli.add_command(negotiate_cli, name="negotiate")


if __name__ == '__main__':
    cli()
```

### Plan

1. Add import for negotiate_cli
2. Register negotiate command
3. Update version command feature list

### Verification

```bash
phaser --help | grep negotiate
phaser negotiate --help
phaser version | grep Negotiation
```

### Acceptance Criteria

- [ ] `phaser negotiate` command available
- [ ] `phaser version` shows "Phase Negotiation" in features
- [ ] All negotiate subcommands accessible via phaser CLI

### Rollback

```bash
git checkout HEAD -- tools/cli.py
```

### Completion

Phase 46 complete when `phaser negotiate` is fully integrated.

---

