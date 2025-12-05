"""Tests for the Insights module."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tools.insights import (
    AuditStats,
    ContractStats,
    EventStats,
    FileStats,
    InsightsSummary,
    TrendPoint,
    format_audit_stats,
    format_summary,
    get_audit_stats,
    get_contract_stats,
    get_event_stats,
    get_file_stats,
    get_period_bounds,
    get_summary,
    get_trends,
    parse_since,
)
from tools.storage import PhaserStorage


class TestParseSince:
    """Tests for parse_since function."""

    def test_iso_date(self) -> None:
        """Parses ISO date format."""
        result = parse_since("2025-12-01")
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 1

    def test_relative_days(self) -> None:
        """Parses relative days format."""
        result = parse_since("7d")
        now = datetime.now(timezone.utc)
        expected = now - timedelta(days=7)

        # Allow 1 second tolerance
        assert abs((result - expected).total_seconds()) < 1

    def test_relative_weeks(self) -> None:
        """Parses relative weeks format."""
        result = parse_since("4w")
        now = datetime.now(timezone.utc)
        expected = now - timedelta(weeks=4)

        assert abs((result - expected).total_seconds()) < 1

    def test_relative_months(self) -> None:
        """Parses relative months format."""
        result = parse_since("3m")
        now = datetime.now(timezone.utc)
        expected = now - timedelta(days=90)  # Approximate

        assert abs((result - expected).total_seconds()) < 1

    def test_invalid_format(self) -> None:
        """Raises error for invalid format."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_since("invalid")


class TestGetPeriodBounds:
    """Tests for get_period_bounds function."""

    def test_day_bounds(self) -> None:
        """Day bounds start at midnight."""
        ref = datetime(2025, 12, 5, 14, 30, tzinfo=timezone.utc)
        start, end = get_period_bounds("day", ref)

        assert start.hour == 0
        assert start.minute == 0
        assert end.day == 6

    def test_week_bounds(self) -> None:
        """Week bounds start on Monday."""
        ref = datetime(2025, 12, 5, 14, 30, tzinfo=timezone.utc)  # Friday
        start, end = get_period_bounds("week", ref)

        assert start.weekday() == 0  # Monday
        assert (end - start).days == 7

    def test_month_bounds(self) -> None:
        """Month bounds start on 1st."""
        ref = datetime(2025, 12, 5, 14, 30, tzinfo=timezone.utc)
        start, end = get_period_bounds("month", ref)

        assert start.day == 1
        assert end.month == 1  # January next year


class TestInsightsSummary:
    """Tests for InsightsSummary dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        summary = InsightsSummary(
            period_start="2025-09-05",
            period_end="2025-12-05",
            scope="project",
            audit_count=10,
            completed_count=8,
            in_progress_count=2,
            failed_count=0,
            phase_count=40,
            phase_success_rate=0.95,
            avg_phases_per_audit=4.0,
            top_violations=[("no-singleton", 5)],
            most_changed_files=[("src/main.py", 10)],
        )
        result = summary.to_dict()

        assert result["audit_count"] == 10
        assert result["phase_success_rate"] == 0.95
        assert result["top_violations"][0]["count"] == 5


class TestGetSummary:
    """Tests for get_summary function."""

    def test_empty_storage(self, tmp_path: Path) -> None:
        """Summary with no data."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        result = get_summary(storage)

        assert result.audit_count == 0
        assert result.phase_count == 0
        assert result.scope == "project"

    def test_with_audits(self, tmp_path: Path) -> None:
        """Summary with audit data."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        # Add test audit
        storage.save_audit({
            "project": "test",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "completed",
        })

        result = get_summary(storage)

        assert result.audit_count == 1
        assert result.completed_count == 1


class TestGetAuditStats:
    """Tests for get_audit_stats function."""

    def test_empty_storage(self, tmp_path: Path) -> None:
        """Empty list when no audits."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        result = get_audit_stats(storage)

        assert result == []

    def test_filter_by_status(self, tmp_path: Path) -> None:
        """Filters audits by status."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

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

        result = get_audit_stats(storage, status="completed")

        assert len(result) == 1
        assert result[0].status == "completed"

    def test_limit(self, tmp_path: Path) -> None:
        """Respects limit parameter."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        for i in range(5):
            storage.save_audit({
                "project": "test",
                "slug": f"audit-{i}",
                "date": "2025-12-05",
                "status": "completed",
            })

        result = get_audit_stats(storage, limit=3)

        assert len(result) == 3


class TestGetFileStats:
    """Tests for get_file_stats function."""

    def test_empty_storage(self, tmp_path: Path) -> None:
        """Empty list when no events."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        result = get_file_stats(storage)

        assert result == []

    def test_aggregates_changes(self, tmp_path: Path) -> None:
        """Aggregates file changes from events."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        # Add file events
        audit_id = str(uuid.uuid4())

        for i in range(3):
            storage.append_event({
                "id": str(uuid.uuid4()),
                "type": "file_modified",
                "timestamp": "2025-12-05T10:00:00Z",
                "audit_id": audit_id,
                "data": {"path": "src/main.py"},
            })

        storage.append_event({
            "id": str(uuid.uuid4()),
            "type": "file_created",
            "timestamp": "2025-12-05T10:00:00Z",
            "audit_id": audit_id,
            "data": {"path": "src/new.py"},
        })

        result = get_file_stats(storage)

        assert len(result) == 2
        assert result[0].path == "src/main.py"
        assert result[0].change_count == 3


class TestGetEventStats:
    """Tests for get_event_stats function."""

    def test_empty_storage(self, tmp_path: Path) -> None:
        """Empty list when no events."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        result = get_event_stats(storage)

        assert result == []

    def test_counts_by_type(self, tmp_path: Path) -> None:
        """Counts events by type."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        audit_id = str(uuid.uuid4())

        for _ in range(5):
            storage.append_event({
                "id": str(uuid.uuid4()),
                "type": "phase_completed",
                "timestamp": "2025-12-05T10:00:00Z",
                "audit_id": audit_id,
            })

        for _ in range(2):
            storage.append_event({
                "id": str(uuid.uuid4()),
                "type": "phase_failed",
                "timestamp": "2025-12-05T10:00:00Z",
                "audit_id": audit_id,
            })

        result = get_event_stats(storage)

        phase_completed = next(s for s in result if s.event_type == "phase_completed")
        phase_failed = next(s for s in result if s.event_type == "phase_failed")

        assert phase_completed.count == 5
        assert phase_failed.count == 2


class TestGetTrends:
    """Tests for get_trends function."""

    def test_empty_storage(self, tmp_path: Path) -> None:
        """Returns trend points even with no data."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        result = get_trends(storage, num_periods=4)

        assert len(result) == 4
        assert all(t.audit_count == 0 for t in result)


class TestFormatSummary:
    """Tests for format_summary function."""

    def test_format_empty(self) -> None:
        """Formats empty summary."""
        summary = InsightsSummary(
            period_start=None,
            period_end="2025-12-05",
            scope="project",
            audit_count=0,
            completed_count=0,
            in_progress_count=0,
            failed_count=0,
            phase_count=0,
            phase_success_rate=0.0,
            avg_phases_per_audit=0.0,
            top_violations=[],
            most_changed_files=[],
        )

        result = format_summary(summary)

        assert "No audit data found" in result

    def test_format_with_data(self) -> None:
        """Formats summary with data."""
        summary = InsightsSummary(
            period_start="2025-09-05",
            period_end="2025-12-05",
            scope="project",
            audit_count=10,
            completed_count=8,
            in_progress_count=2,
            failed_count=0,
            phase_count=40,
            phase_success_rate=0.95,
            avg_phases_per_audit=4.0,
            top_violations=[("no-singleton", 5)],
            most_changed_files=[("src/main.py", 10)],
        )

        result = format_summary(summary)

        assert "Total: 10" in result
        assert "Completed: 8" in result
        assert "95%" in result


class TestFormatAuditStats:
    """Tests for format_audit_stats function."""

    def test_format_empty(self) -> None:
        """Formats empty list."""
        result = format_audit_stats([])
        assert "No audits found" in result

    def test_format_with_data(self) -> None:
        """Formats audit stats."""
        stats = [
            AuditStats(
                id="abc-123",
                slug="test-audit",
                project="test",
                date="2025-12-05",
                status="completed",
                phase_count=6,
                completed_phases=6,
                duration_seconds=3600,
            )
        ]

        result = format_audit_stats(stats)

        assert "test-audit" in result
        assert "2025-12-05" in result
        assert "6/6" in result
        assert "1h 0m" in result


class TestAuditStats:
    """Tests for AuditStats dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        stats = AuditStats(
            id="abc-123",
            slug="test-audit",
            project="test",
            date="2025-12-05",
            status="completed",
            phase_count=6,
            completed_phases=5,
            duration_seconds=3600,
        )

        result = stats.to_dict()

        assert result["id"] == "abc-123"
        assert result["slug"] == "test-audit"
        assert result["duration_seconds"] == 3600


class TestContractStats:
    """Tests for ContractStats dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        stats = ContractStats(
            contract_id="no-singleton",
            rule_id="no-singleton",
            severity="error",
            violation_count=5,
            last_violation="2025-12-05T10:00:00Z",
            affected_files=["src/main.py"],
        )

        result = stats.to_dict()

        assert result["contract_id"] == "no-singleton"
        assert result["violation_count"] == 5


class TestFileStats:
    """Tests for FileStats dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        stats = FileStats(
            path="src/main.py",
            change_count=10,
            audit_count=3,
            last_changed="2025-12-05T10:00:00Z",
            change_types={"modified": 8, "created": 2},
        )

        result = stats.to_dict()

        assert result["path"] == "src/main.py"
        assert result["change_count"] == 10
        assert result["change_types"]["modified"] == 8


class TestEventStats:
    """Tests for EventStats dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        stats = EventStats(
            event_type="phase_completed",
            count=15,
            last_occurred="2025-12-05T10:00:00Z",
        )

        result = stats.to_dict()

        assert result["event_type"] == "phase_completed"
        assert result["count"] == 15


class TestTrendPoint:
    """Tests for TrendPoint dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        point = TrendPoint(
            period_start="2025-12-02",
            period_end="2025-12-09",
            audit_count=3,
            phase_count=15,
            violation_count=2,
        )

        result = point.to_dict()

        assert result["period_start"] == "2025-12-02"
        assert result["audit_count"] == 3


class TestGetContractStats:
    """Tests for get_contract_stats function."""

    def test_empty_storage(self, tmp_path: Path) -> None:
        """Empty list when no violations."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        result = get_contract_stats(storage)

        assert result == []

    def test_aggregates_violations(self, tmp_path: Path) -> None:
        """Aggregates violations by contract."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        audit_id = str(uuid.uuid4())

        # Add violation events
        for _ in range(3):
            storage.append_event({
                "id": str(uuid.uuid4()),
                "type": "verification_failed",
                "timestamp": "2025-12-05T10:00:00Z",
                "audit_id": audit_id,
                "data": {
                    "contract_id": "no-singleton",
                    "path": "src/main.py",
                    "severity": "error",
                },
            })

        storage.append_event({
            "id": str(uuid.uuid4()),
            "type": "verification_failed",
            "timestamp": "2025-12-05T10:00:00Z",
            "audit_id": audit_id,
            "data": {
                "contract_id": "require-tests",
                "path": "src/utils.py",
                "severity": "warning",
            },
        })

        result = get_contract_stats(storage)

        assert len(result) == 2

        no_singleton = next(s for s in result if s.contract_id == "no-singleton")
        assert no_singleton.violation_count == 3
        assert no_singleton.severity == "error"
