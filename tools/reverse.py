"""
Phaser Reverse Audit

Generate structured audit documents from git diffs.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# Enums
# =============================================================================


class GroupingStrategy(str, Enum):
    """Strategy for grouping commits into phases."""

    COMMITS = "commits"
    DIRECTORIES = "directories"
    FILETYPES = "filetypes"
    SEMANTIC = "semantic"


class ChangeCategory(str, Enum):
    """Category of changes in a phase."""

    FEATURE = "feature"
    REFACTOR = "refactor"
    FIX = "fix"
    TEST = "test"
    DOCS = "docs"
    CHORE = "chore"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FileChangeInfo:
    """Information about a file change in a commit."""

    path: str
    change_type: str  # "added", "modified", "deleted", "renamed"
    insertions: int = 0
    deletions: int = 0
    old_path: str | None = None  # For renames

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "path": self.path,
            "change_type": self.change_type,
            "insertions": self.insertions,
            "deletions": self.deletions,
        }
        if self.old_path:
            result["old_path"] = self.old_path
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileChangeInfo:
        """Create from dictionary."""
        return cls(
            path=d["path"],
            change_type=d["change_type"],
            insertions=d.get("insertions", 0),
            deletions=d.get("deletions", 0),
            old_path=d.get("old_path"),
        )


@dataclass
class CommitInfo:
    """Information about a git commit."""

    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    files: list[FileChangeInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "hash": self.hash,
            "short_hash": self.short_hash,
            "author": self.author,
            "date": self.date,
            "message": self.message,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "files": [f.to_dict() for f in self.files],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CommitInfo:
        """Create from dictionary."""
        return cls(
            hash=d["hash"],
            short_hash=d["short_hash"],
            author=d["author"],
            date=d["date"],
            message=d["message"],
            files_changed=d.get("files_changed", 0),
            insertions=d.get("insertions", 0),
            deletions=d.get("deletions", 0),
            files=[FileChangeInfo.from_dict(f) for f in d.get("files", [])],
        )


@dataclass
class InferredPhase:
    """A phase inferred from git history."""

    number: int
    title: str
    description: str
    category: str
    commits: list[CommitInfo] = field(default_factory=list)
    files: list[FileChangeInfo] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        """Number of unique files in this phase."""
        return len(set(f.path for f in self.files))

    @property
    def total_insertions(self) -> int:
        """Total insertions in this phase."""
        return sum(f.insertions for f in self.files)

    @property
    def total_deletions(self) -> int:
        """Total deletions in this phase."""
        return sum(f.deletions for f in self.files)

    @property
    def total_changes(self) -> int:
        """Total line changes in this phase."""
        return self.total_insertions + self.total_deletions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "commits": [c.to_dict() for c in self.commits],
            "files": [f.to_dict() for f in self.files],
            "file_count": self.file_count,
            "total_insertions": self.total_insertions,
            "total_deletions": self.total_deletions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InferredPhase:
        """Create from dictionary."""
        return cls(
            number=d["number"],
            title=d["title"],
            description=d["description"],
            category=d["category"],
            commits=[CommitInfo.from_dict(c) for c in d.get("commits", [])],
            files=[FileChangeInfo.from_dict(f) for f in d.get("files", [])],
        )


@dataclass
class ReverseAuditResult:
    """Result of reverse audit generation."""

    title: str
    project: str
    commit_range: str
    strategy: str
    generated_at: str

    total_commits: int = 0
    total_files: int = 0
    total_insertions: int = 0
    total_deletions: int = 0

    phases: list[InferredPhase] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "project": self.project,
            "commit_range": self.commit_range,
            "strategy": self.strategy,
            "generated_at": self.generated_at,
            "summary": {
                "total_commits": self.total_commits,
                "total_files": self.total_files,
                "total_insertions": self.total_insertions,
                "total_deletions": self.total_deletions,
            },
            "phases": [p.to_dict() for p in self.phases],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReverseAuditResult:
        """Create from dictionary."""
        summary = d.get("summary", {})
        return cls(
            title=d["title"],
            project=d["project"],
            commit_range=d["commit_range"],
            strategy=d["strategy"],
            generated_at=d["generated_at"],
            total_commits=summary.get("total_commits", 0),
            total_files=summary.get("total_files", 0),
            total_insertions=summary.get("total_insertions", 0),
            total_deletions=summary.get("total_deletions", 0),
            phases=[InferredPhase.from_dict(p) for p in d.get("phases", [])],
        )


# =============================================================================
# Git Helper Functions
# =============================================================================


def run_git_command(
    args: list[str],
    repo_path: Path | None = None,
) -> str:
    """
    Run a git command and return output.

    Args:
        args: Git command arguments (without 'git')
        repo_path: Repository path (default: current directory)

    Returns:
        Command output as string

    Raises:
        ValueError: If not a git repository
        subprocess.CalledProcessError: If command fails
    """
    cwd = repo_path or Path.cwd()

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise ValueError("Git is not installed or not in PATH")
    except subprocess.CalledProcessError as e:
        if "not a git repository" in e.stderr.lower():
            raise ValueError(f"Not a git repository: {cwd}")
        raise


def is_git_repository(path: Path | None = None) -> bool:
    """Check if path is inside a git repository."""
    try:
        run_git_command(["rev-parse", "--is-inside-work-tree"], path)
        return True
    except (ValueError, subprocess.CalledProcessError):
        return False


def validate_commit_range(
    commit_range: str,
    repo_path: Path | None = None,
) -> bool:
    """
    Validate that a commit range is valid.

    Args:
        commit_range: Git commit range string
        repo_path: Repository path

    Returns:
        True if valid, raises ValueError if not
    """
    try:
        # Parse range into start and end refs
        if ".." in commit_range:
            parts = commit_range.split("..")
            for part in parts:
                if part:  # Skip empty parts (e.g., "..HEAD")
                    run_git_command(["rev-parse", "--verify", part], repo_path)
        else:
            run_git_command(["rev-parse", "--verify", commit_range], repo_path)
        return True
    except subprocess.CalledProcessError:
        raise ValueError(
            f"Invalid commit range: {commit_range}\n"
            "Examples of valid ranges:\n"
            "  HEAD~5..HEAD\n"
            "  main..feature-branch\n"
            "  abc123..def456"
        )


def get_current_branch(repo_path: Path | None = None) -> str:
    """Get the current branch name."""
    try:
        return run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    except subprocess.CalledProcessError:
        return "unknown"


def get_repo_name(repo_path: Path | None = None) -> str:
    """Get the repository name from remote or directory."""
    path = repo_path or Path.cwd()

    # Try to get from remote
    try:
        remote = run_git_command(["remote", "get-url", "origin"], path)
        # Extract repo name from URL
        name = remote.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name
    except subprocess.CalledProcessError:
        pass

    # Fall back to directory name
    return path.resolve().name


# =============================================================================
# Commit Parsing Functions
# =============================================================================


def parse_commit_range(
    commit_range: str,
    repo_path: Path | None = None,
    include_merges: bool = False,
) -> list[CommitInfo]:
    """
    Parse a git commit range and return commit information.

    Args:
        commit_range: Git commit range (e.g., "HEAD~5..HEAD")
        repo_path: Path to repository (default: current directory)
        include_merges: Include merge commits (default: False)

    Returns:
        List of CommitInfo, oldest first

    Raises:
        ValueError: If commit range is invalid or not a git repo
    """
    validate_commit_range(commit_range, repo_path)

    # Format: hash|short_hash|author|date|message
    format_str = "%H|%h|%an|%aI|%s"

    args = [
        "log",
        "--format=" + format_str,
        "--reverse",  # Oldest first
        commit_range,
    ]

    if not include_merges:
        args.append("--no-merges")

    output = run_git_command(args, repo_path)

    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        if not line.strip():
            continue

        parts = line.split("|", 4)
        if len(parts) < 5:
            continue

        hash_, short_hash, author, date, message = parts

        # Get file changes for this commit
        files = get_commit_files(hash_, repo_path)

        # Calculate totals
        insertions = sum(f.insertions for f in files)
        deletions = sum(f.deletions for f in files)

        commits.append(
            CommitInfo(
                hash=hash_,
                short_hash=short_hash,
                author=author,
                date=date,
                message=message,
                files_changed=len(files),
                insertions=insertions,
                deletions=deletions,
                files=files,
            )
        )

    return commits


def get_commit_files(
    commit_hash: str,
    repo_path: Path | None = None,
) -> list[FileChangeInfo]:
    """
    Get files changed in a specific commit.

    Args:
        commit_hash: Git commit hash
        repo_path: Path to repository

    Returns:
        List of FileChangeInfo for files in commit
    """
    # Get numstat for insertions/deletions
    numstat = run_git_command(
        ["show", "--numstat", "--format=", commit_hash],
        repo_path,
    )

    # Get name-status for change types
    name_status = run_git_command(
        ["show", "--name-status", "--format=", commit_hash],
        repo_path,
    )

    # Parse name-status to get change types
    change_types: dict[str, tuple[str, str | None]] = {}  # path -> (type, old_path)
    for line in name_status.split("\n"):
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            if status.startswith("R"):  # Renamed
                old_path = parts[1]
                new_path = parts[2] if len(parts) > 2 else parts[1]
                change_types[new_path] = ("renamed", old_path)
            elif status == "A":
                change_types[parts[1]] = ("added", None)
            elif status == "D":
                change_types[parts[1]] = ("deleted", None)
            elif status == "M":
                change_types[parts[1]] = ("modified", None)
            else:
                change_types[parts[1]] = ("modified", None)

    # Parse numstat for line counts
    files = []
    for line in numstat.split("\n"):
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        insertions_str, deletions_str, path = parts[0], parts[1], parts[2]

        # Handle binary files (shown as -)
        try:
            insertions = int(insertions_str) if insertions_str != "-" else 0
            deletions = int(deletions_str) if deletions_str != "-" else 0
        except ValueError:
            insertions = 0
            deletions = 0

        # Handle renames with arrow notation: old_path => new_path
        if " => " in path:
            # Parse rename format: {old => new}/path or path/{old => new}
            path = path.split(" => ")[-1].rstrip("}")
            if "{" in path:
                path = path.replace("{", "").replace("}", "")

        change_type, old_path = change_types.get(path, ("modified", None))

        files.append(
            FileChangeInfo(
                path=path,
                change_type=change_type,
                insertions=insertions,
                deletions=deletions,
                old_path=old_path,
            )
        )

    return files


def get_diff_stats(
    commit_range: str,
    repo_path: Path | None = None,
) -> tuple[int, int, int]:
    """
    Get aggregate diff statistics for a commit range.

    Args:
        commit_range: Git commit range
        repo_path: Repository path

    Returns:
        Tuple of (files_changed, insertions, deletions)
    """
    try:
        output = run_git_command(
            ["diff", "--shortstat", commit_range],
            repo_path,
        )
    except subprocess.CalledProcessError:
        return 0, 0, 0

    if not output:
        return 0, 0, 0

    files = insertions = deletions = 0

    # Parse: "X files changed, Y insertions(+), Z deletions(-)"
    files_match = re.search(r"(\d+) files? changed", output)
    if files_match:
        files = int(files_match.group(1))

    insertions_match = re.search(r"(\d+) insertions?\(\+\)", output)
    if insertions_match:
        insertions = int(insertions_match.group(1))

    deletions_match = re.search(r"(\d+) deletions?\(-\)", output)
    if deletions_match:
        deletions = int(deletions_match.group(1))

    return files, insertions, deletions


# =============================================================================
# Helper Functions
# =============================================================================


def now_iso() -> str:
    """Get current time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
