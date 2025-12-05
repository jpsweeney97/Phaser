"""Tests for the Replay module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.replay import (
    FileChange,
    Regression,
    RegressionType,
    ReplayableAudit,
    ReplayResult,
    ReplayScope,
    check_file_regressions,
    format_replay_result,
    format_replayable_audits,
    get_audit_by_slug,
    get_audit_file_changes,
    get_replayable_audits,
    now_iso,
    save_replay_result,
)
from tools.storage import PhaserStorage


class TestReplayScope:
    """Tests for ReplayScope enum."""

    def test_all_value(self) -> None:
        """ALL has correct value."""
        assert ReplayScope.ALL.value == "all"

    def test_contracts_value(self) -> None:
        """CONTRACTS has correct value."""
        assert ReplayScope.CONTRACTS.value == "contracts"

    def test_files_value(self) -> None:
        """FILES has correct value."""
        assert ReplayScope.FILES.value == "files"


class TestRegressionType:
    """Tests for RegressionType enum."""

    def test_contract_violation_value(self) -> None:
        """CONTRACT_VIOLATION has correct value."""
        assert RegressionType.CONTRACT_VIOLATION.value == "contract_violation"

    def test_file_regression_value(self) -> None:
        """FILE_REGRESSION has correct value."""
        assert RegressionType.FILE_REGRESSION.value == "file_regression"

    def test_pattern_regression_value(self) -> None:
        """PATTERN_REGRESSION has correct value."""
        assert RegressionType.PATTERN_REGRESSION.value == "pattern_regression"

    def test_contract_missing_value(self) -> None:
        """CONTRACT_MISSING has correct value."""
        assert RegressionType.CONTRACT_MISSING.value == "contract_missing"


class TestRegression:
    """Tests for Regression dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        reg = Regression(
            type=RegressionType.CONTRACT_VIOLATION,
            source="no-singleton",
            message="Contract failed",
            severity="error",
            details={"count": 5},
        )
        result = reg.to_dict()

        assert result["type"] == "contract_violation"
        assert result["source"] == "no-singleton"
        assert result["message"] == "Contract failed"
        assert result["severity"] == "error"
        assert result["details"]["count"] == 5

    def test_from_dict(self) -> None:
        """from_dict reconstructs Regression."""
        data = {
            "type": "file_regression",
            "source": "/path/to/file",
            "message": "File reappeared",
            "severity": "warning",
            "details": {},
        }
        reg = Regression.from_dict(data)

        assert reg.type == RegressionType.FILE_REGRESSION
        assert reg.source == "/path/to/file"
        assert reg.severity == "warning"

    def test_default_severity(self) -> None:
        """Default severity is error."""
        reg = Regression(
            type=RegressionType.CONTRACT_VIOLATION,
            source="test",
            message="Test",
        )
        assert reg.severity == "error"

    def test_default_details(self) -> None:
        """Default details is empty dict."""
        reg = Regression(
            type=RegressionType.CONTRACT_VIOLATION,
            source="test",
            message="Test",
        )
        assert reg.details == {}


class TestReplayResult:
    """Tests for ReplayResult dataclass."""

    def test_passed_when_no_regressions(self) -> None:
        """passed is True when no regressions."""
        result = ReplayResult(
            audit_id="abc",
            audit_slug="test",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
            regressions=[],
        )
        assert result.passed is True
        assert result.regression_count == 0

    def test_not_passed_with_regressions(self) -> None:
        """passed is False when regressions exist."""
        result = ReplayResult(
            audit_id="abc",
            audit_slug="test",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
            regressions=[
                Regression(
                    type=RegressionType.CONTRACT_VIOLATION,
                    source="test",
                    message="Test",
                )
            ],
        )
        assert result.passed is False
        assert result.regression_count == 1

    def test_error_and_warning_counts(self) -> None:
        """error_count and warning_count work correctly."""
        result = ReplayResult(
            audit_id="abc",
            audit_slug="test",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
            regressions=[
                Regression(type=RegressionType.CONTRACT_VIOLATION, source="a", message="A", severity="error"),
                Regression(type=RegressionType.CONTRACT_VIOLATION, source="b", message="B", severity="error"),
                Regression(type=RegressionType.FILE_REGRESSION, source="c", message="C", severity="warning"),
            ],
        )
        assert result.error_count == 2
        assert result.warning_count == 1

    def test_to_dict(self) -> None:
        """to_dict includes all fields."""
        result = ReplayResult(
            audit_id="abc",
            audit_slug="test",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.CONTRACTS,
            contracts_checked=5,
            contracts_passed=4,
        )
        data = result.to_dict()

        assert data["audit_id"] == "abc"
        assert data["scope"] == "contracts"
        assert data["contracts_checked"] == 5
        assert data["passed"] is True

    def test_from_dict(self) -> None:
        """from_dict reconstructs ReplayResult."""
        data = {
            "audit_id": "abc",
            "audit_slug": "test",
            "replayed_at": "2025-12-05T10:00:00Z",
            "scope": "files",
            "files_checked": 10,
            "files_passed": 8,
            "regressions": [
                {"type": "file_regression", "source": "f.py", "message": "Missing"}
            ],
        }
        result = ReplayResult.from_dict(data)

        assert result.scope == ReplayScope.FILES
        assert result.files_checked == 10
        assert len(result.regressions) == 1


class TestReplayableAudit:
    """Tests for ReplayableAudit dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        audit = ReplayableAudit(
            id="abc-123",
            slug="test-audit",
            date="2025-12-05",
            status="completed",
            phase_count=6,
            contract_ids=["c1", "c2"],
            file_change_count=15,
        )
        data = audit.to_dict()

        assert data["slug"] == "test-audit"
        assert data["phase_count"] == 6
        assert len(data["contract_ids"]) == 2

    def test_from_dict(self) -> None:
        """from_dict reconstructs ReplayableAudit."""
        data = {
            "id": "abc",
            "slug": "test",
            "date": "2025-12-05",
            "status": "completed",
            "last_replayed": "2025-12-06T10:00:00Z",
            "last_replay_passed": True,
        }
        audit = ReplayableAudit.from_dict(data)

        assert audit.last_replayed == "2025-12-06T10:00:00Z"
        assert audit.last_replay_passed is True


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_to_dict_minimal(self) -> None:
        """to_dict with minimal fields."""
        change = FileChange(
            path="src/main.py",
            change_type="created",
            timestamp="2025-12-05T10:00:00Z",
            audit_id="abc",
        )
        data = change.to_dict()

        assert data["path"] == "src/main.py"
        assert data["change_type"] == "created"
        assert "hash_before" not in data

    def test_to_dict_with_hashes(self) -> None:
        """to_dict includes optional hash fields."""
        change = FileChange(
            path="src/main.py",
            change_type="modified",
            timestamp="2025-12-05T10:00:00Z",
            audit_id="abc",
            hash_before="abc123",
            hash_after="def456",
        )
        data = change.to_dict()

        assert data["hash_before"] == "abc123"
        assert data["hash_after"] == "def456"

    def test_from_dict(self) -> None:
        """from_dict reconstructs FileChange."""
        data = {
            "path": "src/test.py",
            "change_type": "deleted",
            "timestamp": "2025-12-05T10:00:00Z",
            "audit_id": "abc",
            "hash_before": "xyz789",
        }
        change = FileChange.from_dict(data)

        assert change.path == "src/test.py"
        assert change.change_type == "deleted"
        assert change.hash_before == "xyz789"
        assert change.hash_after is None


class TestGetAuditBySlug:
    """Tests for get_audit_by_slug function."""

    def test_finds_by_slug(self, tmp_path: Path) -> None:
        """Finds audit by exact slug."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.save_audit({
            "project": "test",
            "slug": "my-audit",
            "date": "2025-12-05",
            "status": "completed",
        })

        result = get_audit_by_slug("my-audit", storage)

        assert result is not None
        assert result["slug"] == "my-audit"

    def test_latest_returns_most_recent(self, tmp_path: Path) -> None:
        """'latest' returns most recent completed audit."""
        storage = PhaserStorage(tmp_path / ".phaser")

        storage.save_audit({
            "project": "test",
            "slug": "old-audit",
            "date": "2025-12-01",
            "status": "completed",
        })
        storage.save_audit({
            "project": "test",
            "slug": "new-audit",
            "date": "2025-12-05",
            "status": "completed",
        })

        result = get_audit_by_slug("latest", storage)

        assert result is not None
        assert result["slug"] == "new-audit"

    def test_returns_none_if_not_found(self, tmp_path: Path) -> None:
        """Returns None if slug not found."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        result = get_audit_by_slug("nonexistent", storage)

        assert result is None

    def test_latest_returns_none_if_no_completed(self, tmp_path: Path) -> None:
        """'latest' returns None if no completed audits."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.save_audit({
            "project": "test",
            "slug": "in-progress",
            "date": "2025-12-05",
            "status": "in_progress",
        })

        result = get_audit_by_slug("latest", storage)

        assert result is None


class TestCheckFileRegressions:
    """Tests for check_file_regressions function."""

    def test_deleted_file_reappeared(self, tmp_path: Path) -> None:
        """Detects deleted file that reappeared."""
        # Create the file that should be deleted
        test_file = tmp_path / "should_be_deleted.py"
        test_file.write_text("content")

        changes = [
            FileChange(
                path="should_be_deleted.py",
                change_type="deleted",
                timestamp="2025-12-05T10:00:00Z",
                audit_id="abc",
            )
        ]

        checked, passed, regressions = check_file_regressions(changes, tmp_path)

        assert checked == 1
        assert passed == 0
        assert len(regressions) == 1
        assert regressions[0].type == RegressionType.FILE_REGRESSION
        assert "reappeared" in regressions[0].message

    def test_deleted_file_still_deleted(self, tmp_path: Path) -> None:
        """No regression if deleted file stays deleted."""
        changes = [
            FileChange(
                path="was_deleted.py",
                change_type="deleted",
                timestamp="2025-12-05T10:00:00Z",
                audit_id="abc",
            )
        ]

        checked, passed, regressions = check_file_regressions(changes, tmp_path)

        assert checked == 1
        assert passed == 1
        assert len(regressions) == 0

    def test_created_file_still_exists(self, tmp_path: Path) -> None:
        """No regression if created file still exists."""
        test_file = tmp_path / "created.py"
        test_file.write_text("content")

        changes = [
            FileChange(
                path="created.py",
                change_type="created",
                timestamp="2025-12-05T10:00:00Z",
                audit_id="abc",
            )
        ]

        checked, passed, regressions = check_file_regressions(changes, tmp_path)

        assert checked == 1
        assert passed == 1
        assert len(regressions) == 0

    def test_created_file_missing(self, tmp_path: Path) -> None:
        """Detects created file that is now missing."""
        changes = [
            FileChange(
                path="should_exist.py",
                change_type="created",
                timestamp="2025-12-05T10:00:00Z",
                audit_id="abc",
            )
        ]

        checked, passed, regressions = check_file_regressions(changes, tmp_path)

        assert checked == 1
        assert passed == 0
        assert len(regressions) == 1
        assert "missing" in regressions[0].message

    def test_modified_file_still_exists(self, tmp_path: Path) -> None:
        """No regression if modified file still exists."""
        test_file = tmp_path / "modified.py"
        test_file.write_text("content")

        changes = [
            FileChange(
                path="modified.py",
                change_type="modified",
                timestamp="2025-12-05T10:00:00Z",
                audit_id="abc",
            )
        ]

        checked, passed, regressions = check_file_regressions(changes, tmp_path)

        assert checked == 1
        assert passed == 1
        assert len(regressions) == 0

    def test_modified_file_missing(self, tmp_path: Path) -> None:
        """Detects modified file that is now missing."""
        changes = [
            FileChange(
                path="was_modified.py",
                change_type="modified",
                timestamp="2025-12-05T10:00:00Z",
                audit_id="abc",
            )
        ]

        checked, passed, regressions = check_file_regressions(changes, tmp_path)

        assert checked == 1
        assert passed == 0
        assert len(regressions) == 1
        assert "missing" in regressions[0].message

    def test_renamed_file_exists(self, tmp_path: Path) -> None:
        """No regression if renamed file exists at new path."""
        test_file = tmp_path / "new_name.py"
        test_file.write_text("content")

        changes = [
            FileChange(
                path="new_name.py",
                change_type="renamed",
                timestamp="2025-12-05T10:00:00Z",
                audit_id="abc",
                old_path="old_name.py",
            )
        ]

        checked, passed, regressions = check_file_regressions(changes, tmp_path)

        assert checked == 1
        assert passed == 1
        assert len(regressions) == 0


class TestFormatReplayResult:
    """Tests for format_replay_result function."""

    def test_format_passing_result(self) -> None:
        """Formats passing result correctly."""
        result = ReplayResult(
            audit_id="abc",
            audit_slug="test-audit",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
            contracts_checked=3,
            contracts_passed=3,
            files_checked=10,
            files_passed=10,
        )

        output = format_replay_result(result)

        assert "test-audit" in output
        assert "No regressions detected" in output
        assert "3 checked, 3 passed" in output

    def test_format_failing_result(self) -> None:
        """Formats failing result with regressions."""
        result = ReplayResult(
            audit_id="abc",
            audit_slug="test-audit",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
            regressions=[
                Regression(
                    type=RegressionType.CONTRACT_VIOLATION,
                    source="no-singleton",
                    message="Contract failed",
                    severity="error",
                )
            ],
        )

        output = format_replay_result(result)

        assert "Regressions (1)" in output
        assert "ERROR" in output
        assert "no-singleton" in output

    def test_format_warning_result(self) -> None:
        """Formats warning-level regression."""
        result = ReplayResult(
            audit_id="abc",
            audit_slug="test-audit",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
            regressions=[
                Regression(
                    type=RegressionType.FILE_REGRESSION,
                    source="old_file.py",
                    message="Old path exists",
                    severity="warning",
                )
            ],
        )

        output = format_replay_result(result)

        assert "WARNING" in output


class TestFormatReplayableAudits:
    """Tests for format_replayable_audits function."""

    def test_format_empty_list(self) -> None:
        """Formats empty list with helpful message."""
        output = format_replayable_audits([])

        assert "No completed audits" in output

    def test_format_audit_list(self) -> None:
        """Formats list of audits."""
        audits = [
            ReplayableAudit(
                id="abc",
                slug="test-audit",
                date="2025-12-05",
                status="completed",
                phase_count=6,
                contract_ids=["c1", "c2"],
            )
        ]

        output = format_replayable_audits(audits)

        assert "test-audit" in output
        assert "2025-12-05" in output
        assert "Audits Available for Replay" in output


class TestGetReplayableAudits:
    """Tests for get_replayable_audits function."""

    def test_returns_completed_audits(self, tmp_path: Path) -> None:
        """Returns only completed audits by default."""
        storage = PhaserStorage(tmp_path / ".phaser")

        storage.save_audit({
            "project": "test",
            "slug": "completed-audit",
            "date": "2025-12-05",
            "status": "completed",
        })
        storage.save_audit({
            "project": "test",
            "slug": "in-progress-audit",
            "date": "2025-12-05",
            "status": "in_progress",
        })

        result = get_replayable_audits(storage)

        assert len(result) == 1
        assert result[0].slug == "completed-audit"

    def test_returns_all_with_status_all(self, tmp_path: Path) -> None:
        """Returns all audits when status='all'."""
        storage = PhaserStorage(tmp_path / ".phaser")

        storage.save_audit({
            "project": "test",
            "slug": "completed-audit",
            "date": "2025-12-05",
            "status": "completed",
        })
        storage.save_audit({
            "project": "test",
            "slug": "in-progress-audit",
            "date": "2025-12-05",
            "status": "in_progress",
        })

        result = get_replayable_audits(storage, status="all")

        assert len(result) == 2

    def test_respects_limit(self, tmp_path: Path) -> None:
        """Respects limit parameter."""
        storage = PhaserStorage(tmp_path / ".phaser")

        for i in range(5):
            storage.save_audit({
                "project": "test",
                "slug": f"audit-{i}",
                "date": f"2025-12-0{i+1}",
                "status": "completed",
            })

        result = get_replayable_audits(storage, limit=3)

        assert len(result) == 3


class TestSaveReplayResult:
    """Tests for save_replay_result function."""

    def test_saves_to_replays_json(self, tmp_path: Path) -> None:
        """Saves result to replays.json."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        # Create an audit to update
        audit_id = storage.save_audit({
            "project": "test",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "completed",
        })

        result = ReplayResult(
            audit_id=audit_id,
            audit_slug="test-audit",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
        )

        save_replay_result(result, storage)

        replays_path = storage.get_path("replays.json")
        assert replays_path.exists()

        with open(replays_path) as f:
            data = json.load(f)
        assert len(data["replays"]) == 1
        assert data["replays"][0]["audit_slug"] == "test-audit"

    def test_appends_to_existing(self, tmp_path: Path) -> None:
        """Appends to existing replays."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        # Create initial replay file
        replays_path = storage.get_path("replays.json")
        with open(replays_path, "w") as f:
            json.dump({"version": 1, "replays": [{"audit_slug": "old"}]}, f)

        audit_id = storage.save_audit({
            "project": "test",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "completed",
        })

        result = ReplayResult(
            audit_id=audit_id,
            audit_slug="test-audit",
            replayed_at="2025-12-05T10:00:00Z",
            scope=ReplayScope.ALL,
        )

        save_replay_result(result, storage)

        with open(replays_path) as f:
            data = json.load(f)
        assert len(data["replays"]) == 2


class TestNowIso:
    """Tests for now_iso helper function."""

    def test_returns_iso_format(self) -> None:
        """Returns valid ISO 8601 timestamp."""
        result = now_iso()

        assert "T" in result
        assert "Z" in result or "+" in result

    def test_consistent_format(self) -> None:
        """Returns consistent format on multiple calls."""
        r1 = now_iso()
        r2 = now_iso()

        # Both should have same structure
        assert len(r1) == len(r2)


class TestGetAuditFileChanges:
    """Tests for get_audit_file_changes function."""

    def test_returns_file_changes_from_events(self, tmp_path: Path) -> None:
        """Extracts file changes from events."""
        storage = PhaserStorage(tmp_path / ".phaser")
        audit_id = storage.save_audit({
            "project": "test",
            "slug": "test",
            "date": "2025-12-05",
            "status": "completed",
        })

        # Add file events
        storage.append_event({
            "id": "evt-001",
            "type": "file_created",
            "timestamp": "2025-12-05T10:00:00Z",
            "audit_id": audit_id,
            "data": {"path": "src/new.py"},
        })
        storage.append_event({
            "id": "evt-002",
            "type": "file_deleted",
            "timestamp": "2025-12-05T10:01:00Z",
            "audit_id": audit_id,
            "data": {"path": "src/old.py"},
        })

        result = get_audit_file_changes(audit_id, storage)

        assert len(result) == 2
        assert result[0].path == "src/new.py"
        assert result[0].change_type == "created"
        assert result[1].path == "src/old.py"
        assert result[1].change_type == "deleted"

    def test_ignores_non_file_events(self, tmp_path: Path) -> None:
        """Ignores events that aren't file changes."""
        storage = PhaserStorage(tmp_path / ".phaser")
        audit_id = storage.save_audit({
            "project": "test",
            "slug": "test",
            "date": "2025-12-05",
            "status": "completed",
        })

        storage.append_event({
            "id": "evt-001",
            "type": "phase_completed",
            "timestamp": "2025-12-05T10:00:00Z",
            "audit_id": audit_id,
            "data": {"phase": 1},
        })
        storage.append_event({
            "id": "evt-002",
            "type": "file_created",
            "timestamp": "2025-12-05T10:01:00Z",
            "audit_id": audit_id,
            "data": {"path": "src/new.py"},
        })

        result = get_audit_file_changes(audit_id, storage)

        assert len(result) == 1
        assert result[0].change_type == "created"
