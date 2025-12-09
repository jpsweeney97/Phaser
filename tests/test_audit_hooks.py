"""Tests for the Phaser audit lifecycle hooks."""

from pathlib import Path
import tempfile
import shutil

import pytest

from tools.audit_hooks import (
    AUDIT_EXCLUDE_PATTERNS,
    get_audit_diff_detailed,
    get_audit_diff_summary,
    on_audit_complete,
    on_audit_setup,
)
from tools.events import Event, EventEmitter, EventType
from tools.storage import PhaserStorage


@pytest.fixture
def isolated_storage() -> PhaserStorage:
    """Create storage in a separate directory from project."""
    d = Path(tempfile.mkdtemp())
    yield PhaserStorage(root=d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def isolated_emitter(isolated_storage: PhaserStorage) -> EventEmitter:
    """EventEmitter using isolated storage."""
    return EventEmitter(storage=isolated_storage)


@pytest.fixture
def project_dir() -> Path:
    """Create a separate project directory for auditing."""
    d = Path(tempfile.mkdtemp())
    (d / "src").mkdir()
    (d / "src" / "main.py").write_text("print('hello')")
    (d / "README.md").write_text("# Test Project")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestAuditExcludePatterns:
    """Tests for default exclude patterns."""

    def test_contains_expected_patterns(self) -> None:
        """Verify standard patterns are excluded."""
        assert ".git" in AUDIT_EXCLUDE_PATTERNS
        assert ".audit" in AUDIT_EXCLUDE_PATTERNS
        assert ".phaser" in AUDIT_EXCLUDE_PATTERNS
        assert "__pycache__" in AUDIT_EXCLUDE_PATTERNS
        assert "node_modules" in AUDIT_EXCLUDE_PATTERNS

    def test_excludes_virtual_environments(self) -> None:
        """Verify venv directories are excluded."""
        assert ".venv" in AUDIT_EXCLUDE_PATTERNS
        assert "venv" in AUDIT_EXCLUDE_PATTERNS


class TestOnAuditSetup:
    """Tests for on_audit_setup function."""

    def test_captures_manifest(
        self, sample_project: Path, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Verify manifest is captured from project root."""
        manifest = on_audit_setup(sample_project, "test-audit-1", storage, emitter)

        assert manifest is not None
        assert manifest.file_count > 0
        assert manifest.root == str(sample_project.resolve())

    def test_saves_manifest_to_storage(
        self, sample_project: Path, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Verify manifest is persisted to .phaser/manifests/{audit_id}-pre.yaml."""
        on_audit_setup(sample_project, "test-audit-2", storage, emitter)

        pre_manifest = storage.get_path("manifests/test-audit-2-pre.yaml")

        assert pre_manifest.exists()

    def test_emits_file_created_event(
        self, sample_project: Path, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Verify FILE_CREATED event is emitted with file count."""
        events_received: list[Event] = []
        emitter.subscribe(lambda e: events_received.append(e))

        manifest = on_audit_setup(sample_project, "test-audit-3", storage, emitter)

        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.FILE_CREATED
        assert event.audit_id == "test-audit-3"
        assert event.data["file_count"] == manifest.file_count

    def test_excludes_audit_patterns(
        self, temp_dir: Path, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Verify .audit, .git, __pycache__ are excluded from manifest."""
        # Create project with excluded directories
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "main.py").write_text("print('hello')")
        (temp_dir / ".git").mkdir()
        (temp_dir / ".git" / "config").write_text("git config")
        (temp_dir / "__pycache__").mkdir()
        (temp_dir / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"\x00\x00")
        (temp_dir / ".audit").mkdir()
        (temp_dir / ".audit" / "CONTEXT.md").write_text("# Audit")

        manifest = on_audit_setup(temp_dir, "test-audit-4", storage, emitter)

        # Only src/main.py should be included
        paths = [f.path for f in manifest.files]
        assert "src/main.py" in paths
        assert not any(".git" in p for p in paths)
        assert not any("__pycache__" in p for p in paths)
        assert not any(".audit" in p for p in paths)


class TestOnAuditComplete:
    """Tests for on_audit_complete function."""

    def test_captures_post_manifest(
        self, project_dir: Path, isolated_storage: PhaserStorage, isolated_emitter: EventEmitter
    ) -> None:
        """Verify post-audit manifest is captured."""
        # Setup first
        on_audit_setup(project_dir, "test-audit-5", isolated_storage, isolated_emitter)

        # Complete
        diff = on_audit_complete(project_dir, "test-audit-5", isolated_storage, isolated_emitter)

        # Check post manifest exists
        post_manifest = isolated_storage.get_path("manifests/test-audit-5-post.yaml")
        assert post_manifest.exists()

        # No changes, so diff should be empty
        assert diff is not None
        assert len(diff.added) == 0
        assert len(diff.modified) == 0
        assert len(diff.deleted) == 0

    def test_computes_diff_with_changes(
        self, project_dir: Path, isolated_storage: PhaserStorage, isolated_emitter: EventEmitter
    ) -> None:
        """Verify diff is computed between pre and post manifests."""
        # Setup
        on_audit_setup(project_dir, "test-audit-6", isolated_storage, isolated_emitter)

        # Make changes
        (project_dir / "new_file.py").write_text("# New file")
        (project_dir / "src" / "main.py").write_text("print('modified')")

        # Complete
        diff = on_audit_complete(project_dir, "test-audit-6", isolated_storage, isolated_emitter)

        assert diff is not None
        assert len(diff.added) == 1
        assert diff.added[0].path == "new_file.py"
        assert len(diff.modified) == 1
        assert diff.modified[0].path == "src/main.py"

    def test_emits_file_change_events(
        self, sample_project: Path, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Verify FILE_CREATED/MODIFIED/DELETED events are emitted for changes."""
        # Setup
        on_audit_setup(sample_project, "test-audit-7", storage, emitter)

        # Track events after setup
        events_received: list[Event] = []
        emitter.subscribe(lambda e: events_received.append(e))

        # Make changes
        (sample_project / "added.py").write_text("# Added")
        (sample_project / "src" / "main.py").write_text("print('modified')")
        (sample_project / "README.md").unlink()

        # Complete
        on_audit_complete(sample_project, "test-audit-7", storage, emitter)

        # Filter out the manifest FILE_CREATED event
        change_events = [
            e for e in events_received
            if "manifests" not in e.data.get("path", "")
        ]

        event_types = [e.type for e in change_events]
        assert EventType.FILE_CREATED in event_types
        assert EventType.FILE_MODIFIED in event_types
        assert EventType.FILE_DELETED in event_types

    def test_returns_none_if_pre_missing(
        self, sample_project: Path, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Verify None returned when pre-manifest is missing."""
        # Skip setup, go straight to complete
        diff = on_audit_complete(sample_project, "no-setup-audit", storage, emitter)

        assert diff is None


class TestGetAuditDiffSummary:
    """Tests for get_audit_diff_summary function."""

    def test_returns_summary_string(
        self, project_dir: Path, isolated_storage: PhaserStorage, isolated_emitter: EventEmitter
    ) -> None:
        """Verify summary format: '+N added, ~N modified, -N deleted'."""
        # Setup and make changes
        on_audit_setup(project_dir, "test-audit-8", isolated_storage, isolated_emitter)
        (project_dir / "new.py").write_text("# New")
        on_audit_complete(project_dir, "test-audit-8", isolated_storage, isolated_emitter)

        summary = get_audit_diff_summary("test-audit-8", isolated_storage)

        assert "+1 added" in summary or "1 added" in summary

    def test_returns_message_when_manifests_missing(
        self, storage: PhaserStorage
    ) -> None:
        """Verify message when manifests are unavailable."""
        summary = get_audit_diff_summary("nonexistent-audit", storage)

        assert "No diff available" in summary
        assert "missing manifests" in summary


class TestGetAuditDiffDetailed:
    """Tests for get_audit_diff_detailed function."""

    def test_returns_detailed_diff(
        self, sample_project: Path, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Verify detailed diff includes file paths and changes."""
        # Setup and make changes
        on_audit_setup(sample_project, "test-audit-9", storage, emitter)
        (sample_project / "src" / "main.py").write_text("print('changed line')")
        on_audit_complete(sample_project, "test-audit-9", storage, emitter)

        detailed = get_audit_diff_detailed("test-audit-9", storage)

        assert "Modified:" in detailed or "src/main.py" in detailed

    def test_returns_message_when_manifests_missing(
        self, storage: PhaserStorage
    ) -> None:
        """Verify message when manifests are unavailable."""
        detailed = get_audit_diff_detailed("nonexistent-audit", storage)

        assert "No diff available" in detailed
        assert "missing manifests" in detailed
