## Phase 44: Negotiation Operations

### Context

With data structures in place, we need to implement the actual negotiation operations: split, merge, reorder, skip/unskip, modify, and reset.

### Goal

Implement all six negotiation operations with proper validation and history tracking.

### Files

**Modify: `tools/negotiate.py`**

Add the following after the existing code:

```python
# ============================================================================
# Validation
# ============================================================================

class NegotiationError(Exception):
    """Error during negotiation operation."""
    pass


def validate_phase_exists(state: NegotiationState, phase_id: str) -> Phase:
    """
    Validate that a phase exists in current state.

    Raises NegotiationError if not found.
    """
    phase = state.get_phase(phase_id)
    if phase is None:
        # Try by number
        try:
            number = int(phase_id.replace('phase-', ''))
            phase = state.get_phase_by_number(number)
        except ValueError:
            pass

    if phase is None:
        raise NegotiationError(f"Phase '{phase_id}' not found. Use 'list' to see phases.")

    return phase


def validate_position(state: NegotiationState, position: int) -> None:
    """
    Validate that a position is valid.

    Raises NegotiationError if out of range.
    """
    max_pos = len(state.current_phases)
    if position < 1 or position > max_pos:
        raise NegotiationError(f"Position {position} out of range (1-{max_pos}).")


def validate_split(phase: Phase) -> None:
    """
    Validate that a phase can be split.

    Raises NegotiationError if not splittable.
    """
    if phase.file_count < 2:
        raise NegotiationError(
            f"Phase has only {phase.file_count} file(s). Need at least 2 to split."
        )


def validate_merge(state: NegotiationState, phase_ids: List[str]) -> List[Phase]:
    """
    Validate that phases can be merged.

    Returns list of phases to merge.
    Raises NegotiationError if invalid.
    """
    if len(phase_ids) < 2:
        raise NegotiationError("Need at least 2 phases to merge.")

    phases = []
    for pid in phase_ids:
        phases.append(validate_phase_exists(state, pid))

    return phases


def check_consecutive(phases: List[Phase]) -> bool:
    """Check if phases are consecutive by number."""
    numbers = sorted(p.number for p in phases)
    for i in range(1, len(numbers)):
        if numbers[i] != numbers[i-1] + 1:
            return False
    return True


# ============================================================================
# Operations
# ============================================================================

def renumber_phases(phases: List[Phase]) -> None:
    """Renumber phases sequentially starting from 1."""
    for i, phase in enumerate(phases, 1):
        phase.number = i
        # Only update simple phase-N IDs, not derived ones (with suffixes like phase-2a)
        if phase.id.startswith('phase-') and not phase.is_derived:
            # Check if ID is just phase-N (no suffix)
            if re.match(r'^phase-\d+$', phase.id):
                phase.id = f"phase-{i}"


def record_operation(
    state: NegotiationState,
    op_type: OpType,
    target_ids: List[str],
    params: Dict[str, Any] = None,
    description: str = ""
) -> None:
    """Record an operation in the state history."""
    op = NegotiationOp(
        op_type=op_type,
        timestamp=now_iso(),
        target_ids=target_ids,
        params=params or {},
        description=description,
    )
    state.operations.append(op)
    state.modified_at = now_iso()


def op_split(
    state: NegotiationState,
    phase_id: str,
    split_at: Optional[List[int]] = None
) -> List[Phase]:
    """
    Split a phase into multiple phases.

    Args:
        state: Current negotiation state.
        phase_id: ID of phase to split.
        split_at: Optional list of file indices to split at.
                  If None, splits each file into its own phase.

    Returns:
        List of new phases created.
    """
    phase = validate_phase_exists(state, phase_id)
    validate_split(phase)

    # Store original ID before any modifications
    original_phase_id = phase.id

    # Default: split at every file
    if split_at is None:
        split_at = list(range(1, phase.file_count))

    # Create split points
    points = [0] + sorted(split_at) + [phase.file_count]
    new_phases = []

    for i in range(len(points) - 1):
        start, end = points[i], points[i + 1]
        files = phase.files[start:end]

        if not files:
            continue

        suffix = chr(ord('a') + i)
        new_id = f"{original_phase_id}{suffix}"

        new_phase = Phase(
            id=new_id,
            number=phase.number,  # Will be renumbered
            title=f"{phase.title} (Part {i + 1})",
            context=phase.context,
            goal=phase.goal if i == 0 else f"Continue: {phase.goal}",
            files=files,
            plan=phase.plan if i == 0 else [],
            verification=phase.verification if i == len(points) - 2 else [],
            acceptance_criteria=phase.acceptance_criteria if i == len(points) - 2 else [],
            rollback=phase.rollback,
            split_from=original_phase_id,
        )
        new_phases.append(new_phase)

    # Replace original phase with new phases
    idx = state.current_phases.index(phase)
    state.current_phases = (
        state.current_phases[:idx] +
        new_phases +
        state.current_phases[idx + 1:]
    )

    renumber_phases(state.current_phases)
    record_operation(
        state, OpType.SPLIT, [original_phase_id],
        params={"split_at": split_at, "new_count": len(new_phases)},
        description=f"Split {original_phase_id} into {len(new_phases)} phases"
    )

    return new_phases


def op_merge(state: NegotiationState, phase_ids: List[str], force: bool = False) -> Phase:
    """
    Merge multiple phases into one.

    Args:
        state: Current negotiation state.
        phase_ids: IDs of phases to merge.
        force: If True, skip consecutive check warning.

    Returns:
        The merged phase.
    """
    phases = validate_merge(state, phase_ids)

    # Warn if non-consecutive (unless forced)
    if not force and not check_consecutive(phases):
        import click
        if not click.confirm("Phases are non-consecutive. Merge anyway?"):
            raise NegotiationError("Merge cancelled.")

    # Sort by current position
    phases_sorted = sorted(phases, key=lambda p: p.number)

    # Combine content
    merged_files = []
    merged_plan = []
    merged_verification = []
    merged_criteria = []
    merged_rollback = []

    for p in phases_sorted:
        merged_files.extend(p.files)
        merged_plan.extend(p.plan)
        merged_verification.extend(p.verification)
        merged_criteria.extend(p.acceptance_criteria)
        merged_rollback.extend(p.rollback)

    # Create merged phase
    first = phases_sorted[0]
    merged = Phase(
        id=first.id,
        number=first.number,
        title=f"{first.title} (Merged)",
        context=first.context,
        goal=first.goal,
        files=merged_files,
        plan=merged_plan,
        verification=merged_verification,
        acceptance_criteria=merged_criteria,
        rollback=merged_rollback,
        merged_from=[p.id for p in phases_sorted],
    )

    # Remove original phases and insert merged
    for p in phases_sorted:
        state.current_phases.remove(p)

    # Insert at first phase's position
    insert_idx = first.number - 1
    if insert_idx > len(state.current_phases):
        insert_idx = len(state.current_phases)
    state.current_phases.insert(insert_idx, merged)

    renumber_phases(state.current_phases)
    record_operation(
        state, OpType.MERGE, phase_ids,
        params={"merged_id": merged.id},
        description=f"Merged {len(phase_ids)} phases into {merged.id}"
    )

    return merged


def op_reorder(state: NegotiationState, phase_id: str, new_position: int) -> None:
    """
    Move a phase to a new position.

    Args:
        state: Current negotiation state.
        phase_id: ID of phase to move.
        new_position: Target position (1-indexed).
    """
    phase = validate_phase_exists(state, phase_id)
    validate_position(state, new_position)

    old_position = phase.number

    # Remove from current position
    state.current_phases.remove(phase)

    # Insert at new position (0-indexed)
    state.current_phases.insert(new_position - 1, phase)

    renumber_phases(state.current_phases)
    record_operation(
        state, OpType.REORDER, [phase_id],
        params={"from": old_position, "to": new_position},
        description=f"Moved {phase_id} from position {old_position} to {new_position}"
    )


def op_skip(state: NegotiationState, phase_id: str) -> None:
    """
    Mark a phase as skipped.

    Args:
        state: Current negotiation state.
        phase_id: ID of phase to skip.
    """
    phase = validate_phase_exists(state, phase_id)

    if phase.id in state.skipped_ids:
        raise NegotiationError(f"Phase {phase_id} is already skipped.")

    state.skipped_ids.add(phase.id)
    record_operation(
        state, OpType.SKIP, [phase_id],
        description=f"Marked {phase_id} as skipped"
    )


def op_unskip(state: NegotiationState, phase_id: str) -> None:
    """
    Remove skip mark from a phase.

    Args:
        state: Current negotiation state.
        phase_id: ID of phase to unskip.
    """
    phase = validate_phase_exists(state, phase_id)

    if phase.id not in state.skipped_ids:
        raise NegotiationError(f"Phase {phase_id} is not skipped.")

    state.skipped_ids.remove(phase.id)
    record_operation(
        state, OpType.UNSKIP, [phase_id],
        description=f"Removed skip mark from {phase_id}"
    )


MODIFIABLE_FIELDS = {'title', 'context', 'goal', 'plan', 'verification', 'acceptance_criteria', 'rollback'}


def op_modify(
    state: NegotiationState,
    phase_id: str,
    field: str,
    value: Any
) -> None:
    """
    Modify a field of a phase.

    Args:
        state: Current negotiation state.
        phase_id: ID of phase to modify.
        field: Field name to modify.
        value: New value for the field.
    """
    phase = validate_phase_exists(state, phase_id)

    if field not in MODIFIABLE_FIELDS:
        raise NegotiationError(
            f"Field '{field}' cannot be modified. "
            f"Modifiable fields: {', '.join(sorted(MODIFIABLE_FIELDS))}"
        )

    old_value = getattr(phase, field)
    setattr(phase, field, value)

    record_operation(
        state, OpType.MODIFY, [phase_id],
        params={"field": field, "old_value": str(old_value)[:50]},
        description=f"Modified {field} of {phase_id}"
    )


def op_reset(state: NegotiationState, scope: str = "all") -> None:
    """
    Reset negotiation state.

    Args:
        state: Current negotiation state.
        scope: "all" to reset everything, or a phase_id to reset just that phase.
    """
    import copy

    if scope == "all":
        state.current_phases = copy.deepcopy(state.original_phases)
        state.skipped_ids.clear()
        state.operations.clear()  # Clear history on full reset
        # Don't record reset operation for full reset - start fresh
    else:
        # Find original phase
        original = None
        for p in state.original_phases:
            if p.id == scope:
                original = p
                break

        if original is None:
            raise NegotiationError(f"Phase {scope} was not in the original audit.")

        # Replace in current phases
        for i, p in enumerate(state.current_phases):
            if p.id == scope or p.split_from == scope or scope in p.merged_from:
                state.current_phases[i] = copy.deepcopy(original)
                break

        # Remove from skipped if present
        state.skipped_ids.discard(scope)

        renumber_phases(state.current_phases)
        record_operation(
            state, OpType.RESET, [scope],
            params={"scope": scope},
            description=f"Reset {scope} to original state"
        )
```

### Plan

1. Add validation functions
2. Implement renumber_phases helper
3. Implement each operation (split, merge, reorder, skip, unskip, modify, reset)
4. Add operation recording

### Verification

```bash
python -c "
from tools.negotiate import NegotiationState, Phase, op_skip, op_unskip
state = NegotiationState([Phase('p1', 1, 'Test')], [Phase('p1', 1, 'Test')])
op_skip(state, 'p1')
print(f'Skipped: {state.skipped_ids}')
op_unskip(state, 'p1')
print(f'After unskip: {state.skipped_ids}')
print('✓ Operations work')
"
```

### Acceptance Criteria

- [ ] NegotiationError exception class defined
- [ ] validate_phase_exists, validate_position, validate_split, validate_merge implemented
- [ ] op_split creates multiple phases from one, tracks split_from
- [ ] op_merge combines phases, tracks merged_from, warns on non-consecutive
- [ ] op_reorder moves phase to new position
- [ ] op_skip/op_unskip toggle skip state
- [ ] op_modify changes phase fields
- [ ] op_reset restores original state and clears history for "all" scope
- [ ] All operations record history via record_operation

### Rollback

```bash
git checkout HEAD -- tools/negotiate.py
```

### Completion

Phase 44 complete when all operations work with proper validation and history tracking.

---

