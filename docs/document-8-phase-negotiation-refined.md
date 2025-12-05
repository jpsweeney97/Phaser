# Document 8: Phase Negotiation

**Phaser v1.5.0 — Batch 2, Document 4 of 4**

## Overview

| Property        | Value                                                           |
| --------------- | --------------------------------------------------------------- |
| Document        | 8 of 8                                                          |
| Phases          | 42-47 (6 phases)                                                |
| Feature         | Phase Negotiation                                               |
| New Files       | specs/negotiate.md, tools/negotiate.py, tests/test_negotiate.py |
| Modified Files  | tools/cli.py, CHANGELOG.md                                      |
| Estimated Tests | +35 tests                                                       |

## Feature Summary

Phase Negotiation enables users to review, customize, and adjust audit phases before execution. Users can split large phases, merge small ones, reorder for dependencies, skip irrelevant phases, and modify phase details—all through an interactive CLI workflow.

---

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

## Phase 43: Phase Parsing and State Management

### Context

With the specification complete, we need to implement the core data structures and parsing logic. This includes extracting phases from markdown audit files and managing negotiation state.

### Goal

Implement NegotiationState, NegotiationOp, OpType, and audit file parsing in tools/negotiate.py.

### Files

**Create: `tools/negotiate.py`**

```python
"""
Phase Negotiation System for Phaser.

Enables users to customize audit phases before execution through
split, merge, reorder, skip, and modify operations.
"""

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


def now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class OpType(str, Enum):
    """Types of negotiation operations."""
    SPLIT = "split"
    MERGE = "merge"
    REORDER = "reorder"
    SKIP = "skip"
    UNSKIP = "unskip"
    MODIFY = "modify"
    RESET = "reset"


@dataclass
class FileChange:
    """A file change within a phase."""
    path: str
    action: str  # create, modify, delete
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "action": self.action,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FileChange':
        return cls(
            path=data["path"],
            action=data["action"],
            description=data.get("description", ""),
        )


@dataclass
class Phase:
    """A single phase in an audit document."""
    id: str
    number: int
    title: str
    context: str = ""
    goal: str = ""
    files: List[FileChange] = field(default_factory=list)
    plan: List[str] = field(default_factory=list)
    verification: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    rollback: List[str] = field(default_factory=list)

    # Negotiation tracking
    original_id: Optional[str] = None
    split_from: Optional[str] = None
    merged_from: List[str] = field(default_factory=list)

    @property
    def is_derived(self) -> bool:
        """True if phase was created via split/merge."""
        return self.split_from is not None or len(self.merged_from) > 0

    @property
    def file_count(self) -> int:
        """Number of files in this phase."""
        return len(self.files)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "context": self.context,
            "goal": self.goal,
            "files": [f.to_dict() for f in self.files],
            "plan": self.plan,
            "verification": self.verification,
            "acceptance_criteria": self.acceptance_criteria,
            "rollback": self.rollback,
            "original_id": self.original_id,
            "split_from": self.split_from,
            "merged_from": self.merged_from,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Phase':
        return cls(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            context=data.get("context", ""),
            goal=data.get("goal", ""),
            files=[FileChange.from_dict(f) for f in data.get("files", [])],
            plan=data.get("plan", []),
            verification=data.get("verification", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            rollback=data.get("rollback", []),
            original_id=data.get("original_id"),
            split_from=data.get("split_from"),
            merged_from=data.get("merged_from", []),
        )


@dataclass
class NegotiationOp:
    """A single negotiation operation."""
    op_type: OpType
    timestamp: str
    target_ids: List[str]
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "op_type": self.op_type.value,
            "timestamp": self.timestamp,
            "target_ids": self.target_ids,
            "params": self.params,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NegotiationOp':
        return cls(
            op_type=OpType(data["op_type"]),
            timestamp=data["timestamp"],
            target_ids=data["target_ids"],
            params=data.get("params", {}),
            description=data.get("description", ""),
        )


@dataclass
class NegotiationState:
    """Current state of a phase negotiation session."""
    original_phases: List[Phase]
    current_phases: List[Phase]
    operations: List[NegotiationOp] = field(default_factory=list)
    skipped_ids: Set[str] = field(default_factory=set)
    created_at: str = field(default_factory=now_iso)
    modified_at: str = field(default_factory=now_iso)
    source_file: str = ""
    source_hash: str = ""

    @property
    def phase_count(self) -> int:
        """Number of current phases."""
        return len(self.current_phases)

    @property
    def active_count(self) -> int:
        """Number of non-skipped phases."""
        return len([p for p in self.current_phases if p.id not in self.skipped_ids])

    @property
    def operation_count(self) -> int:
        """Number of operations applied."""
        return len(self.operations)

    @property
    def has_changes(self) -> bool:
        """True if any operations have been applied."""
        return len(self.operations) > 0 or len(self.skipped_ids) > 0

    def get_phase(self, phase_id: str) -> Optional[Phase]:
        """Get phase by ID."""
        for phase in self.current_phases:
            if phase.id == phase_id:
                return phase
        return None

    def get_phase_by_number(self, number: int) -> Optional[Phase]:
        """Get phase by number."""
        for phase in self.current_phases:
            if phase.number == number:
                return phase
        return None

    def to_dict(self) -> dict:
        return {
            "original_phases": [p.to_dict() for p in self.original_phases],
            "current_phases": [p.to_dict() for p in self.current_phases],
            "operations": [op.to_dict() for op in self.operations],
            "skipped_ids": list(self.skipped_ids),
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "source_file": self.source_file,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NegotiationState':
        return cls(
            original_phases=[Phase.from_dict(p) for p in data["original_phases"]],
            current_phases=[Phase.from_dict(p) for p in data["current_phases"]],
            operations=[NegotiationOp.from_dict(op) for op in data.get("operations", [])],
            skipped_ids=set(data.get("skipped_ids", [])),
            created_at=data.get("created_at", now_iso()),
            modified_at=data.get("modified_at", now_iso()),
            source_file=data.get("source_file", ""),
            source_hash=data.get("source_hash", ""),
        )


def compute_file_hash(path: str) -> str:
    """Compute SHA-256 hash of file contents."""
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def parse_phase_header(line: str) -> Optional[Tuple[int, str]]:
    """
    Parse a phase header line.

    Returns (number, title) or None if not a phase header.

    Examples:
        "## Phase 1: Setup Project" -> (1, "Setup Project")
        "### Phase 42: Implement Feature" -> (42, "Implement Feature")
    """
    # Match ## Phase N: Title or ### Phase N: Title
    match = re.match(r'^#{2,3}\s+Phase\s+(\d+):\s*(.+)$', line.strip())
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None


def parse_section(lines: List[str], start_idx: int, section_name: str) -> Tuple[str, int]:
    """
    Parse a section starting with ### Section Name.

    Returns (content, end_index).
    """
    content_lines = []
    i = start_idx

    # Skip the header line
    if i < len(lines) and section_name.lower() in lines[i].lower():
        i += 1

    # Collect content until next section or phase
    while i < len(lines):
        line = lines[i]
        # Stop at next section header or phase header
        if line.startswith('### ') or line.startswith('## Phase'):
            break
        content_lines.append(line)
        i += 1

    return '\n'.join(content_lines).strip(), i


def parse_list_section(lines: List[str], start_idx: int, section_name: str) -> Tuple[List[str], int]:
    """
    Parse a section containing a bulleted list.

    Returns (items, end_index).
    """
    items = []
    i = start_idx

    # Skip the header line
    if i < len(lines) and section_name.lower() in lines[i].lower():
        i += 1

    # Collect list items
    while i < len(lines):
        line = lines[i].strip()
        # Stop at next section header or phase header
        if line.startswith('### ') or line.startswith('## Phase'):
            break
        # Parse list items
        if line.startswith('- ') or line.startswith('* '):
            items.append(line[2:].strip())
        elif line.startswith('[ ] ') or line.startswith('[x] '):
            items.append(line[4:].strip())
        i += 1

    return items, i


def parse_files_section(lines: List[str], start_idx: int) -> Tuple[List[FileChange], int]:
    """
    Parse the Files section of a phase.

    Returns (file_changes, end_index).
    """
    files = []
    i = start_idx

    # Skip header
    if i < len(lines) and 'files' in lines[i].lower():
        i += 1

    current_action = "modify"
    current_path = ""
    current_desc = ""

    while i < len(lines):
        line = lines[i].strip()

        # Stop at next section
        if line.startswith('### ') or line.startswith('## Phase'):
            break

        # Detect action keywords
        if line.lower().startswith('**create:'):
            current_action = "create"
            path_match = re.search(r'\*\*Create:\s*`([^`]+)`\*\*', line, re.IGNORECASE)
            if path_match:
                current_path = path_match.group(1)
        elif line.lower().startswith('**modify:'):
            current_action = "modify"
            path_match = re.search(r'\*\*Modify:\s*`([^`]+)`\*\*', line, re.IGNORECASE)
            if path_match:
                current_path = path_match.group(1)
        elif line.lower().startswith('**delete:'):
            current_action = "delete"
            path_match = re.search(r'\*\*Delete:\s*`([^`]+)`\*\*', line, re.IGNORECASE)
            if path_match:
                current_path = path_match.group(1)
        elif line.startswith('`') and line.endswith('`'):
            # Standalone path
            current_path = line.strip('`')

        # If we have a path, save the file change
        if current_path:
            files.append(FileChange(
                path=current_path,
                action=current_action,
                description=current_desc,
            ))
            current_path = ""
            current_desc = ""

        i += 1

    return files, i


def parse_audit_file(path: str) -> List[Phase]:
    """
    Parse an audit markdown file and extract phases.

    Args:
        path: Path to the audit markdown file.

    Returns:
        List of Phase objects.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file cannot be parsed.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audit file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    phases = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for phase header
        header = parse_phase_header(line)
        if header:
            number, title = header
            phase_id = f"phase-{number}"

            # Initialize phase data
            context = ""
            goal = ""
            files: List[FileChange] = []
            plan: List[str] = []
            verification: List[str] = []
            acceptance_criteria: List[str] = []
            rollback: List[str] = []

            i += 1

            # Parse phase sections
            while i < len(lines):
                section_line = lines[i].strip().lower()

                # Check for next phase
                if parse_phase_header(lines[i]):
                    break

                # Parse known sections
                if '### context' in section_line:
                    context, i = parse_section(lines, i, 'context')
                elif '### goal' in section_line:
                    goal, i = parse_section(lines, i, 'goal')
                elif '### files' in section_line:
                    files, i = parse_files_section(lines, i)
                elif '### plan' in section_line:
                    plan, i = parse_list_section(lines, i, 'plan')
                elif '### verification' in section_line:
                    verification, i = parse_list_section(lines, i, 'verification')
                elif '### acceptance' in section_line:
                    acceptance_criteria, i = parse_list_section(lines, i, 'acceptance')
                elif '### rollback' in section_line:
                    rollback, i = parse_list_section(lines, i, 'rollback')
                else:
                    i += 1

            phases.append(Phase(
                id=phase_id,
                number=number,
                title=title,
                context=context,
                goal=goal,
                files=files,
                plan=plan,
                verification=verification,
                acceptance_criteria=acceptance_criteria,
                rollback=rollback,
            ))
        else:
            i += 1

    return phases


def load_negotiation_state(path: str) -> NegotiationState:
    """
    Load negotiation state from YAML file.

    Args:
        path: Path to the state YAML file.

    Returns:
        NegotiationState object.
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return NegotiationState.from_dict(data)


def save_negotiation_state(state: NegotiationState, path: str) -> None:
    """
    Save negotiation state to YAML file.

    Args:
        state: NegotiationState to save.
        path: Destination path.
    """
    # Ensure directory exists (handle empty dirname)
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # Update modification time
    state.modified_at = now_iso()

    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(state.to_dict(), f, default_flow_style=False, sort_keys=False)


def get_state_path(audit_path: str) -> str:
    """
    Get the state file path for an audit file.

    State files are stored in .phaser/negotiate/<hash>.yaml
    """
    audit_hash = compute_file_hash(audit_path)
    return os.path.join('.phaser', 'negotiate', f'{audit_hash}.yaml')


def init_negotiation(audit_path: str) -> NegotiationState:
    """
    Initialize a new negotiation session from an audit file.

    Args:
        audit_path: Path to the audit markdown file.

    Returns:
        New NegotiationState object.
    """
    phases = parse_audit_file(audit_path)

    if not phases:
        raise ValueError(f"No phases found in {audit_path}")

    # Deep copy phases for current
    import copy
    current = copy.deepcopy(phases)

    return NegotiationState(
        original_phases=phases,
        current_phases=current,
        source_file=os.path.abspath(audit_path),
        source_hash=compute_file_hash(audit_path),
    )


def resume_or_init(audit_path: str) -> Tuple[NegotiationState, bool]:
    """
    Resume existing session or initialize new one.

    Args:
        audit_path: Path to the audit file.

    Returns:
        (NegotiationState, was_resumed) tuple.
    """
    state_path = get_state_path(audit_path)

    if os.path.exists(state_path):
        state = load_negotiation_state(state_path)
        return state, True

    state = init_negotiation(audit_path)
    return state, False
```

### Plan

1. Create tools/negotiate.py with all data structures
2. Implement audit file parsing
3. Implement state persistence
4. Add helper functions for state management

### Verification

```bash
python -c "from tools.negotiate import OpType, Phase, NegotiationState; print('✓ Imports work')"
python -c "from tools.negotiate import parse_phase_header; print(parse_phase_header('## Phase 1: Test'))"
python -c "from tools.negotiate import NegotiationState; s = NegotiationState([], []); print(s.to_dict())"
```

### Acceptance Criteria

- [ ] OpType enum with 7 operation types
- [ ] FileChange dataclass with to_dict/from_dict
- [ ] Phase dataclass with is_derived property
- [ ] NegotiationOp dataclass with serialization
- [ ] NegotiationState with phase_count, active_count, has_changes properties
- [ ] parse_audit_file extracts phases from markdown
- [ ] State persistence via load/save functions
- [ ] resume_or_init handles both new and existing sessions

### Rollback

```bash
rm tools/negotiate.py
```

### Completion

Phase 43 complete when all data structures are implemented with serialization and parsing functions work correctly.

---

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

## Phase 47: Tests and Documentation

### Context

All functionality is implemented. We need comprehensive tests and updated documentation.

### Goal

Create test suite for negotiate module and update CHANGELOG.md.

### Files

**Create: `tests/test_negotiate.py`**

```python
"""Tests for Phase Negotiation system."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from tools.negotiate import (
    OpType,
    FileChange,
    Phase,
    NegotiationOp,
    NegotiationState,
    NegotiationError,
    now_iso,
    parse_phase_header,
    parse_audit_file,
    compute_file_hash,
    init_negotiation,
    save_negotiation_state,
    load_negotiation_state,
    validate_phase_exists,
    validate_position,
    validate_split,
    validate_merge,
    check_consecutive,
    op_split,
    op_merge,
    op_reorder,
    op_skip,
    op_unskip,
    op_modify,
    op_reset,
    format_phase_list,
    format_phase_detail,
    format_diff,
    generate_negotiated_audit,
    MODIFIABLE_FIELDS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_audit_content():
    """Sample audit markdown content."""
    return """# Sample Audit

## Phase 1: Setup Project

### Context
Initial project setup.

### Goal
Create project structure.

### Files

**Create: `src/main.py`**

**Create: `requirements.txt`**

### Plan
- Create directories
- Add files

### Acceptance Criteria
- [ ] Project structure exists
- [ ] Files created

---

## Phase 2: Add Features

### Context
Adding core features.

### Goal
Implement main functionality.

### Files

**Modify: `src/main.py`**

**Create: `src/utils.py`**

**Create: `tests/test_main.py`**

### Plan
- Implement features
- Add tests

### Acceptance Criteria
- [ ] Features work
- [ ] Tests pass

---

## Phase 3: Documentation

### Context
Final documentation.

### Goal
Write docs.

### Files

**Create: `README.md`**

### Plan
- Write README

### Acceptance Criteria
- [ ] README complete
"""


@pytest.fixture
def sample_audit_file(sample_audit_content, tmp_path):
    """Create a temporary audit file."""
    audit_path = tmp_path / "audit.md"
    audit_path.write_text(sample_audit_content)
    return str(audit_path)


@pytest.fixture
def sample_state(sample_audit_file):
    """Create a sample negotiation state."""
    return init_negotiation(sample_audit_file)


# ============================================================================
# Test OpType Enum
# ============================================================================

class TestOpType:
    def test_values(self):
        assert OpType.SPLIT.value == "split"
        assert OpType.MERGE.value == "merge"
        assert OpType.REORDER.value == "reorder"
        assert OpType.SKIP.value == "skip"
        assert OpType.UNSKIP.value == "unskip"
        assert OpType.MODIFY.value == "modify"
        assert OpType.RESET.value == "reset"

    def test_from_string(self):
        assert OpType("split") == OpType.SPLIT
        assert OpType("merge") == OpType.MERGE


# ============================================================================
# Test FileChange
# ============================================================================

class TestFileChange:
    def test_to_dict(self):
        fc = FileChange("src/main.py", "create", "Main file")
        d = fc.to_dict()
        assert d["path"] == "src/main.py"
        assert d["action"] == "create"
        assert d["description"] == "Main file"

    def test_from_dict(self):
        d = {"path": "test.py", "action": "modify", "description": ""}
        fc = FileChange.from_dict(d)
        assert fc.path == "test.py"
        assert fc.action == "modify"


# ============================================================================
# Test Phase
# ============================================================================

class TestPhase:
    def test_is_derived_false_by_default(self):
        p = Phase("p1", 1, "Test")
        assert p.is_derived is False

    def test_is_derived_true_if_split(self):
        p = Phase("p1a", 1, "Test", split_from="p1")
        assert p.is_derived is True

    def test_is_derived_true_if_merged(self):
        p = Phase("p1", 1, "Test", merged_from=["p2", "p3"])
        assert p.is_derived is True

    def test_file_count(self):
        p = Phase("p1", 1, "Test", files=[
            FileChange("a.py", "create"),
            FileChange("b.py", "modify"),
        ])
        assert p.file_count == 2

    def test_to_dict_from_dict_roundtrip(self):
        p = Phase(
            id="p1",
            number=1,
            title="Test Phase",
            context="Context here",
            goal="Goal here",
            files=[FileChange("test.py", "create")],
            plan=["Step 1", "Step 2"],
            acceptance_criteria=["Criterion 1"],
        )
        d = p.to_dict()
        p2 = Phase.from_dict(d)
        assert p2.id == p.id
        assert p2.title == p.title
        assert len(p2.files) == 1
        assert p2.plan == p.plan


# ============================================================================
# Test NegotiationOp
# ============================================================================

class TestNegotiationOp:
    def test_to_dict(self):
        op = NegotiationOp(
            op_type=OpType.SKIP,
            timestamp="2025-01-01T00:00:00Z",
            target_ids=["phase-1"],
            description="Skipped phase 1"
        )
        d = op.to_dict()
        assert d["op_type"] == "skip"
        assert d["target_ids"] == ["phase-1"]

    def test_from_dict(self):
        d = {
            "op_type": "merge",
            "timestamp": "2025-01-01T00:00:00Z",
            "target_ids": ["phase-1", "phase-2"],
            "params": {"merged_id": "phase-1"},
            "description": "Merged"
        }
        op = NegotiationOp.from_dict(d)
        assert op.op_type == OpType.MERGE
        assert len(op.target_ids) == 2


# ============================================================================
# Test NegotiationState
# ============================================================================

class TestNegotiationState:
    def test_phase_count(self, sample_state):
        assert sample_state.phase_count == 3

    def test_active_count(self, sample_state):
        assert sample_state.active_count == 3
        sample_state.skipped_ids.add("phase-1")
        assert sample_state.active_count == 2

    def test_has_changes_false_initially(self, sample_state):
        assert sample_state.has_changes is False

    def test_has_changes_true_after_skip(self, sample_state):
        sample_state.skipped_ids.add("phase-1")
        assert sample_state.has_changes is True

    def test_get_phase(self, sample_state):
        p = sample_state.get_phase("phase-2")
        assert p is not None
        assert p.title == "Add Features"

    def test_get_phase_by_number(self, sample_state):
        p = sample_state.get_phase_by_number(3)
        assert p is not None
        assert p.title == "Documentation"


# ============================================================================
# Test Parsing
# ============================================================================

class TestParsing:
    def test_parse_phase_header_valid(self):
        result = parse_phase_header("## Phase 42: Implement Feature")
        assert result == (42, "Implement Feature")

    def test_parse_phase_header_triple_hash(self):
        result = parse_phase_header("### Phase 1: Setup")
        assert result == (1, "Setup")

    def test_parse_phase_header_invalid(self):
        assert parse_phase_header("# Not a phase") is None
        assert parse_phase_header("Regular text") is None

    def test_parse_audit_file(self, sample_audit_file):
        phases = parse_audit_file(sample_audit_file)
        assert len(phases) == 3
        assert phases[0].title == "Setup Project"
        assert phases[1].title == "Add Features"
        assert phases[2].title == "Documentation"

    def test_parse_audit_file_extracts_files(self, sample_audit_file):
        phases = parse_audit_file(sample_audit_file)
        # Phase 1 has 2 files, Phase 2 has 3 files, Phase 3 has 1 file
        assert len(phases[0].files) == 2
        assert len(phases[1].files) == 3
        assert len(phases[2].files) == 1
        assert any(f.path == "src/main.py" for f in phases[0].files)

    def test_parse_audit_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_audit_file("/nonexistent/path.md")


# ============================================================================
# Test Validation
# ============================================================================

class TestValidation:
    def test_validate_phase_exists_found(self, sample_state):
        p = validate_phase_exists(sample_state, "phase-1")
        assert p.number == 1

    def test_validate_phase_exists_not_found(self, sample_state):
        with pytest.raises(NegotiationError):
            validate_phase_exists(sample_state, "phase-99")

    def test_validate_position_valid(self, sample_state):
        validate_position(sample_state, 1)
        validate_position(sample_state, 3)

    def test_validate_position_invalid(self, sample_state):
        with pytest.raises(NegotiationError):
            validate_position(sample_state, 0)
        with pytest.raises(NegotiationError):
            validate_position(sample_state, 10)

    def test_validate_split_valid(self, sample_state):
        phase = sample_state.get_phase("phase-2")
        validate_split(phase)  # Has 3 files

    def test_validate_split_invalid(self, sample_state):
        phase = sample_state.get_phase("phase-3")  # Has 1 file
        with pytest.raises(NegotiationError):
            validate_split(phase)

    def test_validate_merge_valid(self, sample_state):
        phases = validate_merge(sample_state, ["phase-1", "phase-2"])
        assert len(phases) == 2

    def test_validate_merge_too_few(self, sample_state):
        with pytest.raises(NegotiationError):
            validate_merge(sample_state, ["phase-1"])

    def test_check_consecutive_true(self, sample_state):
        phases = [sample_state.get_phase("phase-1"), sample_state.get_phase("phase-2")]
        assert check_consecutive(phases) is True

    def test_check_consecutive_false(self, sample_state):
        phases = [sample_state.get_phase("phase-1"), sample_state.get_phase("phase-3")]
        assert check_consecutive(phases) is False


# ============================================================================
# Test Operations
# ============================================================================

class TestOperations:
    def test_op_skip(self, sample_state):
        op_skip(sample_state, "phase-1")
        assert "phase-1" in sample_state.skipped_ids
        assert sample_state.operation_count == 1

    def test_op_skip_already_skipped(self, sample_state):
        op_skip(sample_state, "phase-1")
        with pytest.raises(NegotiationError):
            op_skip(sample_state, "phase-1")

    def test_op_unskip(self, sample_state):
        op_skip(sample_state, "phase-1")
        op_unskip(sample_state, "phase-1")
        assert "phase-1" not in sample_state.skipped_ids

    def test_op_unskip_not_skipped(self, sample_state):
        with pytest.raises(NegotiationError):
            op_unskip(sample_state, "phase-1")

    def test_op_reorder(self, sample_state):
        op_reorder(sample_state, "phase-1", 3)
        # Phase 1 should now be at position 3
        assert sample_state.current_phases[2].title == "Setup Project"

    def test_op_modify_title(self, sample_state):
        op_modify(sample_state, "phase-1", "title", "New Title")
        p = sample_state.get_phase("phase-1")
        assert p.title == "New Title"

    def test_op_modify_invalid_field(self, sample_state):
        with pytest.raises(NegotiationError):
            op_modify(sample_state, "phase-1", "invalid_field", "value")

    def test_op_merge(self, sample_state):
        merged = op_merge(sample_state, ["phase-1", "phase-2"], force=True)
        assert sample_state.phase_count == 2  # 3 - 2 + 1
        assert len(merged.merged_from) == 2

    def test_op_split(self, sample_state):
        # Phase 2 has 3 files
        new_phases = op_split(sample_state, "phase-2", split_at=[1, 2])
        assert len(new_phases) == 3
        assert sample_state.phase_count == 5  # 3 - 1 + 3
        # Verify split tracking
        assert all(p.split_from == "phase-2" for p in new_phases)

    def test_op_split_preserves_derived_ids(self, sample_state):
        """Verify that split phase IDs are not overwritten by renumbering."""
        new_phases = op_split(sample_state, "phase-2", split_at=[1, 2])
        # IDs should have suffixes like phase-2a, phase-2b, phase-2c
        ids = [p.id for p in new_phases]
        assert "phase-2a" in ids
        assert "phase-2b" in ids
        assert "phase-2c" in ids

    def test_op_reset_all(self, sample_state):
        op_skip(sample_state, "phase-1")
        op_modify(sample_state, "phase-2", "title", "Changed")
        assert sample_state.operation_count == 2
        op_reset(sample_state, "all")
        assert len(sample_state.skipped_ids) == 0
        assert sample_state.operation_count == 0  # History cleared
        p2 = sample_state.get_phase("phase-2")
        assert p2.title == "Add Features"

    def test_op_reset_single_phase(self, sample_state):
        op_modify(sample_state, "phase-1", "title", "Changed")
        op_reset(sample_state, "phase-1")
        p1 = sample_state.get_phase("phase-1")
        assert p1.title == "Setup Project"
        # Single phase reset should record operation
        assert sample_state.operation_count == 2


# ============================================================================
# Test Formatting
# ============================================================================

class TestFormatting:
    def test_format_phase_list(self, sample_state):
        output = format_phase_list(sample_state)
        assert "3 active" in output
        assert "Setup Project" in output
        assert "Add Features" in output

    def test_format_phase_list_with_skip(self, sample_state):
        sample_state.skipped_ids.add("phase-1")
        output = format_phase_list(sample_state)
        assert "[SKIP]" in output

    def test_format_phase_detail(self, sample_state):
        phase = sample_state.get_phase("phase-1")
        output = format_phase_detail(phase, False)
        assert "Phase 1" in output
        assert "Setup Project" in output

    def test_format_diff(self, sample_state):
        sample_state.skipped_ids.add("phase-1")
        output = format_diff(sample_state)
        assert "Skipped" in output
        assert "phase-1" in output

    def test_generate_negotiated_audit(self, sample_state):
        output = generate_negotiated_audit(sample_state)
        assert "# Negotiated Audit" in output
        assert "## Phase 1" in output
        assert "## Phase 2" in output

    def test_generate_negotiated_audit_excludes_skipped(self, sample_state):
        op_skip(sample_state, "phase-1")
        output = generate_negotiated_audit(sample_state, include_skipped=False)
        assert "Setup Project" not in output  # Phase 1 excluded


# ============================================================================
# Test Persistence
# ============================================================================

class TestPersistence:
    def test_save_and_load_state(self, sample_state, tmp_path):
        # Make some changes
        op_skip(sample_state, "phase-1")

        # Save
        state_path = str(tmp_path / "state.yaml")
        save_negotiation_state(sample_state, state_path)

        # Load
        loaded = load_negotiation_state(state_path)
        assert loaded.phase_count == sample_state.phase_count
        assert "phase-1" in loaded.skipped_ids
        assert loaded.operation_count == 1

    def test_save_to_filename_only(self, sample_state, tmp_path):
        """Test saving when path has no directory component."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            save_negotiation_state(sample_state, "state.yaml")
            assert os.path.exists("state.yaml")
        finally:
            os.chdir(original_cwd)

    def test_compute_file_hash(self, sample_audit_file):
        hash1 = compute_file_hash(sample_audit_file)
        hash2 = compute_file_hash(sample_audit_file)
        assert hash1 == hash2
        assert len(hash1) == 16


# ============================================================================
# Test CLI (basic)
# ============================================================================

class TestCLI:
    def test_cli_help(self):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'negotiate' in result.output.lower() or 'phase' in result.output.lower()

    def test_preview_command(self, sample_audit_file):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['preview', sample_audit_file])
        assert result.exit_code == 0
        assert "3 phases" in result.output

    def test_status_no_session(self, sample_audit_file):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['status', sample_audit_file])
        assert result.exit_code == 0
        assert "No negotiation session" in result.output

    def test_skip_command(self, sample_audit_file, tmp_path):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        output_path = str(tmp_path / "output.md")
        result = runner.invoke(cli, ['skip', sample_audit_file, '--phases', '1,3', '--output', output_path])
        assert result.exit_code == 0
        assert "Skipped phase 1" in result.output
        assert "Skipped phase 3" in result.output
        assert os.path.exists(output_path)
```

**Modify: `CHANGELOG.md`**

Add to the existing [1.5.0] section:

```markdown
## [1.5.0] - 2025-12-05

### Added

- **Reverse Audit** (`phaser reverse`)

  - `phaser reverse generate <commit-range>` — Generate audit document from git diff
  - `phaser reverse preview <commit-range>` — Preview inferred phases
  - `phaser reverse commits <commit-range>` — List commits with details
  - `phaser reverse diff <commit-range>` — Show full diff
  - Multiple grouping strategies: commits, directories, filetypes, semantic
  - Output formats: markdown, yaml, json
  - Automatic phase title and category inference
  - Support for conventional commit parsing

- **Phase Negotiation** (`phaser negotiate`)
  - `phaser negotiate <audit-file>` — Interactive phase customization
  - `phaser negotiate preview <audit-file>` — Preview phases in audit
  - `phaser negotiate skip <audit-file> --phases N,M` — Quick skip phases
  - `phaser negotiate apply <audit-file> --ops <file.yaml>` — Batch apply operations
  - `phaser negotiate export <audit-file>` — Export negotiated audit
  - `phaser negotiate status <audit-file>` — Show session status
  - Operations: split, merge, reorder, skip, modify, reset
  - Session persistence with resume capability
  - Non-consecutive merge warning
  - Tracks operation history for review
  - Produces clean negotiated audit documents
```

### Plan

1. Create comprehensive test file covering all modules
2. Update CHANGELOG.md with Phase Negotiation feature
3. Verify test count meets target

### Verification

```bash
python -m pytest tests/test_negotiate.py -v
python -m pytest tests/ -q | tail -5  # Check total count
grep -A 20 "Phase Negotiation" CHANGELOG.md
```

### Acceptance Criteria

- [ ] tests/test_negotiate.py created with ~35 tests
- [ ] All tests pass
- [ ] CHANGELOG.md updated with Phase Negotiation feature
- [ ] Test coverage includes: OpType, FileChange, Phase, NegotiationOp, NegotiationState
- [ ] Test coverage includes: parsing, validation, all operations
- [ ] Test coverage includes: formatting, persistence, CLI commands
- [ ] Total test count 345+ (310 + 35)

### Rollback

```bash
rm tests/test_negotiate.py
git checkout HEAD -- CHANGELOG.md
```

### Completion

Phase 47 complete when all tests pass and documentation is updated.

---

## Document Summary

| Phase | Title           | Files                                 | Status |
| ----- | --------------- | ------------------------------------- | ------ |
| 42    | Specification   | specs/negotiate.md                    | ⏳     |
| 43    | Parsing & State | tools/negotiate.py (create)           | ⏳     |
| 44    | Operations      | tools/negotiate.py (extend)           | ⏳     |
| 45    | CLI Commands    | tools/negotiate.py (extend)           | ⏳     |
| 46    | CLI Integration | tools/cli.py                          | ⏳     |
| 47    | Tests & Docs    | tests/test_negotiate.py, CHANGELOG.md | ⏳     |

## Expected Outcomes

After completing all phases:

1. **New Files:**

   - `specs/negotiate.md` (~350 lines)
   - `tools/negotiate.py` (~900 lines)
   - `tests/test_negotiate.py` (~450 lines)

2. **Modified Files:**

   - `tools/cli.py` (add negotiate import and registration)
   - `CHANGELOG.md` (add Phase Negotiation section)

3. **New Commands:**

   - `phaser negotiate <audit-file>` — Interactive mode
   - `phaser negotiate preview <audit-file>` — Preview phases
   - `phaser negotiate skip <audit-file> --phases N,M` — Quick skip
   - `phaser negotiate apply <audit-file> --ops <file.yaml>` — Batch apply
   - `phaser negotiate export <audit-file> --output <file>` — Export
   - `phaser negotiate status <audit-file>` — Session status

4. **Test Count:** 345+ total (existing 310 + new 35)

5. **Version:** Remains 1.5.0 (version already bumped in Document 7)

---

## Batch 2 Completion Checklist

| Document | Feature       | Phases    | Status                     |
| -------- | ------------- | --------- | -------------------------- |
| 5        | Replay        | 24-29     | ✅ Complete                |
| 6        | Insights      | 30-35     | ✅ Complete                |
| 7        | Reverse       | 36-41     | ✅ Complete                |
| **8**    | **Negotiate** | **42-47** | **⏳ Ready for Execution** |

After Claude Code executes Document 8, Batch 2 will be complete and Phaser v1.5.0 will have all planned features:

- Branch-per-Phase Mode
- Contract Enforcement
- Manifest Diffing
- Dry-Run Simulation
- Reverse Audit
- Phase Negotiation
