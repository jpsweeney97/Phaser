"""
Phaser Audit Lifecycle Hooks

Integrates diff capture into the audit lifecycle.
Called during audit setup and completion to capture manifests and compute changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tools.diff import (
    DiffResult,
    Manifest,
    capture_manifest,
    compare_manifests,
    load_manifests_for_audit,
    save_manifest_to_storage,
)
from tools.events import EventEmitter, EventType

if TYPE_CHECKING:
    from tools.storage import PhaserStorage


# Default patterns to exclude from manifest capture during audits
AUDIT_EXCLUDE_PATTERNS = [
    ".audit",
    ".git",
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


def on_audit_setup(
    project_root: Path,
    audit_id: str,
    storage: PhaserStorage,
    emitter: EventEmitter,
) -> Manifest:
    """
    Called when audit is set up. Captures pre-audit manifest.

    Args:
        project_root: Root directory of the project being audited
        audit_id: Unique identifier for the audit
        storage: PhaserStorage instance for persistence
        emitter: EventEmitter for publishing events

    Returns:
        The captured pre-audit Manifest
    """
    manifest = capture_manifest(project_root, exclude_patterns=AUDIT_EXCLUDE_PATTERNS)
    manifest_path = save_manifest_to_storage(storage, manifest, audit_id, "pre")

    emitter.emit(
        EventType.FILE_CREATED,
        audit_id=audit_id,
        path=str(manifest_path),
        file_count=manifest.file_count,
        total_size_bytes=manifest.total_size_bytes,
    )

    return manifest


def on_audit_complete(
    project_root: Path,
    audit_id: str,
    storage: PhaserStorage,
    emitter: EventEmitter,
) -> DiffResult | None:
    """
    Called when audit completes. Captures post-audit manifest and computes diff.

    Args:
        project_root: Root directory of the project being audited
        audit_id: Unique identifier for the audit
        storage: PhaserStorage instance for persistence
        emitter: EventEmitter for publishing events

    Returns:
        DiffResult if both manifests exist, None otherwise
    """
    # Capture post-audit manifest
    manifest = capture_manifest(project_root, exclude_patterns=AUDIT_EXCLUDE_PATTERNS)
    manifest_path = save_manifest_to_storage(storage, manifest, audit_id, "post")

    emitter.emit(
        EventType.FILE_CREATED,
        audit_id=audit_id,
        path=str(manifest_path),
        file_count=manifest.file_count,
        total_size_bytes=manifest.total_size_bytes,
    )

    # Load both manifests and compare
    pre, post = load_manifests_for_audit(storage, audit_id)
    if pre is None or post is None:
        return None

    diff = compare_manifests(pre, post)

    # Emit events for each change
    for change in diff.added:
        emitter.emit(
            EventType.FILE_CREATED,
            audit_id=audit_id,
            path=change.path,
            size=change.after_size,
        )

    for change in diff.modified:
        emitter.emit(
            EventType.FILE_MODIFIED,
            audit_id=audit_id,
            path=change.path,
            before_size=change.before_size,
            after_size=change.after_size,
        )

    for change in diff.deleted:
        emitter.emit(
            EventType.FILE_DELETED,
            audit_id=audit_id,
            path=change.path,
        )

    return diff


def get_audit_diff_summary(
    audit_id: str,
    storage: PhaserStorage,
) -> str:
    """
    Get human-readable diff summary for an audit.

    Args:
        audit_id: Unique identifier for the audit
        storage: PhaserStorage instance

    Returns:
        Summary string (e.g., "+3 added, ~12 modified, -1 deleted")
    """
    pre, post = load_manifests_for_audit(storage, audit_id)
    if pre is None or post is None:
        return "No diff available (missing manifests)"

    diff = compare_manifests(pre, post, include_diff=False)
    return diff.summary()


def get_audit_diff_detailed(
    audit_id: str,
    storage: PhaserStorage,
) -> str:
    """
    Get detailed diff output for an audit.

    Args:
        audit_id: Unique identifier for the audit
        storage: PhaserStorage instance

    Returns:
        Detailed diff string with unified diff for each file
    """
    pre, post = load_manifests_for_audit(storage, audit_id)
    if pre is None or post is None:
        return "No diff available (missing manifests)"

    diff = compare_manifests(pre, post, include_diff=True)
    return diff.detailed()
