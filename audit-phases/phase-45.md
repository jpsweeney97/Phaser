## Phase 45: Negotiate CLI Commands

### Context

With operations implemented, we need a CLI interface. This phase adds both interactive mode and non-interactive commands.

### Goal

Implement the `phaser negotiate` CLI with interactive mode and subcommands.

### Files

**Modify: `tools/negotiate.py`**

Add CLI implementation at the end of the file:

```python
# ============================================================================
# Formatting
# ============================================================================

def format_phase_list(state: NegotiationState) -> str:
    """Format phases as a list for display."""
    lines = []
    lines.append(f"Phases ({state.active_count} active, {len(state.skipped_ids)} skipped):")
    lines.append("")

    for phase in state.current_phases:
        skip_mark = " [SKIP]" if phase.id in state.skipped_ids else ""
        derived_mark = ""
        if phase.split_from:
            derived_mark = f" (split from {phase.split_from})"
        elif phase.merged_from:
            derived_mark = f" (merged from {len(phase.merged_from)} phases)"

        lines.append(
            f"  {phase.number:3}. {phase.title}{skip_mark}{derived_mark}"
        )
        lines.append(f"       Files: {phase.file_count}")

    return '\n'.join(lines)


def format_phase_detail(phase: Phase, is_skipped: bool) -> str:
    """Format a single phase with full details."""
    lines = []

    status = " [SKIPPED]" if is_skipped else ""
    lines.append(f"Phase {phase.number}: {phase.title}{status}")
    lines.append("=" * 60)

    if phase.context:
        lines.append(f"\nContext:\n{phase.context}")

    if phase.goal:
        lines.append(f"\nGoal:\n{phase.goal}")

    if phase.files:
        lines.append(f"\nFiles ({len(phase.files)}):")
        for f in phase.files:
            lines.append(f"  - [{f.action}] {f.path}")

    if phase.plan:
        lines.append("\nPlan:")
        for item in phase.plan:
            lines.append(f"  - {item}")

    if phase.acceptance_criteria:
        lines.append("\nAcceptance Criteria:")
        for item in phase.acceptance_criteria:
            lines.append(f"  - {item}")

    return '\n'.join(lines)


def format_operation_history(state: NegotiationState) -> str:
    """Format operation history."""
    if not state.operations:
        return "No operations recorded."

    lines = [f"Operation History ({len(state.operations)} operations):"]
    lines.append("")

    for i, op in enumerate(state.operations, 1):
        lines.append(f"  {i}. [{op.op_type.value}] {op.description}")
        lines.append(f"       at {op.timestamp}")

    return '\n'.join(lines)


def format_diff(state: NegotiationState) -> str:
    """Format differences between original and current state."""
    lines = ["Changes from original:"]
    lines.append("")

    orig_ids = {p.id for p in state.original_phases}
    curr_ids = {p.id for p in state.current_phases}

    # Removed phases
    removed = orig_ids - curr_ids
    if removed:
        lines.append("Removed:")
        for pid in removed:
            lines.append(f"  - {pid}")

    # Added phases (from splits/merges)
    added = curr_ids - orig_ids
    if added:
        lines.append("Added:")
        for pid in added:
            lines.append(f"  + {pid}")

    # Skipped
    if state.skipped_ids:
        lines.append("Skipped:")
        for pid in state.skipped_ids:
            lines.append(f"  ~ {pid}")

    # Summary
    lines.append("")
    lines.append(f"Original: {len(state.original_phases)} phases")
    lines.append(f"Current:  {state.phase_count} phases ({state.active_count} active)")
    lines.append(f"Operations: {state.operation_count}")

    return '\n'.join(lines)


def generate_negotiated_audit(state: NegotiationState, include_skipped: bool = False) -> str:
    """
    Generate a negotiated audit document.

    Args:
        state: Current negotiation state.
        include_skipped: If True, include skipped phases as comments.

    Returns:
        Markdown content.
    """
    lines = []

    # Header
    lines.append(f"<!-- Negotiated from: {state.source_file} -->")
    lines.append(f"<!-- Operations: {state.operation_count} -->")
    lines.append(f"<!-- Generated: {now_iso()} -->")
    lines.append("")
    lines.append("# Negotiated Audit")
    lines.append("")

    phase_num = 0
    for phase in state.current_phases:
        is_skipped = phase.id in state.skipped_ids

        if is_skipped and not include_skipped:
            continue

        phase_num += 1

        if is_skipped:
            lines.append(f"<!-- SKIPPED: Phase {phase_num}: {phase.title} -->")
            lines.append("")
            continue

        lines.append(f"## Phase {phase_num}: {phase.title}")
        lines.append("")

        if phase.context:
            lines.append("### Context")
            lines.append(phase.context)
            lines.append("")

        if phase.goal:
            lines.append("### Goal")
            lines.append(phase.goal)
            lines.append("")

        if phase.files:
            lines.append("### Files")
            lines.append("")
            for f in phase.files:
                action = f.action.capitalize()
                lines.append(f"**{action}: `{f.path}`**")
                if f.description:
                    lines.append(f.description)
                lines.append("")

        if phase.plan:
            lines.append("### Plan")
            for item in phase.plan:
                lines.append(f"- {item}")
            lines.append("")

        if phase.verification:
            lines.append("### Verification")
            for item in phase.verification:
                lines.append(f"- {item}")
            lines.append("")

        if phase.acceptance_criteria:
            lines.append("### Acceptance Criteria")
            for item in phase.acceptance_criteria:
                lines.append(f"- [ ] {item}")
            lines.append("")

        if phase.rollback:
            lines.append("### Rollback")
            for item in phase.rollback:
                lines.append(f"- {item}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return '\n'.join(lines)


# ============================================================================
# CLI
# ============================================================================

import click


@click.group(invoke_without_command=True)
@click.argument('audit_file', required=False, type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file for negotiated audit')
@click.pass_context
def cli(ctx, audit_file, output):
    """
    Negotiate audit phases before execution.

    Opens an interactive session to customize phases via split, merge,
    reorder, skip, and modify operations.

    Examples:

        phaser negotiate audit.md

        phaser negotiate preview audit.md

        phaser negotiate skip audit.md --phases 5,8,12
    """
    ctx.ensure_object(dict)
    ctx.obj['audit_file'] = audit_file
    ctx.obj['output'] = output

    if ctx.invoked_subcommand is None and audit_file:
        # Start interactive session
        run_interactive_session(audit_file, output)


def run_interactive_session(audit_file: str, output: Optional[str] = None) -> None:
    """Run interactive negotiation session."""
    state, resumed = resume_or_init(audit_file)

    if resumed:
        click.echo(f"Resumed session with {state.operation_count} operations.")
    else:
        click.echo(f"Started new session with {state.phase_count} phases.")

    click.echo("Type 'help' for available commands.\n")

    while True:
        try:
            cmd = input('negotiate> ').strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nExiting without saving.")
            break

        if not cmd:
            continue

        parts = cmd.split()
        command = parts[0].lower()
        args = parts[1:]

        try:
            if command == 'help':
                show_help()
            elif command == 'list':
                click.echo(format_phase_list(state))
            elif command == 'show':
                if not args:
                    click.echo("Usage: show <phase-number>")
                else:
                    phase = validate_phase_exists(state, f"phase-{args[0]}")
                    is_skipped = phase.id in state.skipped_ids
                    click.echo(format_phase_detail(phase, is_skipped))
            elif command == 'split':
                if not args:
                    click.echo("Usage: split <phase-number> [--at N,M,...]")
                else:
                    phase_id = f"phase-{args[0]}"
                    split_at = None
                    if '--at' in args:
                        idx = args.index('--at')
                        if idx + 1 < len(args):
                            split_at = [int(x) for x in args[idx + 1].split(',')]
                    new_phases = op_split(state, phase_id, split_at)
                    click.echo(f"Split into {len(new_phases)} phases.")
            elif command == 'merge':
                if len(args) < 2:
                    click.echo("Usage: merge <phase1> <phase2> [<phase3> ...]")
                else:
                    phase_ids = [f"phase-{a}" for a in args]
                    merged = op_merge(state, phase_ids)
                    click.echo(f"Merged into {merged.id}.")
            elif command == 'reorder':
                if len(args) < 2:
                    click.echo("Usage: reorder <phase-number> <new-position>")
                else:
                    phase_id = f"phase-{args[0]}"
                    new_pos = int(args[1])
                    op_reorder(state, phase_id, new_pos)
                    click.echo(f"Moved to position {new_pos}.")
            elif command == 'skip':
                if not args:
                    click.echo("Usage: skip <phase-number>")
                else:
                    phase_id = f"phase-{args[0]}"
                    op_skip(state, phase_id)
                    click.echo(f"Marked {phase_id} as skipped.")
            elif command == 'unskip':
                if not args:
                    click.echo("Usage: unskip <phase-number>")
                else:
                    phase_id = f"phase-{args[0]}"
                    op_unskip(state, phase_id)
                    click.echo(f"Removed skip from {phase_id}.")
            elif command == 'modify':
                if len(args) < 3:
                    click.echo("Usage: modify <phase-number> <field> <value>")
                else:
                    phase_id = f"phase-{args[0]}"
                    field = args[1]
                    value = ' '.join(args[2:])
                    op_modify(state, phase_id, field, value)
                    click.echo(f"Modified {field}.")
            elif command == 'history':
                click.echo(format_operation_history(state))
            elif command == 'diff':
                click.echo(format_diff(state))
            elif command == 'reset':
                scope = args[0] if args else 'all'
                if scope != 'all':
                    scope = f"phase-{scope}"
                op_reset(state, scope)
                click.echo(f"Reset {scope}.")
            elif command == 'save':
                out_path = output
                if args and args[0] != '--output':
                    out_path = args[0]
                elif '--output' in args:
                    idx = args.index('--output')
                    if idx + 1 < len(args):
                        out_path = args[idx + 1]

                if not out_path:
                    out_path = audit_file.replace('.md', '-negotiated.md')

                content = generate_negotiated_audit(state)
                with open(out_path, 'w') as f:
                    f.write(content)
                click.echo(f"Saved to {out_path}")

                # Also save state
                state_path = get_state_path(audit_file)
                save_negotiation_state(state, state_path)
                click.echo(f"State saved to {state_path}")
            elif command == 'exit' or command == 'quit':
                if state.has_changes:
                    if click.confirm("You have unsaved changes. Exit anyway?"):
                        break
                else:
                    break
            else:
                click.echo(f"Unknown command: {command}. Type 'help' for commands.")
        except NegotiationError as e:
            click.echo(f"Error: {e}")
        except Exception as e:
            click.echo(f"Error: {e}")


def show_help():
    """Show help text for interactive mode."""
    click.echo("""
Available Commands:

  list                    Show all phases with status
  show <phase>            Show phase details
  split <phase> [--at N]  Split phase at file indices
  merge <p1> <p2> ...     Merge multiple phases
  reorder <phase> <pos>   Move phase to position
  skip <phase>            Mark phase as skipped
  unskip <phase>          Remove skip mark
  modify <phase> <f> <v>  Modify phase field
  history                 Show operation history
  diff                    Show changes from original
  reset [<phase>|all]     Reset to original
  save [--output <file>]  Save negotiated audit
  exit                    Exit session
  help                    Show this help
""")


@cli.command()
@click.argument('audit_file', type=click.Path(exists=True))
def preview(audit_file):
    """Preview phases in an audit file."""
    try:
        phases = parse_audit_file(audit_file)
        click.echo(f"Audit: {audit_file}")
        click.echo(f"Phases: {len(phases)}")
        click.echo("")

        total_files = 0
        for phase in phases:
            total_files += phase.file_count
            click.echo(f"  {phase.number:3}. {phase.title}")
            click.echo(f"       {phase.file_count} files")

        click.echo("")
        click.echo(f"Total: {len(phases)} phases, {total_files} files")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command('skip')
@click.argument('audit_file', type=click.Path(exists=True))
@click.option('--phases', '-p', required=True, help='Comma-separated phase numbers to skip')
@click.option('--output', '-o', type=click.Path(), help='Output file')
def skip_phases(audit_file, phases, output):
    """Skip phases without interactive mode."""
    state, _ = resume_or_init(audit_file)

    phase_nums = [int(p.strip()) for p in phases.split(',')]

    for num in phase_nums:
        try:
            op_skip(state, f"phase-{num}")
            click.echo(f"Skipped phase {num}")
        except NegotiationError as e:
            click.echo(f"Warning: {e}")

    out_path = output or audit_file.replace('.md', '-negotiated.md')
    content = generate_negotiated_audit(state)
    with open(out_path, 'w') as f:
        f.write(content)
    click.echo(f"Saved to {out_path}")


@cli.command('apply')
@click.argument('audit_file', type=click.Path(exists=True))
@click.option('--ops', '-o', required=True, type=click.Path(exists=True), help='Operations YAML file')
@click.option('--output', type=click.Path(), help='Output file')
def apply_operations(audit_file, ops, output):
    """Apply operations from a YAML file."""
    state, _ = resume_or_init(audit_file)

    # Load operations from file
    with open(ops, 'r') as f:
        ops_data = yaml.safe_load(f)

    operations = ops_data.get('operations', [])
    click.echo(f"Applying {len(operations)} operations...")

    for op_data in operations:
        op_type = op_data.get('type', op_data.get('op_type'))
        try:
            if op_type == 'skip':
                for target in op_data.get('targets', op_data.get('target_ids', [])):
                    op_skip(state, target)
                    click.echo(f"  Skipped {target}")
            elif op_type == 'unskip':
                for target in op_data.get('targets', op_data.get('target_ids', [])):
                    op_unskip(state, target)
                    click.echo(f"  Unskipped {target}")
            elif op_type == 'reorder':
                target = op_data.get('target', op_data.get('target_ids', [None])[0])
                position = op_data.get('position', op_data.get('params', {}).get('to'))
                op_reorder(state, target, position)
                click.echo(f"  Reordered {target} to position {position}")
            elif op_type == 'split':
                target = op_data.get('target', op_data.get('target_ids', [None])[0])
                split_at = op_data.get('at', op_data.get('params', {}).get('split_at'))
                new_phases = op_split(state, target, split_at)
                click.echo(f"  Split {target} into {len(new_phases)} phases")
            elif op_type == 'merge':
                targets = op_data.get('targets', op_data.get('target_ids', []))
                merged = op_merge(state, targets, force=True)
                click.echo(f"  Merged into {merged.id}")
            elif op_type == 'modify':
                target = op_data.get('target', op_data.get('target_ids', [None])[0])
                field = op_data.get('field', op_data.get('params', {}).get('field'))
                value = op_data.get('value', op_data.get('params', {}).get('value'))
                op_modify(state, target, field, value)
                click.echo(f"  Modified {field} of {target}")
            else:
                click.echo(f"  Unknown operation type: {op_type}")
        except NegotiationError as e:
            click.echo(f"  Error: {e}")

    out_path = output or audit_file.replace('.md', '-negotiated.md')
    content = generate_negotiated_audit(state)
    with open(out_path, 'w') as f:
        f.write(content)
    click.echo(f"Saved to {out_path}")

    # Save state
    state_path = get_state_path(audit_file)
    save_negotiation_state(state, state_path)


@cli.command('export')
@click.argument('audit_file', type=click.Path(exists=True))
@click.option('--output', '-o', required=True, type=click.Path(), help='Output file')
@click.option('--include-skipped', is_flag=True, help='Include skipped phases as comments')
def export_audit(audit_file, output, include_skipped):
    """Export negotiated audit to file."""
    state, resumed = resume_or_init(audit_file)

    if not resumed:
        click.echo("No negotiation session found. Exporting original.")

    content = generate_negotiated_audit(state, include_skipped=include_skipped)
    with open(output, 'w') as f:
        f.write(content)
    click.echo(f"Exported to {output}")


@cli.command()
@click.argument('audit_file', type=click.Path(exists=True))
def status(audit_file):
    """Show negotiation session status."""
    state_path = get_state_path(audit_file)

    if not os.path.exists(state_path):
        click.echo("No negotiation session found for this audit.")
        return

    state = load_negotiation_state(state_path)

    click.echo(f"Audit: {state.source_file}")
    click.echo(f"Created: {state.created_at}")
    click.echo(f"Modified: {state.modified_at}")
    click.echo(f"Original phases: {len(state.original_phases)}")
    click.echo(f"Current phases: {state.phase_count}")
    click.echo(f"Active: {state.active_count}")
    click.echo(f"Skipped: {len(state.skipped_ids)}")
    click.echo(f"Operations: {state.operation_count}")


if __name__ == '__main__':
    cli()
```

### Plan

1. Add formatting functions for display
2. Implement generate_negotiated_audit for export
3. Add interactive session with command loop
4. Add non-interactive subcommands (preview, skip, apply, export, status)

### Verification

```bash
python -m tools.negotiate --help
python -m tools.negotiate preview examples/sample-audit.md 2>/dev/null || echo "Sample needed"
```

### Acceptance Criteria

- [ ] format_phase_list shows all phases with status markers
- [ ] format_phase_detail shows full phase information
- [ ] format_operation_history shows all operations
- [ ] format_diff shows changes from original
- [ ] generate_negotiated_audit produces valid markdown
- [ ] Interactive mode with all commands working
- [ ] preview subcommand shows phase summary
- [ ] skip subcommand skips phases without interaction
- [ ] apply subcommand applies operations from YAML file
- [ ] export subcommand saves negotiated audit
- [ ] status subcommand shows session info

### Rollback

```bash
git checkout HEAD -- tools/negotiate.py
```

### Completion

Phase 45 complete when both interactive and non-interactive CLI modes are functional.

---

