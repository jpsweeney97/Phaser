"""Tests for tools/diff.py — Manifest capture and comparison."""

import tempfile
from pathlib import Path

import pytest

from tools.diff import (
    DiffResult,
    FileChange,
    FileEntry,
    Manifest,
    capture_manifest,
    compare_manifests,
    compute_file_diff,
    load_manifests_for_audit,
    save_manifest_to_storage,
)


# -----------------------------------------------------------------------------
# FileEntry Tests
# -----------------------------------------------------------------------------


def test_file_entry_creation() -> None:
    """FileEntry can be created with all fields."""
    entry = FileEntry(
        path="src/main.py",
        type="text",
        size=100,
        sha256="abc123",
        content="print('hello')",
        is_executable=False,
    )
    assert entry.path == "src/main.py"
    assert entry.type == "text"
    assert entry.size == 100
    assert entry.sha256 == "abc123"
    assert entry.content == "print('hello')"
    assert entry.is_executable is False


def test_file_entry_to_dict() -> None:
    """FileEntry serializes to dictionary."""
    entry = FileEntry(
        path="test.py",
        type="text",
        size=50,
        sha256="def456",
        content="# test",
        is_executable=True,
    )
    d = entry.to_dict()
    assert d["path"] == "test.py"
    assert d["type"] == "text"
    assert d["size"] == 50
    assert d["sha256"] == "def456"
    assert d["content"] == "# test"
    assert d["is_executable"] is True


def test_file_entry_from_dict() -> None:
    """FileEntry deserializes from dictionary."""
    d = {
        "path": "lib.py",
        "type": "text",
        "size": 200,
        "sha256": "ghi789",
        "content": "def foo(): pass",
        "is_executable": False,
    }
    entry = FileEntry.from_dict(d)
    assert entry.path == "lib.py"
    assert entry.size == 200
    assert entry.content == "def foo(): pass"


def test_file_entry_binary_no_content() -> None:
    """Binary FileEntry has None content."""
    entry = FileEntry(
        path="image.png",
        type="binary",
        size=1024,
        sha256="xyz",
        content=None,
        is_executable=False,
    )
    assert entry.type == "binary"
    assert entry.content is None


# -----------------------------------------------------------------------------
# Manifest Tests
# -----------------------------------------------------------------------------


def test_manifest_creation() -> None:
    """Manifest can be created with files."""
    files = [
        FileEntry("a.py", "text", 10, "hash1", "# a", False),
        FileEntry("b.py", "text", 20, "hash2", "# b", False),
    ]
    manifest = Manifest(
        root="/project",
        timestamp="2025-12-05T10:00:00Z",
        file_count=2,
        total_size_bytes=30,
        files=files,
    )
    assert manifest.root == "/project"
    assert manifest.file_count == 2
    assert len(manifest.files) == 2


def test_manifest_to_dict() -> None:
    """Manifest serializes to dictionary."""
    manifest = Manifest(
        root="/test",
        timestamp="2025-01-01T00:00:00Z",
        file_count=1,
        total_size_bytes=100,
        files=[FileEntry("x.py", "text", 100, "h", "code", False)],
    )
    d = manifest.to_dict()
    assert d["root"] == "/test"
    assert d["file_count"] == 1
    assert len(d["files"]) == 1


def test_manifest_from_dict() -> None:
    """Manifest deserializes from dictionary."""
    d = {
        "root": "/proj",
        "timestamp": "2025-06-01T12:00:00Z",
        "file_count": 1,
        "total_size_bytes": 50,
        "files": [
            {"path": "f.py", "type": "text", "size": 50, "sha256": "h", "content": "", "is_executable": False}
        ],
    }
    manifest = Manifest.from_dict(d)
    assert manifest.root == "/proj"
    assert manifest.file_count == 1
    assert manifest.files[0].path == "f.py"


def test_manifest_save_load_roundtrip(temp_dir: Path) -> None:
    """Manifest can be saved and loaded."""
    manifest = Manifest(
        root=str(temp_dir),
        timestamp="2025-12-05T10:00:00Z",
        file_count=1,
        total_size_bytes=10,
        files=[FileEntry("test.txt", "text", 10, "abc", "hello", False)],
    )

    path = temp_dir / "manifest.yaml"
    manifest.save(path)

    loaded = Manifest.load(path)
    assert loaded.root == manifest.root
    assert loaded.file_count == 1
    assert loaded.files[0].path == "test.txt"
    assert loaded.files[0].content == "hello"


# -----------------------------------------------------------------------------
# Capture Tests
# -----------------------------------------------------------------------------


def test_capture_manifest_empty_dir(temp_dir: Path) -> None:
    """Capture empty directory returns empty manifest."""
    manifest = capture_manifest(temp_dir)
    assert manifest.file_count == 0
    assert manifest.total_size_bytes == 0
    assert len(manifest.files) == 0


def test_capture_manifest_with_files(temp_dir: Path) -> None:
    """Capture directory with files."""
    (temp_dir / "hello.txt").write_text("Hello, World!")
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text("print('hi')")

    manifest = capture_manifest(temp_dir)
    assert manifest.file_count == 2
    paths = {f.path for f in manifest.files}
    assert "hello.txt" in paths
    assert "src/main.py" in paths


def test_capture_manifest_excludes_patterns(temp_dir: Path) -> None:
    """Capture respects exclude patterns."""
    (temp_dir / "keep.txt").write_text("keep")
    (temp_dir / "skip").mkdir()
    (temp_dir / "skip" / "hidden.txt").write_text("skip")

    manifest = capture_manifest(temp_dir, exclude_patterns=["skip"])
    assert manifest.file_count == 1
    assert manifest.files[0].path == "keep.txt"


def test_capture_manifest_handles_binary(temp_dir: Path) -> None:
    """Capture detects binary files."""
    (temp_dir / "text.txt").write_text("text content")
    (temp_dir / "binary.bin").write_bytes(b"\x00\x01\x02\x03")

    manifest = capture_manifest(temp_dir)
    assert manifest.file_count == 2

    by_path = {f.path: f for f in manifest.files}
    assert by_path["text.txt"].type == "text"
    assert by_path["text.txt"].content == "text content"
    assert by_path["binary.bin"].type == "binary"
    assert by_path["binary.bin"].content is None


def test_capture_manifest_computes_hash(temp_dir: Path) -> None:
    """Capture computes SHA256 hash."""
    (temp_dir / "file.txt").write_text("test content")
    manifest = capture_manifest(temp_dir)

    assert len(manifest.files) == 1
    assert len(manifest.files[0].sha256) == 64  # SHA256 hex length


# -----------------------------------------------------------------------------
# Compare Tests
# -----------------------------------------------------------------------------


def test_compare_identical_manifests() -> None:
    """Comparing identical manifests shows no changes."""
    files = [FileEntry("a.py", "text", 10, "hash1", "code", False)]
    before = Manifest("/proj", "2025-01-01T00:00:00Z", 1, 10, files)
    after = Manifest("/proj", "2025-01-01T01:00:00Z", 1, 10, files.copy())

    result = compare_manifests(before, after)
    assert len(result.added) == 0
    assert len(result.modified) == 0
    assert len(result.deleted) == 0
    assert result.unchanged_count == 1


def test_compare_added_files() -> None:
    """Detect added files."""
    before = Manifest("/proj", "t1", 0, 0, [])
    after = Manifest("/proj", "t2", 1, 10, [
        FileEntry("new.py", "text", 10, "hash", "code", False)
    ])

    result = compare_manifests(before, after)
    assert len(result.added) == 1
    assert result.added[0].path == "new.py"
    assert result.added[0].change_type == "added"


def test_compare_modified_files() -> None:
    """Detect modified files."""
    before = Manifest("/proj", "t1", 1, 10, [
        FileEntry("file.py", "text", 10, "hash1", "old", False)
    ])
    after = Manifest("/proj", "t2", 1, 15, [
        FileEntry("file.py", "text", 15, "hash2", "new content", False)
    ])

    result = compare_manifests(before, after)
    assert len(result.modified) == 1
    assert result.modified[0].path == "file.py"
    assert result.modified[0].before_hash == "hash1"
    assert result.modified[0].after_hash == "hash2"


def test_compare_deleted_files() -> None:
    """Detect deleted files."""
    before = Manifest("/proj", "t1", 1, 10, [
        FileEntry("old.py", "text", 10, "hash", "code", False)
    ])
    after = Manifest("/proj", "t2", 0, 0, [])

    result = compare_manifests(before, after)
    assert len(result.deleted) == 1
    assert result.deleted[0].path == "old.py"
    assert result.deleted[0].change_type == "deleted"


def test_compare_mixed_changes() -> None:
    """Detect mixed add/modify/delete."""
    before = Manifest("/proj", "t1", 2, 20, [
        FileEntry("keep.py", "text", 10, "same", "keep", False),
        FileEntry("modify.py", "text", 10, "old", "old", False),
        FileEntry("delete.py", "text", 10, "del", "del", False),
    ])
    after = Manifest("/proj", "t2", 3, 30, [
        FileEntry("keep.py", "text", 10, "same", "keep", False),
        FileEntry("modify.py", "text", 15, "new", "new content", False),
        FileEntry("add.py", "text", 10, "add", "added", False),
    ])

    result = compare_manifests(before, after)
    assert len(result.added) == 1
    assert len(result.modified) == 1
    assert len(result.deleted) == 1
    assert result.unchanged_count == 1


def test_compare_binary_files_no_diff() -> None:
    """Binary files don't have content diff."""
    before = Manifest("/proj", "t1", 1, 100, [
        FileEntry("img.png", "binary", 100, "hash1", None, False)
    ])
    after = Manifest("/proj", "t2", 1, 150, [
        FileEntry("img.png", "binary", 150, "hash2", None, False)
    ])

    result = compare_manifests(before, after)
    assert len(result.modified) == 1
    assert result.modified[0].diff_lines == ["(binary file changed)"]


# -----------------------------------------------------------------------------
# Diff Output Tests
# -----------------------------------------------------------------------------


def test_diff_result_summary() -> None:
    """DiffResult summary format."""
    result = DiffResult(
        before_timestamp="t1",
        after_timestamp="t2",
        added=[FileChange("a.py", "added", None, "h", None, 10, None)],
        modified=[
            FileChange("b.py", "modified", "h1", "h2", 10, 20, None),
            FileChange("c.py", "modified", "h3", "h4", 15, 25, None),
        ],
        deleted=[],
        unchanged_count=5,
    )
    summary = result.summary()
    assert "+1 added" in summary
    assert "~2 modified" in summary
    assert "deleted" not in summary


def test_diff_result_summary_no_changes() -> None:
    """DiffResult summary when nothing changed."""
    result = DiffResult("t1", "t2", [], [], [], 10)
    assert result.summary() == "No changes"


def test_diff_result_detailed() -> None:
    """DiffResult detailed output."""
    result = DiffResult(
        before_timestamp="t1",
        after_timestamp="t2",
        added=[FileChange("new.py", "added", None, "h", None, 10, None)],
        modified=[FileChange("mod.py", "modified", "h1", "h2", 10, 20, ["--- a/mod.py", "+++ b/mod.py"])],
        deleted=[FileChange("old.py", "deleted", "h", None, 10, None, None)],
        unchanged_count=0,
    )
    detailed = result.detailed()
    assert "Added: new.py" in detailed
    assert "Modified: mod.py" in detailed
    assert "Deleted: old.py" in detailed


def test_diff_result_to_dict() -> None:
    """DiffResult serializes to dict."""
    result = DiffResult("t1", "t2", [], [], [], 5)
    d = result.to_dict()
    assert d["before_timestamp"] == "t1"
    assert d["after_timestamp"] == "t2"
    assert d["unchanged_count"] == 5


# -----------------------------------------------------------------------------
# compute_file_diff Tests
# -----------------------------------------------------------------------------


def test_compute_file_diff_basic() -> None:
    """Compute unified diff between two strings."""
    before = "line1\nline2\nline3\n"
    after = "line1\nmodified\nline3\n"

    diff = compute_file_diff(before, after, "test.py")
    assert any("---" in line for line in diff)
    assert any("+++" in line for line in diff)
    assert any("-line2" in line for line in diff)
    assert any("+modified" in line for line in diff)


def test_compute_file_diff_no_changes() -> None:
    """Diff of identical content is empty."""
    content = "same content\n"
    diff = compute_file_diff(content, content, "file.py")
    assert diff == []


# -----------------------------------------------------------------------------
# Storage Integration Tests
# -----------------------------------------------------------------------------


def test_save_manifest_to_storage(storage) -> None:
    """Save manifest to storage."""
    from tools.diff import save_manifest_to_storage

    manifest = Manifest(
        root="/test",
        timestamp="2025-12-05T10:00:00Z",
        file_count=0,
        total_size_bytes=0,
        files=[],
    )

    path = save_manifest_to_storage(storage, manifest, "audit-123", "pre")
    assert path.exists()
    assert "audit-123-pre.yaml" in str(path)


def test_load_manifests_for_audit(storage, temp_dir: Path) -> None:
    """Load pre and post manifests for an audit."""
    from tools.diff import save_manifest_to_storage, load_manifests_for_audit

    pre = Manifest(str(temp_dir), "t1", 0, 0, [])
    post = Manifest(str(temp_dir), "t2", 1, 10, [
        FileEntry("new.py", "text", 10, "h", "code", False)
    ])

    save_manifest_to_storage(storage, pre, "test-audit", "pre")
    save_manifest_to_storage(storage, post, "test-audit", "post")

    loaded_pre, loaded_post = load_manifests_for_audit(storage, "test-audit")
    assert loaded_pre is not None
    assert loaded_post is not None
    assert loaded_pre.file_count == 0
    assert loaded_post.file_count == 1


def test_load_manifests_missing(storage) -> None:
    """Load returns None for missing manifests."""
    pre, post = load_manifests_for_audit(storage, "nonexistent")
    assert pre is None
    assert post is None
