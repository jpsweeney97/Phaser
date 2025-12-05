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
