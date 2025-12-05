## Phase 42: Phase Negotiation Specification

### Context

Phaser generates comprehensive audit documents, but users may need to adjust phases before execution. A phase might be too large, dependencies might require reordering, or certain phases may be irrelevant to the user's needs.

### Goal

Create a complete specification for the Phase Negotiation system defining all operations, data structures, and CLI interface.

### Files

**Create: `specs/negotiate.md`**

```markdown
# Phase Negotiation Specification

Phaser v1.5 — Phase Negotiation System

## 1. Overview

Phase Negotiation allows users to customize audit phases before execution. This enables:

- **Review**: Inspect phases before committing to execution
- **Split**: Break large phases into smaller, manageable pieces
- **Merge**: Combine related small phases
- **Reorder**: Adjust phase sequence for dependencies
- **Skip**: Mark phases to exclude from execution
- **Modify**: Edit phase titles, descriptions, or acceptance criteria

## 2. Motivation

### Problems Addressed

1. **Oversized Phases**: A single phase with 500+ lines of code changes is hard to review
2. **Dependency Issues**: Phase 5 might depend on Phase 8's changes
3. **Irrelevant Work**: Some phases may not apply to the user's fork/variant
4. **Granularity Mismatch**: User prefers smaller/larger phases than generated
5. **Customization**: User wants to modify descriptions or criteria

### Design Goals

- Non-destructive: Original audit preserved, negotiated version separate
- Reversible: User can reset to original at any time
- Incremental: Changes applied one at a time with preview
- Validated: Operations checked for consistency before applying

## 3. Data Model

### NegotiationState

Tracks the current state of phase negotiation:

    @dataclass
    class NegotiationState:
        """Current state of phase negotiation session."""
        original_phases: List[Phase]      # Immutable original
        current_phases: List[Phase]       # Mutable working copy
        operations: List[NegotiationOp]   # History of operations
        skipped_ids: Set[str]             # Phases marked skip
        created_at: str                   # ISO timestamp
        modified_at: str                  # Last modification
        source_file: str                  # Original audit path

        def to_dict(self) -> dict: ...

        @classmethod
        def from_dict(cls, data: dict) -> 'NegotiationState': ...

        @classmethod
        def from_audit_file(cls, path: str) -> 'NegotiationState': ...

### NegotiationOp

Records a single negotiation operation:

    class OpType(str, Enum):
        SPLIT = "split"
        MERGE = "merge"
        REORDER = "reorder"
        SKIP = "skip"
        UNSKIP = "unskip"
        MODIFY = "modify"
        RESET = "reset"

    @dataclass
    class NegotiationOp:
        """A single negotiation operation."""
        op_type: OpType
        timestamp: str
        target_ids: List[str]           # Phase IDs affected
        params: Dict[str, Any]          # Operation-specific params
        description: str                # Human-readable description

        def to_dict(self) -> dict: ...

        @classmethod
        def from_dict(cls, data: dict) -> 'NegotiationOp': ...

### Phase (Extended)

Phase objects gain negotiation-related fields:

    @dataclass
    class Phase:
        id: str                         # Unique identifier (e.g., "phase-42")
        number: int                     # Display number
        title: str
        context: str
        goal: str
        files: List[FileChange]
        plan: List[str]
        verification: List[str]
        acceptance_criteria: List[str]
        rollback: List[str]

        # Negotiation fields
        original_id: Optional[str]      # If split/merged, original phase
        split_from: Optional[str]       # Parent phase if split
        merged_from: List[str]          # Source phases if merged

        @property
        def is_derived(self) -> bool:
            """True if phase was created via split/merge."""
            return self.split_from is not None or len(self.merged_from) > 0

## 4. Operations

### 4.1 Split

Divide one phase into multiple smaller phases.

**Input:**

- `phase_id`: Phase to split
- `split_points`: List of line numbers or file boundaries

**Behavior:**

1. Validate phase exists and has multiple files/sections
2. Create N new phases from split points
3. Distribute files/code to appropriate new phases
4. Update phase numbering
5. Record operation in history

**Example:**

    Phase 10: "Implement Authentication" (8 files, 400 lines)
      → Split at files 4 and 6
    Phase 10a: "Implement Auth Models" (files 1-3)
    Phase 10b: "Implement Auth Routes" (files 4-5)
    Phase 10c: "Implement Auth Tests" (files 6-8)

### 4.2 Merge

Combine multiple phases into one.

**Input:**

- `phase_ids`: List of phases to merge (must be consecutive or user confirms)

**Behavior:**

1. Validate all phases exist
2. Warn if phases are non-consecutive
3. Combine files, plans, criteria from all phases
4. Create merged phase with combined content
5. Remove original phases
6. Record operation in history

**Constraints:**

- Minimum 2 phases required
- Non-consecutive merge requires confirmation

### 4.3 Reorder

Change the sequence of phases.

**Input:**

- `phase_id`: Phase to move
- `new_position`: Target position (1-indexed)

**Behavior:**

1. Validate phase and position exist
2. Remove phase from current position
3. Insert at new position
4. Renumber all phases
5. Record operation in history

**Dependency Warning:**
If moving would place a phase before its dependencies (detected via file references), warn user.

### 4.4 Skip

Mark a phase to be excluded from execution.

**Input:**

- `phase_id`: Phase to skip

**Behavior:**

1. Add phase_id to skipped_ids set
2. Phase remains in list but marked [SKIP]
3. Record operation in history

**Reverse:** `unskip` removes from skipped_ids

### 4.5 Modify

Edit phase content.

**Input:**

- `phase_id`: Phase to modify
- `field`: Field to change (title, context, goal, etc.)
- `value`: New value

**Behavior:**

1. Validate phase and field exist
2. Store original value (for undo)
3. Apply new value
4. Record operation in history

**Modifiable Fields:**

- title, context, goal (strings)
- plan, verification, acceptance_criteria, rollback (lists)

### 4.6 Reset

Restore to original state.

**Input:**

- `scope`: "all" or specific phase_id

**Behavior:**

- "all": Restore original_phases to current_phases, clear operations and skipped_ids
- phase_id: Restore single phase to original (if it existed originally)

## 5. Validation Rules

### Pre-Operation Validation

1. **Phase Exists**: Target phase must exist in current_phases
2. **Valid Position**: Reorder position must be 1 ≤ pos ≤ len(phases)
3. **Split Feasible**: Phase must have ≥2 files or sections to split
4. **Merge Feasible**: At least 2 phases required

### Post-Operation Validation

1. **No Empty Phases**: Every phase must have at least 1 file
2. **No Duplicate IDs**: All phase IDs unique
3. **Numbering Sequential**: Phase numbers 1, 2, 3... with no gaps
4. **Dependencies Satisfied**: Warn if reorder breaks file dependencies

## 6. CLI Interface

### Main Command

    phaser negotiate <audit-file>

Opens interactive negotiation session for the audit file.

### Interactive Commands

Once in negotiation mode:

    negotiate> list                    # Show all phases with status
    negotiate> show <phase>            # Show phase details
    negotiate> split <phase> [--at <n>]  # Split phase
    negotiate> merge <p1> <p2> [<p3>...]  # Merge phases
    negotiate> reorder <phase> <pos>   # Move phase to position
    negotiate> skip <phase>            # Mark phase as skipped
    negotiate> unskip <phase>          # Remove skip mark
    negotiate> modify <phase> <field> <value>  # Edit field
    negotiate> history                 # Show operation history
    negotiate> diff                    # Show changes from original
    negotiate> reset [<phase>|all]     # Reset changes
    negotiate> save [--output <file>]  # Save negotiated audit
    negotiate> exit                    # Exit without saving
    negotiate> help                    # Show commands

### Non-Interactive Mode

    # Preview phases
    phaser negotiate preview <audit-file>

    # Apply operations from file
    phaser negotiate apply <audit-file> --ops <operations.yaml>

    # Quick skip
    phaser negotiate skip <audit-file> --phases 5,8,12

    # Export negotiated version
    phaser negotiate export <audit-file> --output <new-audit.md>

## 7. State Persistence

### Session File

Negotiation state saved to `.phaser/negotiate/<audit-hash>.yaml`:

    source_file: /path/to/audit.md
    source_hash: abc123...
    created_at: 2025-12-05T10:00:00Z
    modified_at: 2025-12-05T10:15:00Z
    skipped_ids:
      - phase-5
      - phase-12
    operations:
      - op_type: split
        timestamp: 2025-12-05T10:05:00Z
        target_ids: [phase-10]
        params:
          split_at: [4, 6]
        description: 'Split phase 10 into 3 parts'
      - op_type: reorder
        timestamp: 2025-12-05T10:10:00Z
        target_ids: [phase-3]
        params:
          new_position: 7
        description: 'Moved phase 3 to position 7'
    current_phases:
      - id: phase-1
        number: 1
        title: '...'
        # ... full phase data

### Resume Session

    phaser negotiate <audit-file>
    # Detects existing session, prompts: "Resume previous session? [Y/n]"

## 8. Output Format

### Negotiated Audit

The `save` command produces a new audit file with:

1. Original metadata preserved
2. Phases renumbered sequentially
3. Skipped phases removed (or marked in comments)
4. Negotiation history in header comment

    <!-- Negotiated from: original-audit.md -->
    <!-- Operations: 3 splits, 1 merge, 2 skips -->
    <!-- Generated: 2025-12-05T10:30:00Z -->

    # Negotiated Audit: Project Name

    ## Phase 1: First Phase (was Phase 2)

    ...

## 9. Error Handling

| Error            | Message                                             | Recovery            |
| ---------------- | --------------------------------------------------- | ------------------- |
| Phase not found  | "Phase '{id}' not found. Use 'list' to see phases." | Show list           |
| Invalid position | "Position {n} out of range (1-{max})."              | Show valid range    |
| Cannot split     | "Phase has only 1 file. Nothing to split."          | Suggest alternative |
| Merge conflict   | "Phases have conflicting file changes."             | Show conflicts      |
| Parse error      | "Failed to parse audit file: {reason}"              | Show line number    |

## 10. Integration Points

### With Replay

Negotiated audits work seamlessly with replay:

    phaser negotiate audit.md --output negotiated.md
    phaser replay negotiated.md

### With Simulate

Simulate a negotiated audit before execution:

    phaser simulate negotiated.md

### With Contracts

Contracts apply to negotiated phases:

    phaser contracts check negotiated.md
```

### Plan

1. Create specs directory entry if needed
2. Write complete specification file
3. Verify markdown renders correctly

### Verification

```bash
test -f specs/negotiate.md && echo "✓ Spec exists"
head -5 specs/negotiate.md  # Confirm header
wc -l specs/negotiate.md    # Should be ~350 lines
```

### Acceptance Criteria

- [ ] specs/negotiate.md created with complete specification
- [ ] All 6 operations defined (split, merge, reorder, skip, modify, reset)
- [ ] Data model documented (NegotiationState, NegotiationOp, Phase extensions)
- [ ] CLI interface fully specified
- [ ] State persistence format defined

### Rollback

```bash
rm specs/negotiate.md
git checkout HEAD -- specs/
```

### Completion

Phase 42 complete when specification covers all negotiation operations with clear data models and CLI interface.

---

