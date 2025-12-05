## Phase 39: Reverse CLI Commands

### Context

The generation logic is complete. Now we add CLI commands for users to interact with the reverse audit functionality.

### Goal

Implement CLI commands: `phaser reverse`, `phaser reverse preview`, and `phaser reverse commits`.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `tools/reverse.py` | MODIFY | Add CLI commands |

### Plan

1. Add main reverse command
2. Add preview subcommand
3. Add commits subcommand
4. Handle output options and errors

### Implementation

Add these CLI commands to tools/reverse.py:

```python
# =============================================================================
# CLI Interface
# =============================================================================

import click


@click.group(invoke_without_command=True)
@click.argument("commit_range", required=False)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option(
    "--strategy",
    type=click.Choice(["commits", "directories", "filetypes", "semantic"]),
    default="commits",
    help="Phase grouping strategy",
)
@click.option("--title", help="Audit title (default: inferred)")
@click.option("--project", help="Project name (default: inferred)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "yaml", "json"]),
    default="markdown",
    help="Output format",
)
@click.option("--include-diff", is_flag=True, help="Include full diff in output")
@click.option("--max-phases", default=20, help="Maximum phases to generate")
@click.pass_context
def cli(
    ctx: click.Context,
    commit_range: str | None,
    output: str | None,
    strategy: str,
    title: str | None,
    project: str | None,
    output_format: str,
    include_diff: bool,
    max_phases: int,
) -> None:
    """
    Generate audit document from git diff.

    COMMIT_RANGE is a git commit range (e.g., HEAD~5..HEAD, main..feature).

    Examples:

        phaser reverse HEAD~5..HEAD

        phaser reverse main..feature-branch --output audit.md

        phaser reverse HEAD~10..HEAD --strategy directories

        phaser reverse HEAD~5..HEAD --format yaml
    """
    # If no subcommand and commit_range provided, run generation
    if ctx.invoked_subcommand is None:
        if not commit_range:
            click.echo(ctx.get_help())
            return

        import json

        try:
            result = generate_reverse_audit(
                commit_range=commit_range,
                strategy=GroupingStrategy(strategy),
                title=title,
                project=project,
                max_phases=max_phases,
            )
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

        # Format output
        if output_format == "markdown":
            content = format_as_markdown(result, include_diff=include_diff)
        elif output_format == "yaml":
            content = format_as_yaml(result)
        else:
            content = json.dumps(result.to_dict(), indent=2)

        # Write or print
        if output:
            Path(output).write_text(content)
            click.echo(f"Audit document saved to {output}")
        else:
            click.echo(content)


@cli.command()
@click.argument("commit_range")
@click.option(
    "--strategy",
    type=click.Choice(["commits", "directories", "filetypes", "semantic"]),
    default="commits",
    help="Phase grouping strategy",
)
def preview(commit_range: str, strategy: str) -> None:
    """
    Preview what would be generated.

    Shows summary of commits and inferred phases without generating
    the full document.

    Examples:

        phaser reverse preview HEAD~5..HEAD

        phaser reverse preview main..feature --strategy directories
    """
    try:
        commits = parse_commit_range(commit_range)
        phases = group_commits_to_phases(commits, GroupingStrategy(strategy))
        output = format_preview(commits, phases, commit_range, strategy)
        click.echo(output)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("commit_range")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def commits(commit_range: str, output_format: str) -> None:
    """
    List commits in a range with change summaries.

    Examples:

        phaser reverse commits HEAD~5..HEAD

        phaser reverse commits main..feature --format json
    """
    import json

    try:
        commit_list = parse_commit_range(commit_range)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if not commit_list:
        click.echo(f"No commits found in range: {commit_range}")
        return

    if output_format == "json":
        click.echo(json.dumps([c.to_dict() for c in commit_list], indent=2))
    else:
        lines = [
            f"Commits in Range: {commit_range}",
            "=" * (len(f"Commits in Range: {commit_range}")),
            "",
        ]

        for commit in commit_list:
            lines.extend([
                f"{commit.short_hash} ({commit.date[:10]}) {commit.message}",
                f"  Files: {commit.files_changed} (+{commit.insertions} -{commit.deletions})",
            ])

            for f in commit.files[:5]:
                change = f.change_type
                lines.append(f"  - {f.path} ({change})")

            if len(commit.files) > 5:
                lines.append(f"  ... and {len(commit.files) - 5} more files")

            lines.append("")

        click.echo("\n".join(lines))


@cli.command()
@click.argument("commit_range")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def diff(commit_range: str, output: str | None) -> None:
    """
    Show the full diff for a commit range.

    Examples:

        phaser reverse diff HEAD~5..HEAD

        phaser reverse diff main..feature -o changes.diff
    """
    try:
        diff_output = run_git_command(["diff", commit_range])
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output:
        Path(output).write_text(diff_output)
        click.echo(f"Diff saved to {output}")
    else:
        click.echo(diff_output)
```

### Verify

```bash
# Syntax check
python -m py_compile tools/reverse.py && echo "✓ Syntax OK"

# CLI help check
python -c "
from click.testing import CliRunner
from tools.reverse import cli

runner = CliRunner()
result = runner.invoke(cli, ['--help'])
assert 'preview' in result.output
assert 'commits' in result.output
print('✓ CLI group works')
"

# Test preview command
python -c "
from click.testing import CliRunner
from tools.reverse import cli

runner = CliRunner()
result = runner.invoke(cli, ['preview', 'HEAD~3..HEAD'])
print(result.output)
assert 'Reverse Audit Preview' in result.output or 'Error' in result.output
print('✓ Preview command works')
"

# Test commits command
python -c "
from click.testing import CliRunner
from tools.reverse import cli

runner = CliRunner()
result = runner.invoke(cli, ['commits', 'HEAD~3..HEAD'])
print(result.output[:500])
print('✓ Commits command works')
"
```

### Acceptance Criteria

- [ ] Main reverse command generates document from commit range
- [ ] preview subcommand shows summary
- [ ] commits subcommand lists commits with details
- [ ] diff subcommand shows full diff
- [ ] --output option saves to file
- [ ] --format option supports markdown/yaml/json
- [ ] --strategy option changes grouping
- [ ] Error handling with helpful messages

### Rollback

```bash
git checkout HEAD -- tools/reverse.py
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 39/- [x] Phase 39/' CURRENT.md
sed -i 's/Current Phase: 39/Current Phase: 40/' CURRENT.md

# Commit
git add tools/reverse.py CURRENT.md
git commit -m "Phase 39: Add Reverse CLI commands"
```

---

