# Simulation Specification

> Phaser v1.2 — Safe dry-run execution for audits

---

## Purpose

Simulation allows users to preview audit changes without committing them:

- **Preview changes** — See what an audit will do before it does it
- **Catch failures early** — If phase 7 fails, don't run phases 1-6 for real
- **Build confidence** — Trust automated changes by verifying them first
- **Try before you buy** — Run the entire audit in a sandbox, then decide

---

## Sandbox Strategies

| Strategy     | Mechanism                        | Pros                    | Cons                           |
| ------------ | -------------------------------- | ----------------------- | ------------------------------ |
| Git Stash    | `git stash` before, restore after | Simple, native          | Doesn't handle new files well  |
| Git Worktree | Clone to temp worktree           | Full isolation          | Disk space, slower             |
| Copy         | rsync to temp dir                | Works without git       | Slow for large repos           |
| Git Branch   | Create temp branch, reset after  | Native, fast            | Leaves branch artifacts        |

### Recommended: Git Stash + Tracking

The chosen strategy combines git stash with explicit file tracking:

1. **Stash uncommitted changes** — Preserve user's work-in-progress
2. **Track all new files created** — Record paths for deletion on rollback
3. **Track all files modified** — Record paths for git checkout on rollback
4. **Track all files deleted** — Record paths for git checkout on rollback
5. **On rollback** — Delete created files, checkout modified/deleted files, pop stash

This approach is:
- Fast (no copying)
- Safe (stash preserves uncommitted work)
- Complete (tracks all change types)
- Reversible (git checkout restores any tracked file)

---

## Data Schemas

### SimulationContext

Tracks the state of an active simulation session:

```python
@dataclass
class SimulationContext:
    audit_id: str              # ID of the audit being simulated
    root: Path                 # Project root directory
    original_branch: str       # Git branch when simulation started
    stash_ref: str | None      # Stash reference (if uncommitted changes existed)
    created_files: list[Path]  # Files created during simulation
    modified_files: list[Path] # Files modified during simulation
    deleted_files: list[Path]  # Files deleted during simulation
    started_at: str            # ISO timestamp when simulation began
    active: bool = True        # Whether simulation is still active

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "audit_id": self.audit_id,
            "root": str(self.root),
            "original_branch": self.original_branch,
            "stash_ref": self.stash_ref,
            "created_files": [str(p) for p in self.created_files],
            "modified_files": [str(p) for p in self.modified_files],
            "deleted_files": [str(p) for p in self.deleted_files],
            "started_at": self.started_at,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SimulationContext":
        """Deserialize from persistence."""
        return cls(
            audit_id=d["audit_id"],
            root=Path(d["root"]),
            original_branch=d["original_branch"],
            stash_ref=d.get("stash_ref"),
            created_files=[Path(p) for p in d.get("created_files", [])],
            modified_files=[Path(p) for p in d.get("modified_files", [])],
            deleted_files=[Path(p) for p in d.get("deleted_files", [])],
            started_at=d["started_at"],
            active=d.get("active", True),
        )
```

### SimulationResult

Result of a completed simulation:

```python
@dataclass
class SimulationResult:
    success: bool              # True if all phases passed
    phases_run: int            # Total phases executed
    phases_passed: int         # Phases that succeeded
    phases_failed: int         # Phases that failed
    first_failure: int | None  # Phase number of first failure (if any)
    failure_reason: str | None # Error message from first failure
    duration: float            # Total simulation time in seconds
    diff_summary: str          # Human-readable summary of changes
    files_created: int         # Count of files that would be created
    files_modified: int        # Count of files that would be modified
    files_deleted: int         # Count of files that would be deleted

    def to_dict(self) -> dict:
        """Serialize for reporting."""
        return {
            "success": self.success,
            "phases_run": self.phases_run,
            "phases_passed": self.phases_passed,
            "phases_failed": self.phases_failed,
            "first_failure": self.first_failure,
            "failure_reason": self.failure_reason,
            "duration": self.duration,
            "diff_summary": self.diff_summary,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "files_deleted": self.files_deleted,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"Simulation {status}",
            f"Phases: {self.phases_passed}/{self.phases_run} passed",
        ]
        if self.first_failure:
            lines.append(f"First failure: Phase {self.first_failure}")
            if self.failure_reason:
                lines.append(f"Reason: {self.failure_reason}")
        lines.append(f"Would create {self.files_created} files")
        lines.append(f"Would modify {self.files_modified} files")
        lines.append(f"Would delete {self.files_deleted} files")
        lines.append(f"Duration: {self.duration:.1f}s")
        return "\n".join(lines)
```

---

## Operations

### begin_simulation

Enter simulation mode:

```python
def begin_simulation(
    root: Path,
    audit_id: str,
    storage: PhaserStorage | None = None,
) -> SimulationContext:
    """
    Begin a simulation session.

    Steps:
    1. Verify root is a git repository
    2. Check no active simulation exists
    3. Record current branch name
    4. If uncommitted changes exist, create stash
    5. Initialize empty tracking lists
    6. Save context to storage (for recovery)
    7. Return context

    Raises:
        SimulationError: If not a git repo or simulation already active
    """
```

### track_file_change

Record a file change during simulation:

```python
def track_file_change(
    ctx: SimulationContext,
    path: Path,
    change_type: str,  # "created", "modified", "deleted"
) -> None:
    """
    Track a file change during simulation.

    Steps:
    1. Resolve path relative to root
    2. Add to appropriate list based on change_type
    3. Avoid duplicates

    Note: Call this BEFORE making the change for "modified" and "deleted",
    and AFTER making the change for "created".
    """
```

### rollback_simulation

Undo all simulation changes:

```python
def rollback_simulation(ctx: SimulationContext) -> bool:
    """
    Rollback all changes made during simulation.

    Steps:
    1. Delete all created files
    2. Restore all modified files via git checkout
    3. Restore all deleted files via git checkout
    4. Pop stash if one was created
    5. Mark context as inactive
    6. Remove context from storage

    Returns:
        True if rollback succeeded, False otherwise

    Note: Rollback is best-effort. Files outside git tracking
    cannot be restored from git checkout.
    """
```

### commit_simulation

Keep simulation changes (make them real):

```python
def commit_simulation(ctx: SimulationContext) -> bool:
    """
    Keep simulation changes as real changes.

    Steps:
    1. Drop stash (don't restore it)
    2. Mark context as inactive
    3. Remove context from storage

    Returns:
        True if commit succeeded

    Note: After this, changes are permanent. The original
    uncommitted changes (if any) are lost.
    """
```

### get_active_simulation

Check for existing simulation:

```python
def get_active_simulation(
    storage: PhaserStorage,
) -> SimulationContext | None:
    """
    Get active simulation context if one exists.

    Returns:
        SimulationContext if active simulation, None otherwise
    """
```

### simulate_audit

High-level simulation function:

```python
def simulate_audit(
    root: Path,
    audit_id: str,
    phases: list[int] | None = None,
    storage: PhaserStorage | None = None,
    emitter: EventEmitter | None = None,
) -> SimulationResult:
    """
    Simulate an audit (or specific phases).

    Steps:
    1. Begin simulation
    2. For each phase (or specified phases):
       a. Execute phase
       b. Track all file changes
       c. If phase fails and fail_fast, stop
    3. Capture diff summary
    4. Rollback all changes
    5. Return SimulationResult

    Note: Always rolls back, even on success. Use commit_simulation()
    separately if you want to keep changes.
    """
```

---

## Context Manager

For convenient auto-rollback:

```python
@contextmanager
def simulation_context(
    root: Path,
    audit_id: str,
    auto_rollback: bool = True,
) -> Generator[SimulationContext, None, None]:
    """
    Context manager for simulations.

    Usage:
        with simulation_context(root, audit_id) as ctx:
            # Make changes
            track_file_change(ctx, path, "created")
            # ...
        # Auto-rollback on exit

    Args:
        root: Project root directory
        audit_id: Audit identifier
        auto_rollback: If True, rollback on exit. If False, keep changes.
    """
    ctx = begin_simulation(root, audit_id)
    try:
        yield ctx
    finally:
        if auto_rollback:
            rollback_simulation(ctx)
        else:
            commit_simulation(ctx)
```

---

## CLI Interface

```bash
# Simulate entire audit
phaser simulate
python -m tools.simulate run

# Simulate specific phases
phaser simulate --phases 1-5
phaser simulate --phase 3
python -m tools.simulate run --phases 1-5

# Simulate and keep changes if all phases pass
phaser simulate --commit-on-success
python -m tools.simulate run --commit-on-success

# Show active simulation status
phaser simulate status
python -m tools.simulate status

# Manually rollback active simulation
phaser simulate rollback
python -m tools.simulate rollback

# Manually commit active simulation (keep changes)
phaser simulate commit
python -m tools.simulate commit
```

### CLI Commands

| Command   | Description                              |
| --------- | ---------------------------------------- |
| `run`     | Simulate audit execution                 |
| `status`  | Show active simulation status            |
| `rollback`| Rollback active simulation               |
| `commit`  | Commit active simulation (keep changes)  |

### CLI Options for `run`

| Option              | Description                              |
| ------------------- | ---------------------------------------- |
| `--root PATH`       | Project root (default: current dir)      |
| `--phases RANGE`    | Phase range, e.g., "1-5" or "3"          |
| `--commit-on-success` | Keep changes if all phases pass        |
| `--verbose, -v`     | Show detailed output                     |

---

## Integration with Audit Workflow

### New Commands

Recognized by CONTEXT.md automation:

| User Says          | Action                                |
| ------------------ | ------------------------------------- |
| `simulate`         | Run all remaining phases in sandbox   |
| `dry-run`          | Same as simulate                      |
| `preview`          | Same as simulate                      |
| `simulate phase N` | Simulate specific phase only          |

### Workflow

1. User says "simulate"
2. System enters simulation mode (stash, track)
3. System executes all remaining phases
4. System captures what would change
5. System rolls back all changes
6. System reports:
   - "Simulation complete"
   - "Phases: N passed, M failed"
   - "Would create X files, modify Y files, delete Z files"
   - "First failure: Phase P" (if any)
   - "To apply these changes for real, say 'next'"

---

## Edge Cases

### Uncommitted Changes Before Simulation

**Scenario:** User has uncommitted changes when starting simulation.

**Handling:**
1. Stash all uncommitted changes with descriptive message
2. Record stash reference in context
3. On rollback, pop stash to restore user's work
4. On commit, drop stash (user chose to keep simulation changes)

### Simulation Interrupted (Ctrl+C)

**Scenario:** User interrupts simulation mid-execution.

**Handling:**
1. Context is persisted to storage on begin
2. On next run, detect active simulation
3. Offer options: "resume", "rollback", "abandon"
4. Rollback restores to pre-simulation state

### Phase Modifies File Outside Project Root

**Scenario:** Phase tries to modify `/etc/hosts` or similar.

**Handling:**
1. Only track files within project root
2. Files outside root are not tracked
3. Rollback cannot restore files outside root
4. Warn user if phase touches external files

### Nested Git Repositories

**Scenario:** Project contains submodules or nested repos.

**Handling:**
1. Only operate on top-level repository
2. Changes in submodules are not tracked by parent stash
3. Document this limitation clearly

### File Permissions

**Scenario:** Simulation creates executable files.

**Handling:**
1. Track file permissions as part of creation
2. Rollback removes file entirely (permissions don't matter)
3. git checkout restores original permissions for modified files

### Large Files

**Scenario:** Simulation creates large binary files.

**Handling:**
1. Track all files regardless of size
2. No special handling needed
3. Rollback deletes created files normally

---

## Storage

Simulation context is persisted for recovery:

```
.phaser/
└── simulation.yaml    # Active simulation context (if any)
```

Format:
```yaml
audit_id: "security-audit-001"
root: "/path/to/project"
original_branch: "main"
stash_ref: "stash@{0}"
created_files:
  - "src/new_file.py"
  - "tests/test_new.py"
modified_files:
  - "src/existing.py"
deleted_files: []
started_at: "2025-12-05T10:30:00Z"
active: true
```

---

## Error Handling

### SimulationError

Base exception for simulation errors:

```python
class SimulationError(Exception):
    """Base exception for simulation errors."""
    pass

class SimulationAlreadyActiveError(SimulationError):
    """Raised when trying to start simulation while one is active."""
    pass

class NotAGitRepoError(SimulationError):
    """Raised when project root is not a git repository."""
    pass

class RollbackError(SimulationError):
    """Raised when rollback fails."""
    pass
```

---

## Safety Guarantees

| Guarantee                    | Mechanism                                |
| ---------------------------- | ---------------------------------------- |
| Uncommitted work preserved   | git stash before, pop after              |
| All changes reversible       | Track every file change                  |
| Recovery from interruption   | Persist context to storage               |
| No data loss                 | Rollback restores all tracked files      |

---

## Git Commands Used

| Command                      | Purpose                                  |
| ---------------------------- | ---------------------------------------- |
| `git rev-parse --is-inside-work-tree` | Verify git repo              |
| `git branch --show-current`  | Get current branch name                  |
| `git status --porcelain`     | Check for uncommitted changes            |
| `git stash push -m "..."`    | Stash uncommitted changes                |
| `git stash pop`              | Restore stashed changes                  |
| `git stash drop`             | Discard stash (on commit)                |
| `git checkout -- <file>`     | Restore file from HEAD                   |
| `git ls-files`               | List tracked files                       |

---

*Phaser v1.2*
