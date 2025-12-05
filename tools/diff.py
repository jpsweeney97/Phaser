"""
Phaser Diff Engine

Captures directory state as manifests and computes differences between them.
Used to track what changed during an audit.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import click
import yaml

if TYPE_CHECKING:
    from tools.storage import PhaserStorage


# Binary file extensions (skip content diff)
BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".a", ".o",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".pyc", ".pyo", ".class", ".jar",
    ".db", ".sqlite", ".sqlite3",
})

# Default patterns to exclude from manifest capture
DEFAULT_EXCLUDE_PATTERNS = [
    ".git",
    ".audit",
    ".phaser",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    ".DS_Store",
]

# Max file size for content diff (100KB)
DEFAULT_MAX_DIFF_SIZE = 100_000


@dataclass
class FileEntry:
    """A single file in a manifest."""

    path: str
    type: str  # "text" or "binary"
    size: int
    sha256: str
    content: str | None  # None for binary files
    is_executable: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "type": self.type,
            "size": self.size,
            "sha256": self.sha256,
            "content": self.content,
            "is_executable": self.is_executable,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> FileEntry:
        return cls(
            path=str(d["path"]),
            type=str(d["type"]),
            size=int(d["size"]),  # type: ignore[arg-type]
            sha256=str(d["sha256"]),
            content=d.get("content") if d.get("content") is not None else None,  # type: ignore[arg-type]
            is_executable=bool(d.get("is_executable", False)),
        )


@dataclass
class Manifest:
    """Snapshot of a directory's state at a point in time."""

    root: str
    timestamp: str
    file_count: int
    total_size_bytes: int
    files: list[FileEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "timestamp": self.timestamp,
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "files": [f.to_dict() for f in self.files],
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> Manifest:
        files_data = d.get("files", [])
        if not isinstance(files_data, list):
            files_data = []
        return cls(
            root=str(d["root"]),
            timestamp=str(d["timestamp"]),
            file_count=int(d["file_count"]),  # type: ignore[arg-type]
            total_size_bytes=int(d["total_size_bytes"]),  # type: ignore[arg-type]
            files=[FileEntry.from_dict(f) for f in files_data],  # type: ignore[arg-type]
        )

    def save(self, path: Path) -> None:
        """Save manifest to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        """Load manifest from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


@dataclass
class FileChange:
    """A single file change between two manifests."""

    path: str
    change_type: str  # "added", "modified", "deleted"
    before_hash: str | None
    after_hash: str | None
    before_size: int | None
    after_size: int | None
    diff_lines: list[str] | None  # Unified diff for text files

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "change_type": self.change_type,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "before_size": self.before_size,
            "after_size": self.after_size,
            "diff_lines": self.diff_lines,
        }


@dataclass
class DiffResult:
    """Result of comparing two manifests."""

    before_timestamp: str
    after_timestamp: str
    added: list[FileChange] = field(default_factory=list)
    modified: list[FileChange] = field(default_factory=list)
    deleted: list[FileChange] = field(default_factory=list)
    unchanged_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "before_timestamp": self.before_timestamp,
            "after_timestamp": self.after_timestamp,
            "added": [c.to_dict() for c in self.added],
            "modified": [c.to_dict() for c in self.modified],
            "deleted": [c.to_dict() for c in self.deleted],
            "unchanged_count": self.unchanged_count,
        }

    def summary(self) -> str:
        """One-line summary of changes."""
        parts = []
        if self.added:
            parts.append(f"+{len(self.added)} added")
        if self.modified:
            parts.append(f"~{len(self.modified)} modified")
        if self.deleted:
            parts.append(f"-{len(self.deleted)} deleted")
        if not parts:
            return "No changes"
        return ", ".join(parts)

    def detailed(self) -> str:
        """Full unified diff output."""
        lines: list[str] = []

        for change in self.added:
            lines.append(f"Added: {change.path}")

        for change in self.modified:
            lines.append(f"Modified: {change.path}")
            if change.diff_lines:
                lines.extend(change.diff_lines)
            lines.append("")

        for change in self.deleted:
            lines.append(f"Deleted: {change.path}")

        return "\n".join(lines)


def is_binary_file(path: Path, content: bytes) -> bool:
    """Determine if a file is binary based on extension or content."""
    # Check extension first
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    # Check for null bytes in first 8KB
    sample = content[:8192]
    return b"\x00" in sample


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def should_exclude(path: Path, root: Path, exclude_patterns: list[str]) -> bool:
    """Check if path should be excluded from manifest."""
    try:
        rel_path = path.relative_to(root)
    except ValueError:
        return True

    # Check each path component against exclude patterns
    parts = rel_path.parts
    for pattern in exclude_patterns:
        if pattern in parts:
            return True
        # Also check if the relative path starts with pattern
        if str(rel_path).startswith(pattern):
            return True

    return False


def capture_manifest(
    root: Path,
    exclude_patterns: list[str] | None = None,
) -> Manifest:
    """
    Capture current state of directory as manifest.

    Args:
        root: Directory to capture
        exclude_patterns: Glob patterns to exclude (e.g., [".git", ".audit"])

    Returns:
        Manifest snapshot of directory state
    """
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    patterns = exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDE_PATTERNS

    files: list[FileEntry] = []
    total_size = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        current = Path(dirpath)

        # Filter out excluded directories (modifies in-place)
        dirnames[:] = [
            d for d in sorted(dirnames)
            if not should_exclude(current / d, root, patterns)
        ]

        for filename in sorted(filenames):
            filepath = current / filename

            if should_exclude(filepath, root, patterns):
                continue

            try:
                stat_info = filepath.stat()
            except OSError:
                continue

            # Skip symlinks and special files
            if not stat_info.st_mode & stat.S_IFREG:
                continue

            try:
                raw_bytes = filepath.read_bytes()
            except OSError:
                continue

            file_hash = compute_file_hash(raw_bytes)
            is_binary = is_binary_file(filepath, raw_bytes)
            is_exec = bool(stat_info.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

            # Get content for text files only
            content: str | None = None
            if not is_binary:
                try:
                    content = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    is_binary = True

            try:
                rel_path = filepath.relative_to(root).as_posix()
            except ValueError:
                continue

            entry = FileEntry(
                path=rel_path,
                type="binary" if is_binary else "text",
                size=stat_info.st_size,
                sha256=file_hash,
                content=content,
                is_executable=is_exec,
            )
            files.append(entry)
            total_size += stat_info.st_size

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return Manifest(
        root=str(root),
        timestamp=timestamp,
        file_count=len(files),
        total_size_bytes=total_size,
        files=files,
    )


def compute_file_diff(
    before_content: str,
    after_content: str,
    path: str,
) -> list[str]:
    """
    Compute unified diff between two file contents.

    Args:
        before_content: Original file content
        after_content: New file content
        path: File path (for diff header)

    Returns:
        List of diff lines in unified format
    """
    before_lines = before_content.splitlines(keepends=True)
    after_lines = after_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )

    return [line.rstrip("\n") for line in diff]


def compare_manifests(
    before: Manifest,
    after: Manifest,
    include_diff: bool = True,
    max_diff_size: int = DEFAULT_MAX_DIFF_SIZE,
) -> DiffResult:
    """
    Compare two manifests and return differences.

    Args:
        before: Earlier manifest
        after: Later manifest
        include_diff: Whether to compute unified diff for text files
        max_diff_size: Skip diff for files larger than this (bytes)

    Returns:
        DiffResult with added, modified, deleted files
    """
    # Build path -> FileEntry maps
    before_map = {f.path: f for f in before.files}
    after_map = {f.path: f for f in after.files}

    before_paths = set(before_map.keys())
    after_paths = set(after_map.keys())

    added: list[FileChange] = []
    modified: list[FileChange] = []
    deleted: list[FileChange] = []
    unchanged_count = 0

    # Find added files (in after but not before)
    for path in sorted(after_paths - before_paths):
        entry = after_map[path]
        added.append(FileChange(
            path=path,
            change_type="added",
            before_hash=None,
            after_hash=entry.sha256,
            before_size=None,
            after_size=entry.size,
            diff_lines=None,
        ))

    # Find deleted files (in before but not after)
    for path in sorted(before_paths - after_paths):
        entry = before_map[path]
        deleted.append(FileChange(
            path=path,
            change_type="deleted",
            before_hash=entry.sha256,
            after_hash=None,
            before_size=entry.size,
            after_size=None,
            diff_lines=None,
        ))

    # Find modified files (in both, hash differs)
    for path in sorted(before_paths & after_paths):
        before_entry = before_map[path]
        after_entry = after_map[path]

        if before_entry.sha256 == after_entry.sha256:
            unchanged_count += 1
            continue

        # Compute diff for text files
        diff_lines: list[str] | None = None
        if include_diff:
            if before_entry.type == "text" and after_entry.type == "text":
                if before_entry.content and after_entry.content:
                    if before_entry.size <= max_diff_size and after_entry.size <= max_diff_size:
                        diff_lines = compute_file_diff(
                            before_entry.content,
                            after_entry.content,
                            path,
                        )
                    else:
                        diff_lines = ["(diff skipped: file too large)"]
            elif before_entry.type == "binary" or after_entry.type == "binary":
                diff_lines = ["(binary file changed)"]

        modified.append(FileChange(
            path=path,
            change_type="modified",
            before_hash=before_entry.sha256,
            after_hash=after_entry.sha256,
            before_size=before_entry.size,
            after_size=after_entry.size,
            diff_lines=diff_lines,
        ))

    return DiffResult(
        before_timestamp=before.timestamp,
        after_timestamp=after.timestamp,
        added=added,
        modified=modified,
        deleted=deleted,
        unchanged_count=unchanged_count,
    )


# -----------------------------------------------------------------------------
# Storage Integration
# -----------------------------------------------------------------------------


def save_manifest_to_storage(
    storage: PhaserStorage,
    manifest: Manifest,
    audit_id: str,
    stage: str,
) -> Path:
    """
    Save manifest to .phaser/manifests/ directory.

    Args:
        storage: PhaserStorage instance
        manifest: Manifest to save
        audit_id: Audit identifier
        stage: "pre" or "post"

    Returns:
        Path where manifest was saved
    """
    storage.ensure_directories()
    manifest_path = storage.get_path(f"manifests/{audit_id}-{stage}.yaml")
    manifest.save(manifest_path)
    return manifest_path


def load_manifests_for_audit(
    storage: PhaserStorage,
    audit_id: str,
) -> tuple[Manifest | None, Manifest | None]:
    """
    Load pre and post manifests for an audit.

    Args:
        storage: PhaserStorage instance
        audit_id: Audit identifier

    Returns:
        (pre_manifest, post_manifest) - either may be None if not found
    """
    pre_path = storage.get_path(f"manifests/{audit_id}-pre.yaml")
    post_path = storage.get_path(f"manifests/{audit_id}-post.yaml")

    pre: Manifest | None = None
    post: Manifest | None = None

    if pre_path.exists():
        pre = Manifest.load(pre_path)

    if post_path.exists():
        post = Manifest.load(post_path)

    return pre, post


# -----------------------------------------------------------------------------
# CLI Interface
# -----------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Phaser diff engine - capture and compare directory manifests."""
    pass


@cli.command()
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file (default: stdout)")
@click.option("--exclude", multiple=True, help="Patterns to exclude (can repeat)")
def capture(root: Path, output: Path | None, exclude: tuple[str, ...]) -> None:
    """Capture manifest of directory."""
    patterns = list(exclude) if exclude else None
    manifest = capture_manifest(root, exclude_patterns=patterns)

    if output:
        manifest.save(output)
        click.echo(f"Saved manifest: {manifest.file_count} files, {manifest.total_size_bytes:,} bytes")
    else:
        click.echo(yaml.dump(manifest.to_dict(), default_flow_style=False))


@cli.command()
@click.argument("before", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("after", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "summary", "detailed"]),
    default="summary",
    help="Output format",
)
@click.option("--no-diff", is_flag=True, help="Skip unified diff computation")
def compare(before: Path, after: Path, output_format: str, no_diff: bool) -> None:
    """Compare two manifests."""
    before_manifest = Manifest.load(before)
    after_manifest = Manifest.load(after)

    result = compare_manifests(before_manifest, after_manifest, include_diff=not no_diff)

    if output_format == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
    elif output_format == "summary":
        click.echo(result.summary())
    else:  # detailed
        click.echo(result.detailed())


if __name__ == "__main__":
    cli()
