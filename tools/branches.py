"""Branch management for phase-by-phase audit execution.

This module provides git branch management for audits, creating
a branch for each phase to enable PR-style review workflows.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import click
import yaml

if TYPE_CHECKING:
    from tools.storage import PhaserStorage


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class BranchError(Exception):
    """Base exception for branch errors."""

    pass


class BranchModeAlreadyActiveError(BranchError):
    """Raised when trying to start branch mode while one is active."""

    pass


class BranchExistsError(BranchError):
    """Raised when branch already exists."""

    pass


class MergeConflictError(BranchError):
    """Raised when merge has conflicts."""

    pass


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class MergeStrategy(str, Enum):
    """Strategies for merging phase branches."""

    SQUASH = "squash"
    REBASE = "rebase"
    MERGE = "merge"


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------


@dataclass
class BranchInfo:
    """Information about a single phase branch."""

    phase_num: int
    phase_slug: str
    branch_name: str
    created_at: str
    commit_sha: str | None = None
    merged: bool = False

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "phase_num": self.phase_num,
            "phase_slug": self.phase_slug,
            "branch_name": self.branch_name,
            "created_at": self.created_at,
            "commit_sha": self.commit_sha,
            "merged": self.merged,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BranchInfo:
        """Deserialize from persistence."""
        return cls(
            phase_num=d["phase_num"],
            phase_slug=d["phase_slug"],
            branch_name=d["branch_name"],
            created_at=d["created_at"],
            commit_sha=d.get("commit_sha"),
            merged=d.get("merged", False),
        )


@dataclass
class BranchContext:
    """Tracks the state of branch mode for an audit."""

    audit_id: str
    audit_slug: str
    root: Path
    base_branch: str
    current_phase: int | None = None
    branches: list[BranchInfo] = field(default_factory=list)
    active: bool = True

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "audit_id": self.audit_id,
            "audit_slug": self.audit_slug,
            "root": str(self.root),
            "base_branch": self.base_branch,
            "current_phase": self.current_phase,
            "branches": [b.to_dict() for b in self.branches],
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BranchContext:
        """Deserialize from persistence."""
        return cls(
            audit_id=d["audit_id"],
            audit_slug=d["audit_slug"],
            root=Path(d["root"]),
            base_branch=d["base_branch"],
            current_phase=d.get("current_phase"),
            branches=[BranchInfo.from_dict(b) for b in d.get("branches", [])],
            active=d.get("active", True),
        )

    def get_branch(self, phase_num: int) -> BranchInfo | None:
        """Get branch info for a phase number."""
        for b in self.branches:
            if b.phase_num == phase_num:
                return b
        return None

    def current_branch_name(self) -> str | None:
        """Get name of current phase branch."""
        if self.current_phase is None:
            return None
        branch = self.get_branch(self.current_phase)
        return branch.branch_name if branch else None

    def last_branch_name(self) -> str | None:
        """Get name of most recent phase branch."""
        if not self.branches:
            return None
        return self.branches[-1].branch_name


# -----------------------------------------------------------------------------
# Git Operations
# -----------------------------------------------------------------------------


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def get_current_branch(root: Path) -> str:
    """Get current git branch name."""
    result = _run_git(root, "branch", "--show-current")
    if result.returncode != 0 or not result.stdout.strip():
        # Detached HEAD - get commit hash instead
        result = _run_git(root, "rev-parse", "--short", "HEAD")
    return result.stdout.strip()


def branch_exists(root: Path, branch_name: str) -> bool:
    """Check if branch exists locally."""
    result = _run_git(root, "rev-parse", "--verify", f"refs/heads/{branch_name}")
    return result.returncode == 0


def create_branch(root: Path, branch_name: str, from_ref: str | None = None) -> bool:
    """Create a new branch."""
    if from_ref:
        result = _run_git(root, "branch", branch_name, from_ref)
    else:
        result = _run_git(root, "branch", branch_name)
    return result.returncode == 0


def checkout_branch(root: Path, branch_name: str) -> bool:
    """Checkout existing branch."""
    result = _run_git(root, "checkout", branch_name)
    return result.returncode == 0


def checkout_new_branch(root: Path, branch_name: str, from_ref: str | None = None) -> bool:
    """Create and checkout a new branch."""
    if from_ref:
        result = _run_git(root, "checkout", "-b", branch_name, from_ref)
    else:
        result = _run_git(root, "checkout", "-b", branch_name)
    return result.returncode == 0


def commit_all(root: Path, message: str) -> str | None:
    """Stage all and commit, return SHA or None if nothing to commit."""
    # Stage all changes
    result = _run_git(root, "add", "-A")
    if result.returncode != 0:
        return None

    # Check if there's anything to commit
    result = _run_git(root, "status", "--porcelain")
    if not result.stdout.strip():
        return None  # Nothing to commit

    # Commit
    result = _run_git(root, "commit", "-m", message)
    if result.returncode != 0:
        return None

    # Get commit SHA
    result = _run_git(root, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def delete_branch(root: Path, branch_name: str, force: bool = False) -> bool:
    """Delete a branch."""
    flag = "-D" if force else "-d"
    result = _run_git(root, "branch", flag, branch_name)
    return result.returncode == 0


def merge_branch(
    root: Path,
    source: str,
    target: str,
    strategy: MergeStrategy,
    message: str | None = None,
) -> bool:
    """Merge source into target using strategy."""
    # Checkout target
    if not checkout_branch(root, target):
        return False

    if strategy == MergeStrategy.SQUASH:
        result = _run_git(root, "merge", "--squash", source)
        if result.returncode != 0:
            return False
        # Squash merge requires a separate commit
        if message:
            result = _run_git(root, "commit", "-m", message)
        else:
            result = _run_git(root, "commit", "-m", f"Merge {source}")
        return result.returncode == 0

    elif strategy == MergeStrategy.REBASE:
        # First rebase source onto target
        if not checkout_branch(root, source):
            return False
        result = _run_git(root, "rebase", target)
        if result.returncode != 0:
            return False
        # Then fast-forward target
        if not checkout_branch(root, target):
            return False
        result = _run_git(root, "merge", "--ff-only", source)
        return result.returncode == 0

    elif strategy == MergeStrategy.MERGE:
        if message:
            result = _run_git(root, "merge", "--no-ff", "-m", message, source)
        else:
            result = _run_git(root, "merge", "--no-ff", source)
        return result.returncode == 0

    return False


def has_uncommitted_changes(root: Path) -> bool:
    """Check if working directory has uncommitted changes."""
    result = _run_git(root, "status", "--porcelain")
    return bool(result.stdout.strip())


# -----------------------------------------------------------------------------
# Storage Helpers
# -----------------------------------------------------------------------------


def _get_branches_path(root: Path) -> Path:
    """Get path to branch context file."""
    phaser_dir = root / ".phaser"
    phaser_dir.mkdir(exist_ok=True)
    return phaser_dir / "branches.yaml"


def _save_context(ctx: BranchContext) -> None:
    """Save branch context to disk."""
    path = _get_branches_path(ctx.root)
    with open(path, "w") as f:
        yaml.safe_dump(ctx.to_dict(), f, default_flow_style=False)


def _load_context(root: Path) -> BranchContext | None:
    """Load branch context from disk."""
    path = _get_branches_path(root)
    if not path.exists():
        return None
    with open(path) as f:
        data = yaml.safe_load(f)
    if data:
        return BranchContext.from_dict(data)
    return None


def _remove_context(root: Path) -> None:
    """Remove branch context file."""
    path = _get_branches_path(root)
    if path.exists():
        path.unlink()


# -----------------------------------------------------------------------------
# Core Operations
# -----------------------------------------------------------------------------


def begin_branch_mode(
    root: Path,
    audit_id: str,
    audit_slug: str,
    base_branch: str | None = None,
    storage: PhaserStorage | None = None,
) -> BranchContext:
    """
    Initialize branch mode for an audit.

    Args:
        root: Project root directory
        audit_id: Audit identifier
        audit_slug: Audit slug for branch naming
        base_branch: Base branch (default: current branch)
        storage: Optional storage instance (unused, for API compatibility)

    Returns:
        BranchContext for tracking branches

    Raises:
        BranchModeAlreadyActiveError: If branch mode already active
        BranchError: If uncommitted changes exist
    """
    root = root.resolve()

    # Check for existing context
    existing = _load_context(root)
    if existing and existing.active:
        raise BranchModeAlreadyActiveError(
            f"Branch mode already active for audit: {existing.audit_id}"
        )

    # Check for uncommitted changes
    if has_uncommitted_changes(root):
        raise BranchError("Cannot start branch mode with uncommitted changes")

    # Record base branch
    if base_branch is None:
        base_branch = get_current_branch(root)

    # Create context
    ctx = BranchContext(
        audit_id=audit_id,
        audit_slug=audit_slug,
        root=root,
        base_branch=base_branch,
    )

    # Persist for recovery
    _save_context(ctx)

    return ctx


def create_phase_branch(
    ctx: BranchContext,
    phase_num: int,
    phase_slug: str,
) -> BranchInfo:
    """
    Create branch for a phase.

    Args:
        ctx: Active branch context
        phase_num: Phase number
        phase_slug: Phase slug for naming

    Returns:
        BranchInfo for the new branch

    Raises:
        BranchExistsError: If branch already exists
    """
    # Generate branch name
    branch_name = f"audit/{ctx.audit_slug}/phase-{phase_num:02d}-{phase_slug}"

    # Check if branch exists
    if branch_exists(ctx.root, branch_name):
        raise BranchExistsError(f"Branch already exists: {branch_name}")

    # Determine base for new branch
    if ctx.branches:
        # Branch from previous phase
        from_ref = ctx.branches[-1].branch_name
    else:
        # Branch from base
        from_ref = ctx.base_branch

    # Create and checkout
    if not checkout_new_branch(ctx.root, branch_name, from_ref):
        raise BranchError(f"Failed to create branch: {branch_name}")

    # Create BranchInfo
    info = BranchInfo(
        phase_num=phase_num,
        phase_slug=phase_slug,
        branch_name=branch_name,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    # Update context
    ctx.branches.append(info)
    ctx.current_phase = phase_num
    _save_context(ctx)

    return info


def commit_phase(
    ctx: BranchContext,
    phase_num: int,
    message: str | None = None,
) -> str | None:
    """
    Commit current changes for phase.

    Args:
        ctx: Active branch context
        phase_num: Phase number
        message: Commit message (default: "Phase {N}: {slug}")

    Returns:
        Commit SHA or None if nothing to commit
    """
    branch = ctx.get_branch(phase_num)
    if branch is None:
        return None

    if message is None:
        message = f"Phase {phase_num}: {branch.phase_slug}"

    sha = commit_all(ctx.root, message)
    if sha:
        branch.commit_sha = sha
        _save_context(ctx)

    return sha


def merge_all_branches(
    ctx: BranchContext,
    target: str | None = None,
    strategy: MergeStrategy = MergeStrategy.SQUASH,
) -> bool:
    """
    Merge all phase branches into target.

    Args:
        ctx: Active branch context
        target: Target branch (default: base_branch)
        strategy: Merge strategy to use

    Returns:
        True if merge succeeded
    """
    if target is None:
        target = ctx.base_branch

    if not ctx.branches:
        return True  # Nothing to merge

    # Get the last branch (contains all changes due to linear structure)
    last_branch = ctx.branches[-1].branch_name

    # Merge
    message = f"Complete {ctx.audit_slug} audit"
    if not merge_branch(ctx.root, last_branch, target, strategy, message):
        return False

    # Mark all branches as merged
    for branch in ctx.branches:
        branch.merged = True
    _save_context(ctx)

    return True


def cleanup_branches(
    ctx: BranchContext,
    merged_only: bool = True,
) -> int:
    """
    Delete phase branches.

    Args:
        ctx: Active branch context
        merged_only: If True, only delete merged branches

    Returns:
        Number of branches deleted
    """
    deleted = 0

    # Make sure we're not on a branch we're about to delete
    checkout_branch(ctx.root, ctx.base_branch)

    for branch in ctx.branches:
        if merged_only and not branch.merged:
            continue

        # Always force delete - squash merges don't show as merged to git
        # We track merge status ourselves via branch.merged
        if delete_branch(ctx.root, branch.branch_name, force=True):
            deleted += 1

    return deleted


def get_branch_context(
    root: Path,
    storage: PhaserStorage | None = None,
) -> BranchContext | None:
    """
    Load branch context from storage.

    Args:
        root: Project root directory
        storage: Optional storage instance (unused, for API compatibility)

    Returns:
        BranchContext if exists, None otherwise
    """
    ctx = _load_context(root)
    if ctx and ctx.active:
        return ctx
    return None


def end_branch_mode(ctx: BranchContext) -> None:
    """
    End branch mode, cleanup context.

    Args:
        ctx: Active branch context
    """
    ctx.active = False
    _remove_context(ctx.root)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Branch management commands for audit phases."""
    pass


@cli.command("enable")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory",
)
@click.option(
    "--base",
    type=str,
    default=None,
    help="Base branch (default: current)",
)
def enable_cmd(root: Path, base: str | None) -> None:
    """Enable branch mode for current audit."""
    try:
        # Would need to get audit info from .audit/CONTEXT.md in real usage
        ctx = begin_branch_mode(
            root.resolve(),
            audit_id="cli-audit",
            audit_slug="cli-audit",
            base_branch=base,
        )
        click.echo(f"Branch mode enabled")
        click.echo(f"  Base branch: {ctx.base_branch}")
        click.echo(f"  Audit: {ctx.audit_slug}")
    except BranchError as e:
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
    """Show branch mode status."""
    ctx = get_branch_context(root.resolve())

    if ctx is None:
        click.echo("Branch mode not active")
        return

    click.echo(f"Branch mode: active")
    click.echo(f"  Audit: {ctx.audit_slug}")
    click.echo(f"  Base: {ctx.base_branch}")
    click.echo(f"  Current phase: {ctx.current_phase or 'none'}")
    click.echo(f"  Branches: {len(ctx.branches)}")

    if ctx.branches:
        click.echo("\nPhase branches:")
        for b in ctx.branches:
            status = "merged" if b.merged else ("committed" if b.commit_sha else "active")
            click.echo(f"  [{status}] {b.branch_name}")


@cli.command("merge")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory",
)
@click.option(
    "--strategy",
    type=click.Choice(["squash", "rebase", "merge"]),
    default="squash",
    help="Merge strategy",
)
@click.option(
    "--target",
    type=str,
    default=None,
    help="Target branch (default: base)",
)
def merge_cmd(root: Path, strategy: str, target: str | None) -> None:
    """Merge all phase branches."""
    ctx = get_branch_context(root.resolve())

    if ctx is None:
        click.echo("Branch mode not active")
        raise SystemExit(1)

    strat = MergeStrategy(strategy)
    if merge_all_branches(ctx, target, strat):
        click.echo(f"Merged {len(ctx.branches)} branches into {target or ctx.base_branch}")
        click.echo(f"  Strategy: {strategy}")
    else:
        click.echo("Merge failed", err=True)
        raise SystemExit(1)


@cli.command("cleanup")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory",
)
@click.option(
    "--all",
    "all_branches",
    is_flag=True,
    help="Delete all branches, not just merged",
)
def cleanup_cmd(root: Path, all_branches: bool) -> None:
    """Delete phase branches."""
    ctx = get_branch_context(root.resolve())

    if ctx is None:
        click.echo("Branch mode not active")
        raise SystemExit(1)

    deleted = cleanup_branches(ctx, merged_only=not all_branches)
    click.echo(f"Deleted {deleted} branches")

    # End branch mode after cleanup
    end_branch_mode(ctx)
    click.echo("Branch mode ended")


if __name__ == "__main__":
    cli()
