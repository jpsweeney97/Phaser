## Phase 40: CLI Integration

### Context

The reverse module is complete. Now we integrate it with the main CLI and update the version.

### Goal

Register the reverse subcommand group in the main CLI and update version information.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `tools/cli.py` | MODIFY | Add reverse subcommand |
| `pyproject.toml` | MODIFY | Update version to 1.5.0 |

### Plan

1. Import reverse CLI module
2. Register subcommand group
3. Update version string
4. Update version command output

### Implementation

#### tools/cli.py modifications

Add import:

```python
from tools.reverse import cli as reverse_cli
```

Add command registration:

```python
cli.add_command(reverse_cli, name="reverse")
```

Update version:

```python
@click.group()
@click.version_option(version="1.5.0", prog_name="phaser")
```

Update version command:

```python
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
    click.echo("  * Audit Replay")
    click.echo("  * Reverse Audit")
    click.echo()
    click.echo("Batch 2 (coming soon):")
    click.echo("  - Phase Negotiation")
```

#### pyproject.toml modification

```toml
[project]
name = "phaser"
version = "1.5.0"
```

### Verify

```bash
# Syntax check
python -m py_compile tools/cli.py && echo "✓ Syntax OK"

# Check subcommand is registered
python -m tools.cli --help | grep reverse
# Expected: reverse should appear in commands

# Check version
python -m tools.cli version | head -1
# Expected: Phaser v1.5.0

# Check reverse subcommand
python -m tools.cli reverse --help
# Expected: Shows preview, commits, diff commands

# Check pyproject.toml version
grep 'version = "1.5.0"' pyproject.toml && echo "✓ Version updated"
```

### Acceptance Criteria

- [ ] tools/cli.py imports reverse module
- [ ] reverse subcommand group registered
- [ ] phaser reverse --help shows all commands
- [ ] Version updated to 1.5.0 in CLI
- [ ] Version updated to 1.5.0 in pyproject.toml
- [ ] All existing commands still work

### Rollback

```bash
git checkout HEAD -- tools/cli.py pyproject.toml
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 40/- [x] Phase 40/' CURRENT.md
sed -i 's/Current Phase: 40/Current Phase: 41/' CURRENT.md

# Commit
git add tools/cli.py pyproject.toml CURRENT.md
git commit -m "Phase 40: Integrate Reverse into main CLI"
```

---

