"""Simulation engine for safe dry-run audit execution.

This module provides sandbox functionality for running audits without
committing changes. Changes are tracked and can be rolled back.
"""

from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import click
import yaml

if TYPE_CHECKING:
    from tools.events import EventEmitter
    from tools.storage import PhaserStorage


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------


@dataclass
class SimulationContext:
    """Tracks the state of an active simulation session."""

    audit_id: str
    root: Path
    original_branch: str
    stash_ref: str | None
    created_files: list[Path] = field(default_factory=list)
    modified_files: list[Path] = field(default_factory=list)
    deleted_files: list[Path] = field(default_factory=list)
    started_at: str = ""
    active: bool = True

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

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
    def from_dict(cls, d: dict) -> SimulationContext:
        """Deserialize from persistence."""
        return cls(
            audit_id=d["audit_id"],
            root=Path(d["root"]),
            original_branch=d["original_branch"],
            stash_ref=d.get("stash_ref"),
            created_files=[Path(p) for p in d.get("created_files", [])],
            modified_files=[Path(p) for p in d.get("modified_files", [])],
            deleted_files=[Path(p) for p in d.get("deleted_files", [])],
            started_at=d.get("started_at", ""),
            active=d.get("active", True),
        )


@dataclass
class SimulationResult:
    """Result of a completed simulation."""

    success: bool
    phases_run: int
    phases_passed: int
    phases_failed: int
    first_failure: int | None
    failure_reason: str | None
    duration: float
    diff_summary: str
    files_created: int = 0
    files_modified: int = 0
    files_deleted: int = 0

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
        if self.first_failure is not None:
            lines.append(f"First failure: Phase {self.first_failure}")
            if self.failure_reason:
                lines.append(f"Reason: {self.failure_reason}")
        lines.append(f"Would create {self.files_created} files")
        lines.append(f"Would modify {self.files_modified} files")
        lines.append(f"Would delete {self.files_deleted} files")
        lines.append(f"Duration: {self.duration:.1f}s")
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Git Helpers
# -----------------------------------------------------------------------------


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def is_git_repo(root: Path) -> bool:
    """Check if root is inside a git repository."""
    result = _run_git(root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_current_branch(root: Path) -> str:
    """Get current git branch name."""
    result = _run_git(root, "branch", "--show-current")
    if result.returncode != 0:
        # Detached HEAD - get commit hash instead
        result = _run_git(root, "rev-parse", "--short", "HEAD")
    return result.stdout.strip()


def has_uncommitted_changes(root: Path) -> bool:
    """Check if working directory has uncommitted changes."""
    result = _run_git(root, "status", "--porcelain")
    return bool(result.stdout.strip())


def git_stash_push(root: Path, message: str) -> str | None:
    """Create stash, return stash ref or None if nothing to stash."""
    if not has_uncommitted_changes(root):
        return None

    result = _run_git(root, "stash", "push", "-m", message)
    if result.returncode != 0:
        raise SimulationError(f"Failed to stash: {result.stderr}")

    # Get the stash ref
    result = _run_git(root, "stash", "list", "-n", "1")
    if result.returncode == 0 and result.stdout.strip():
        # Parse "stash@{0}: On branch: message" to get "stash@{0}"
        return result.stdout.split(":")[0].strip()
    return "stash@{0}"


def git_stash_pop(root: Path, stash_ref: str) -> bool:
    """Restore stash."""
    result = _run_git(root, "stash", "pop", stash_ref)
    return result.returncode == 0


def git_stash_drop(root: Path, stash_ref: str) -> bool:
    """Drop a stash without applying it."""
    result = _run_git(root, "stash", "drop", stash_ref)
    return result.returncode == 0


def git_checkout_file(root: Path, path: Path) -> bool:
    """Restore file from HEAD."""
    rel_path = path.relative_to(root) if path.is_absolute() else path
    result = _run_git(root, "checkout", "--", str(rel_path))
    return result.returncode == 0


def get_tracked_files(root: Path) -> set[Path]:
    """Get set of git-tracked files."""
    result = _run_git(root, "ls-files")
    if result.returncode != 0:
        return set()
    return {Path(p) for p in result.stdout.strip().split("\n") if p}


def is_file_tracked(root: Path, path: Path) -> bool:
    """Check if a file is tracked by git."""
    rel_path = path.relative_to(root) if path.is_absolute() else path
    result = _run_git(root, "ls-files", "--error-unmatch", str(rel_path))
    return result.returncode == 0


# -----------------------------------------------------------------------------
# Storage Helpers
# -----------------------------------------------------------------------------


def _get_simulation_path(root: Path) -> Path:
    """Get path to simulation context file."""
    phaser_dir = root / ".phaser"
    phaser_dir.mkdir(exist_ok=True)
    return phaser_dir / "simulation.yaml"


def _save_context(ctx: SimulationContext) -> None:
    """Save simulation context to disk."""
    path = _get_simulation_path(ctx.root)
    with open(path, "w") as f:
        yaml.safe_dump(ctx.to_dict(), f, default_flow_style=False)


def _load_context(root: Path) -> SimulationContext | None:
    """Load simulation context from disk."""
    path = _get_simulation_path(root)
    if not path.exists():
        return None
    with open(path) as f:
        data = yaml.safe_load(f)
    if data:
        return SimulationContext.from_dict(data)
    return None


def _remove_context(root: Path) -> None:
    """Remove simulation context file."""
    path = _get_simulation_path(root)
    if path.exists():
        path.unlink()


# -----------------------------------------------------------------------------
# Core Operations
# -----------------------------------------------------------------------------


def begin_simulation(
    root: Path,
    audit_id: str,
    storage: PhaserStorage | None = None,
) -> SimulationContext:
    """
    Begin a simulation session.

    Args:
        root: Project root directory
        audit_id: Audit identifier
        storage: Optional PhaserStorage instance (unused, for API compatibility)

    Returns:
        SimulationContext for tracking changes

    Raises:
        NotAGitRepoError: If root is not a git repository
        SimulationAlreadyActiveError: If simulation is already active
    """
    root = root.resolve()

    # Verify git repo
    if not is_git_repo(root):
        raise NotAGitRepoError(f"Not a git repository: {root}")

    # Check for existing simulation
    existing = _load_context(root)
    if existing and existing.active:
        raise SimulationAlreadyActiveError(
            f"Simulation already active for audit: {existing.audit_id}"
        )

    # Record current branch
    original_branch = get_current_branch(root)

    # Stash uncommitted changes
    stash_ref = git_stash_push(root, f"phaser-simulation-{audit_id}")

    # Create context
    ctx = SimulationContext(
        audit_id=audit_id,
        root=root,
        original_branch=original_branch,
        stash_ref=stash_ref,
    )

    # Persist for recovery
    _save_context(ctx)

    return ctx


def track_file_change(
    ctx: SimulationContext,
    path: Path,
    change_type: str,
) -> None:
    """
    Track a file change during simulation.

    Args:
        ctx: Active simulation context
        path: Path to the changed file
        change_type: One of "created", "modified", "deleted"
    """
    # Resolve to absolute path
    if not path.is_absolute():
        path = ctx.root / path

    # Get relative path for storage
    try:
        rel_path = path.relative_to(ctx.root)
    except ValueError:
        # File is outside project root - skip tracking
        return

    if change_type == "created":
        if rel_path not in ctx.created_files:
            ctx.created_files.append(rel_path)
    elif change_type == "modified":
        if rel_path not in ctx.modified_files:
            ctx.modified_files.append(rel_path)
    elif change_type == "deleted":
        if rel_path not in ctx.deleted_files:
            ctx.deleted_files.append(rel_path)

    # Update persisted context
    _save_context(ctx)


def rollback_simulation(ctx: SimulationContext) -> bool:
    """
    Rollback all changes made during simulation.

    Args:
        ctx: Active simulation context

    Returns:
        True if rollback succeeded, False otherwise
    """
    if not ctx.active:
        return True

    success = True

    # Delete created files
    for rel_path in ctx.created_files:
        full_path = ctx.root / rel_path
        if full_path.exists():
            try:
                full_path.unlink()
                # Remove empty parent directories
                parent = full_path.parent
                while parent != ctx.root:
                    if parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()
                    parent = parent.parent
            except OSError:
                success = False

    # Restore modified files from git
    for rel_path in ctx.modified_files:
        if not git_checkout_file(ctx.root, rel_path):
            success = False

    # Restore deleted files from git
    for rel_path in ctx.deleted_files:
        if not git_checkout_file(ctx.root, rel_path):
            success = False

    # Pop stash if one was created
    if ctx.stash_ref:
        if not git_stash_pop(ctx.root, ctx.stash_ref):
            success = False

    # Mark context inactive
    ctx.active = False
    _remove_context(ctx.root)

    return success


def commit_simulation(ctx: SimulationContext) -> bool:
    """
    Keep simulation changes (make them real).

    Args:
        ctx: Active simulation context

    Returns:
        True if commit succeeded
    """
    if not ctx.active:
        return True

    # Drop stash (don't restore original uncommitted changes)
    if ctx.stash_ref:
        git_stash_drop(ctx.root, ctx.stash_ref)

    # Mark context inactive
    ctx.active = False
    _remove_context(ctx.root)

    return True


def get_active_simulation(
    root: Path,
    storage: PhaserStorage | None = None,
) -> SimulationContext | None:
    """
    Get active simulation context if one exists.

    Args:
        root: Project root directory
        storage: Optional PhaserStorage instance (unused, for API compatibility)

    Returns:
        SimulationContext if active simulation, None otherwise
    """
    ctx = _load_context(root)
    if ctx and ctx.active:
        return ctx
    return None


# -----------------------------------------------------------------------------
# Context Manager
# -----------------------------------------------------------------------------


@contextmanager
def simulation_context(
    root: Path,
    audit_id: str,
    auto_rollback: bool = True,
) -> Generator[SimulationContext, None, None]:
    """
    Context manager for simulations.

    Args:
        root: Project root directory
        audit_id: Audit identifier
        auto_rollback: If True, rollback on exit. If False, keep changes.

    Yields:
        SimulationContext for tracking changes
    """
    ctx = begin_simulation(root, audit_id)
    try:
        yield ctx
    finally:
        if auto_rollback:
            rollback_simulation(ctx)
        else:
            commit_simulation(ctx)


# -----------------------------------------------------------------------------
# High-Level API
# -----------------------------------------------------------------------------


def simulate_audit(
    root: Path,
    audit_id: str,
    phases: list[int] | None = None,
    storage: PhaserStorage | None = None,
    emitter: EventEmitter | None = None,
) -> SimulationResult:
    """
    Simulate an audit (or specific phases).

    This is a high-level function that:
    1. Begins simulation
    2. Executes phases (placeholder - actual execution would be handled by runner)
    3. Captures what would change
    4. Rolls back all changes
    5. Returns result

    Args:
        root: Project root directory
        audit_id: Audit identifier
        phases: Optional list of phase numbers to run (None = all)
        storage: Optional PhaserStorage instance
        emitter: Optional EventEmitter instance

    Returns:
        SimulationResult with outcome details
    """
    start_time = time.time()
    root = root.resolve()

    ctx = begin_simulation(root, audit_id, storage)

    try:
        # Placeholder for phase execution
        # In real usage, this would be called by AuditRunner
        phases_run = len(phases) if phases else 0
        phases_passed = phases_run
        phases_failed = 0
        first_failure = None
        failure_reason = None

        # Build diff summary
        diff_parts = []
        if ctx.created_files:
            diff_parts.append(f"+{len(ctx.created_files)} created")
        if ctx.modified_files:
            diff_parts.append(f"~{len(ctx.modified_files)} modified")
        if ctx.deleted_files:
            diff_parts.append(f"-{len(ctx.deleted_files)} deleted")
        diff_summary = ", ".join(diff_parts) if diff_parts else "No changes"

        result = SimulationResult(
            success=phases_failed == 0,
            phases_run=phases_run,
            phases_passed=phases_passed,
            phases_failed=phases_failed,
            first_failure=first_failure,
            failure_reason=failure_reason,
            duration=time.time() - start_time,
            diff_summary=diff_summary,
            files_created=len(ctx.created_files),
            files_modified=len(ctx.modified_files),
            files_deleted=len(ctx.deleted_files),
        )

    finally:
        # Always rollback
        rollback_simulation(ctx)

    return result


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Simulation commands for safe dry-run execution."""
    pass


@cli.command("run")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory",
)
@click.option(
    "--phases",
    type=str,
    default=None,
    help="Phase range, e.g., '1-5' or '3'",
)
@click.option(
    "--commit-on-success",
    is_flag=True,
    help="Keep changes if all phases pass",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def run_cmd(
    root: Path,
    phases: str | None,
    commit_on_success: bool,
    verbose: bool,
) -> None:
    """Simulate audit execution."""
    # Parse phases
    phase_list: list[int] | None = None
    if phases:
        if "-" in phases:
            start, end = phases.split("-", 1)
            phase_list = list(range(int(start), int(end) + 1))
        else:
            phase_list = [int(phases)]

    try:
        result = simulate_audit(root.resolve(), "cli-simulation", phase_list)
        click.echo(result.summary())

        if verbose:
            click.echo("\nDetails:")
            click.echo(f"  Diff: {result.diff_summary}")

    except SimulationError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command("status")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory",
)
def status_cmd(root: Path) -> None:
    """Show active simulation status."""
    ctx = get_active_simulation(root.resolve())

    if ctx is None:
        click.echo("No active simulation")
        return

    click.echo(f"Active simulation: {ctx.audit_id}")
    click.echo(f"  Started: {ctx.started_at}")
    click.echo(f"  Branch: {ctx.original_branch}")
    click.echo(f"  Stash: {ctx.stash_ref or 'none'}")
    click.echo(f"  Created files: {len(ctx.created_files)}")
    click.echo(f"  Modified files: {len(ctx.modified_files)}")
    click.echo(f"  Deleted files: {len(ctx.deleted_files)}")


@cli.command("rollback")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory",
)
def rollback_cmd(root: Path) -> None:
    """Rollback active simulation."""
    ctx = get_active_simulation(root.resolve())

    if ctx is None:
        click.echo("No active simulation to rollback")
        return

    if rollback_simulation(ctx):
        click.echo(f"Rolled back simulation: {ctx.audit_id}")
        click.echo(f"  Deleted {len(ctx.created_files)} created files")
        click.echo(f"  Restored {len(ctx.modified_files)} modified files")
        click.echo(f"  Restored {len(ctx.deleted_files)} deleted files")
        if ctx.stash_ref:
            click.echo("  Restored stashed changes")
    else:
        click.echo("Rollback completed with errors", err=True)
        raise SystemExit(1)


@cli.command("commit")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory",
)
def commit_cmd(root: Path) -> None:
    """Commit active simulation (keep changes)."""
    ctx = get_active_simulation(root.resolve())

    if ctx is None:
        click.echo("No active simulation to commit")
        return

    if commit_simulation(ctx):
        click.echo(f"Committed simulation: {ctx.audit_id}")
        click.echo("  Changes are now permanent")
        if ctx.stash_ref:
            click.echo("  Note: Original uncommitted changes were discarded")
    else:
        click.echo("Commit failed", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
