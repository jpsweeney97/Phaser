"""Tests for the Phaser storage layer."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.storage import PhaserStorage, DEFAULT_CONFIG


class TestStorageInit:
    """Tests for storage initialization."""

    def test_storage_init_creates_directories(self, storage: PhaserStorage) -> None:
        """Verify .phaser/ directory structure is created."""
        storage.ensure_directories()

        assert storage.root.exists()
        assert (storage.root / "manifests").exists()

    def test_storage_init_with_custom_root(self, temp_dir: Path) -> None:
        """Verify custom root path is used."""
        custom_root = temp_dir / "custom"
        s = PhaserStorage(root=custom_root)

        assert s.root == custom_root

    def test_get_path_resolves_within_root(self, storage: PhaserStorage) -> None:
        """Verify get_path returns paths within .phaser/."""
        path = storage.get_path("audits.json")

        assert path == storage.root / "audits.json"


class TestAuditOperations:
    """Tests for audit CRUD operations."""

    def test_save_and_get_audit(self, storage: PhaserStorage) -> None:
        """Verify audit round-trip save and retrieve."""
        audit = {
            "project": "TestProject",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "in_progress",
        }

        audit_id = storage.save_audit(audit)
        retrieved = storage.get_audit(audit_id)

        assert retrieved is not None
        assert retrieved["project"] == "TestProject"
        assert retrieved["slug"] == "test-audit"
        assert retrieved["id"] == audit_id

    def test_save_audit_generates_id(self, storage: PhaserStorage) -> None:
        """Verify ID is generated when not provided."""
        audit = {
            "project": "TestProject",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "pending",
        }

        audit_id = storage.save_audit(audit)

        assert audit_id is not None
        assert len(audit_id) == 36  # UUID format

    def test_save_audit_preserves_provided_id(self, storage: PhaserStorage) -> None:
        """Verify provided ID is preserved."""
        audit = {
            "id": "custom-id-123",
            "project": "TestProject",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "pending",
        }

        audit_id = storage.save_audit(audit)

        assert audit_id == "custom-id-123"

    def test_save_audit_validates_required_fields(self, storage: PhaserStorage) -> None:
        """Verify validation of required fields."""
        audit = {"project": "TestProject"}  # Missing required fields

        with pytest.raises(ValueError, match="Missing required audit fields"):
            storage.save_audit(audit)

    def test_list_audits_empty(self, storage: PhaserStorage) -> None:
        """Verify empty list when no audits exist."""
        audits = storage.list_audits()

        assert audits == []

    def test_list_audits_with_data(self, storage: PhaserStorage) -> None:
        """Verify all audits are returned."""
        storage.save_audit({
            "project": "Project1",
            "slug": "audit-1",
            "date": "2025-12-05",
            "status": "completed",
        })
        storage.save_audit({
            "project": "Project2",
            "slug": "audit-2",
            "date": "2025-12-05",
            "status": "pending",
        })

        audits = storage.list_audits()

        assert len(audits) == 2

    def test_list_audits_filtered_by_project(self, storage: PhaserStorage) -> None:
        """Verify filtering by project name."""
        storage.save_audit({
            "project": "Project1",
            "slug": "audit-1",
            "date": "2025-12-05",
            "status": "completed",
        })
        storage.save_audit({
            "project": "Project2",
            "slug": "audit-2",
            "date": "2025-12-05",
            "status": "pending",
        })

        audits = storage.list_audits(project="Project1")

        assert len(audits) == 1
        assert audits[0]["project"] == "Project1"

    def test_update_audit(self, storage: PhaserStorage) -> None:
        """Verify audit updates are persisted."""
        audit_id = storage.save_audit({
            "project": "TestProject",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "pending",
        })

        result = storage.update_audit(audit_id, {"status": "completed"})
        updated = storage.get_audit(audit_id)

        assert result is True
        assert updated is not None
        assert updated["status"] == "completed"

    def test_update_nonexistent_audit(self, storage: PhaserStorage) -> None:
        """Verify False returned for nonexistent audit."""
        result = storage.update_audit("nonexistent-id", {"status": "completed"})

        assert result is False

    def test_get_nonexistent_audit(self, storage: PhaserStorage) -> None:
        """Verify None returned for nonexistent audit."""
        result = storage.get_audit("nonexistent-id")

        assert result is None


class TestEventOperations:
    """Tests for event operations."""

    def test_append_and_get_events(self, storage: PhaserStorage) -> None:
        """Verify event round-trip append and retrieve."""
        event = {
            "id": "event-1",
            "type": "phase_completed",
            "timestamp": "2025-12-05T10:00:00.000Z",
            "audit_id": "audit-1",
            "phase": 1,
            "data": {"duration": 45.0},
        }

        storage.append_event(event)
        events = storage.get_events()

        assert len(events) == 1
        assert events[0]["id"] == "event-1"
        assert events[0]["type"] == "phase_completed"

    def test_append_event_validates_required_fields(self, storage: PhaserStorage) -> None:
        """Verify validation of required event fields."""
        event = {"id": "event-1"}  # Missing required fields

        with pytest.raises(ValueError, match="Missing required event fields"):
            storage.append_event(event)

    def test_get_events_filtered_by_audit(self, storage: PhaserStorage) -> None:
        """Verify filtering by audit_id."""
        storage.append_event({
            "id": "event-1",
            "type": "phase_started",
            "timestamp": "2025-12-05T10:00:00.000Z",
            "audit_id": "audit-1",
        })
        storage.append_event({
            "id": "event-2",
            "type": "phase_started",
            "timestamp": "2025-12-05T10:01:00.000Z",
            "audit_id": "audit-2",
        })

        events = storage.get_events(audit_id="audit-1")

        assert len(events) == 1
        assert events[0]["audit_id"] == "audit-1"

    def test_get_events_filtered_by_type(self, storage: PhaserStorage) -> None:
        """Verify filtering by event type."""
        storage.append_event({
            "id": "event-1",
            "type": "phase_started",
            "timestamp": "2025-12-05T10:00:00.000Z",
            "audit_id": "audit-1",
        })
        storage.append_event({
            "id": "event-2",
            "type": "phase_completed",
            "timestamp": "2025-12-05T10:01:00.000Z",
            "audit_id": "audit-1",
        })

        events = storage.get_events(event_type="phase_completed")

        assert len(events) == 1
        assert events[0]["type"] == "phase_completed"

    def test_get_events_sorted_by_timestamp(self, storage: PhaserStorage) -> None:
        """Verify events are sorted chronologically."""
        storage.append_event({
            "id": "event-2",
            "type": "phase_completed",
            "timestamp": "2025-12-05T10:01:00.000Z",
            "audit_id": "audit-1",
        })
        storage.append_event({
            "id": "event-1",
            "type": "phase_started",
            "timestamp": "2025-12-05T10:00:00.000Z",
            "audit_id": "audit-1",
        })

        events = storage.get_events()

        assert events[0]["id"] == "event-1"
        assert events[1]["id"] == "event-2"

    def test_clear_events(self, storage: PhaserStorage) -> None:
        """Verify all events are cleared."""
        storage.append_event({
            "id": "event-1",
            "type": "phase_started",
            "timestamp": "2025-12-05T10:00:00.000Z",
            "audit_id": "audit-1",
        })

        removed = storage.clear_events()
        events = storage.get_events()

        assert removed == 1
        assert events == []

    def test_clear_events_before_date(self, storage: PhaserStorage) -> None:
        """Verify only old events are cleared."""
        storage.append_event({
            "id": "event-1",
            "type": "phase_started",
            "timestamp": "2025-12-04T10:00:00.000Z",
            "audit_id": "audit-1",
        })
        storage.append_event({
            "id": "event-2",
            "type": "phase_completed",
            "timestamp": "2025-12-06T10:00:00.000Z",
            "audit_id": "audit-1",
        })

        cutoff = datetime(2025, 12, 5, tzinfo=timezone.utc)
        removed = storage.clear_events(before=cutoff)
        events = storage.get_events()

        assert removed == 1
        assert len(events) == 1
        assert events[0]["id"] == "event-2"


class TestConfigOperations:
    """Tests for configuration operations."""

    def test_config_defaults(self, storage: PhaserStorage) -> None:
        """Verify default config is returned when no file exists."""
        config = storage.get_config()

        assert config["version"] == 1
        assert config["storage"]["location"] == "global"
        assert config["storage"]["max_events"] == 10000

    def test_config_set_and_get(self, storage: PhaserStorage) -> None:
        """Verify config values can be set and retrieved."""
        storage.set_config("storage.max_events", 5000)
        config = storage.get_config()

        assert config["storage"]["max_events"] == 5000

    def test_config_set_nested_key(self, storage: PhaserStorage) -> None:
        """Verify dot-notation works for nested keys."""
        storage.set_config("features.diffs", False)
        config = storage.get_config()

        assert config["features"]["diffs"] is False

    def test_config_reset(self, storage: PhaserStorage) -> None:
        """Verify config resets to defaults."""
        storage.set_config("storage.max_events", 5000)
        storage.reset_config()
        config = storage.get_config()

        assert config["storage"]["max_events"] == DEFAULT_CONFIG["storage"]["max_events"]

    def test_config_preserves_defaults(self, storage: PhaserStorage) -> None:
        """Verify unset values use defaults."""
        storage.set_config("storage.location", "project")
        config = storage.get_config()

        # Modified value
        assert config["storage"]["location"] == "project"
        # Default values still present
        assert config["storage"]["max_events"] == 10000
        assert config["features"]["diffs"] is True


class TestAtomicWriteSafety:
    """Tests for atomic write safety."""

    def test_atomic_write_safety(self, storage: PhaserStorage) -> None:
        """Verify writes are atomic (no partial writes)."""
        # Save an audit
        audit_id = storage.save_audit({
            "project": "TestProject",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "pending",
        })

        # Verify file exists and is valid
        audits_file = storage.get_path("audits.json")
        assert audits_file.exists()

        # Verify no temp files left behind
        tmp_file = audits_file.with_suffix(".json.tmp")
        assert not tmp_file.exists()

        # Verify content is valid
        retrieved = storage.get_audit(audit_id)
        assert retrieved is not None


class TestAtomicWriteErrorHandling:
    """Tests for _atomic_write error handling and cleanup."""

    def test_cleans_up_temp_file_on_write_error(
        self, storage: PhaserStorage, temp_dir: Path, monkeypatch
    ) -> None:
        """Verify temp file is cleaned up when write fails."""
        storage.ensure_directories()
        test_file = storage.get_path("test.json")
        tmp_file = test_file.with_suffix(".json.tmp")

        # Create a temp file to simulate partial write
        tmp_file.write_text("partial")

        # Make rename fail to simulate disk error after write
        def fail_rename(self, target):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(Path, "rename", fail_rename)

        with pytest.raises(OSError, match="No space left"):
            storage._atomic_write(test_file, '{"test": 1}')

        # Temp file should be cleaned up
        assert not tmp_file.exists()

    def test_reraises_oserror_after_cleanup(
        self, storage: PhaserStorage, temp_dir: Path, monkeypatch
    ) -> None:
        """Verify OSError is re-raised after cleanup."""
        storage.ensure_directories()
        test_file = storage.get_path("test.json")

        def fail_open(*args, **kwargs):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr("builtins.open", fail_open)

        with pytest.raises(OSError, match="Permission denied"):
            storage._atomic_write(test_file, '{"test": 1}')

    def test_no_temp_file_left_on_success(
        self, storage: PhaserStorage
    ) -> None:
        """Verify no temp files remain after successful write."""
        storage.ensure_directories()
        test_file = storage.get_path("success.json")

        storage._atomic_write(test_file, '{"success": true}')

        assert test_file.exists()
