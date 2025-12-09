"""Tests for analytics module."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from tools.analytics import (
    ANALYTICS_SCHEMA_VERSION,
    AggregatedStats,
    AnalyticsError,
    AnalyticsQuery,
    ExecutionRecord,
    ExecutionStatus,
    ImportError,
    PhaseRecord,
    PhaseStatus,
    QueryError,
    StorageError,
)


# =============================================================================
# ExecutionStatus Tests
# =============================================================================


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_values(self):
        """Test enum values."""
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.PARTIAL.value == "partial"
        assert ExecutionStatus.FAILED.value == "failed"

    def test_from_report_success(self):
        """Test parsing success status from report."""
        result = ExecutionStatus.from_report("**Result:** ✅ All phases completed")
        assert result == ExecutionStatus.SUCCESS

    def test_from_report_partial(self):
        """Test parsing partial status from report."""
        result = ExecutionStatus.from_report("**Result:** ⚠️ Completed with issues")
        assert result == ExecutionStatus.PARTIAL

    def test_from_report_partial_lowercase(self):
        """Test parsing partial status with lowercase."""
        result = ExecutionStatus.from_report("Result: Partial completion")
        assert result == ExecutionStatus.PARTIAL

    def test_from_report_failed(self):
        """Test parsing failed status from report."""
        result = ExecutionStatus.from_report("**Result:** ❌ Failed")
        assert result == ExecutionStatus.FAILED

    def test_from_report_unknown_defaults_failed(self):
        """Test unknown status defaults to failed."""
        result = ExecutionStatus.from_report("Unknown status text")
        assert result == ExecutionStatus.FAILED


# =============================================================================
# PhaseStatus Tests
# =============================================================================


class TestPhaseStatus:
    """Tests for PhaseStatus enum."""

    def test_values(self):
        """Test enum values."""
        assert PhaseStatus.COMPLETED.value == "completed"
        assert PhaseStatus.FAILED.value == "failed"
        assert PhaseStatus.SKIPPED.value == "skipped"

    def test_from_symbol_completed(self):
        """Test parsing completed symbol."""
        result = PhaseStatus.from_symbol("✅")
        assert result == PhaseStatus.COMPLETED

    def test_from_symbol_failed(self):
        """Test parsing failed symbol."""
        result = PhaseStatus.from_symbol("❌")
        assert result == PhaseStatus.FAILED

    def test_from_symbol_skipped(self):
        """Test parsing skipped symbol."""
        result = PhaseStatus.from_symbol("⚠️")
        assert result == PhaseStatus.SKIPPED

    def test_from_symbol_unknown_defaults_skipped(self):
        """Test unknown symbol defaults to skipped."""
        result = PhaseStatus.from_symbol("?")
        assert result == PhaseStatus.SKIPPED


# =============================================================================
# PhaseRecord Tests
# =============================================================================


class TestPhaseRecord:
    """Tests for PhaseRecord dataclass."""

    def test_create_minimal(self):
        """Test creating with minimal fields."""
        record = PhaseRecord(
            phase_number=1,
            title="Test Phase",
            status=PhaseStatus.COMPLETED,
        )
        assert record.phase_number == 1
        assert record.title == "Test Phase"
        assert record.status == PhaseStatus.COMPLETED
        assert record.commit_sha is None

    def test_create_full(self):
        """Test creating with all fields."""
        now = datetime.now(timezone.utc)
        record = PhaseRecord(
            phase_number=5,
            title="Complex Phase",
            status=PhaseStatus.COMPLETED,
            commit_sha="abc123",
            started_at=now,
            completed_at=now + timedelta(hours=1),
            duration_seconds=3600.0,
            tests_before=100,
            tests_after=110,
            error_message=None,
            retry_count=0,
        )
        assert record.commit_sha == "abc123"
        assert record.duration_seconds == 3600.0
        assert record.tests_after == 110

    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime(2024, 12, 6, 10, 30, 0)
        record = PhaseRecord(
            phase_number=1,
            title="Test",
            status=PhaseStatus.COMPLETED,
            commit_sha="abc123",
            completed_at=now,
        )
        data = record.to_dict()
        assert data["phase_number"] == 1
        assert data["title"] == "Test"
        assert data["status"] == "completed"
        assert data["commit_sha"] == "abc123"
        assert data["completed_at"] == "2024-12-06T10:30:00"

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "phase_number": 2,
            "title": "Loaded Phase",
            "status": "failed",
            "commit_sha": None,
            "error_message": "Test failed",
            "retry_count": 2,
        }
        record = PhaseRecord.from_dict(data)
        assert record.phase_number == 2
        assert record.status == PhaseStatus.FAILED
        assert record.error_message == "Test failed"
        assert record.retry_count == 2

    def test_round_trip(self):
        """Test serialization round-trip."""
        now = datetime(2024, 12, 6, 10, 0, 0)
        original = PhaseRecord(
            phase_number=3,
            title="Round Trip",
            status=PhaseStatus.COMPLETED,
            commit_sha="def456",
            started_at=now,
            completed_at=now + timedelta(minutes=30),
            duration_seconds=1800.0,
            tests_before=50,
            tests_after=55,
        )
        restored = PhaseRecord.from_dict(original.to_dict())
        assert restored.phase_number == original.phase_number
        assert restored.title == original.title
        assert restored.status == original.status
        assert restored.commit_sha == original.commit_sha
        assert restored.completed_at == original.completed_at


# =============================================================================
# ExecutionRecord Tests
# =============================================================================


class TestExecutionRecord:
    """Tests for ExecutionRecord dataclass."""

    @pytest.fixture
    def sample_record(self):
        """Create a sample execution record."""
        return ExecutionRecord(
            execution_id="test-123",
            audit_document="document-7-reverse.md",
            document_title="Document 7: Reverse Audit",
            project_name="Phaser",
            project_path="/Users/jp/Projects/Phaser",
            branch="audit/2024-12-06-reverse",
            started_at=datetime(2024, 12, 6, 10, 0, 0),
            completed_at=datetime(2024, 12, 6, 11, 30, 0),
            phaser_version="1.6.3",
            status=ExecutionStatus.SUCCESS,
            phases_planned=6,
            phases_completed=6,
            baseline_tests=280,
            final_tests=312,
            base_commit="aaa111",
            final_commit="bbb222",
            commit_count=7,
            files_changed=12,
            phases=[
                PhaseRecord(1, "Phase 1", PhaseStatus.COMPLETED, "c1"),
                PhaseRecord(2, "Phase 2", PhaseStatus.COMPLETED, "c2"),
            ],
        )

    def test_duration_seconds(self, sample_record):
        """Test duration computation."""
        # 1.5 hours = 5400 seconds
        assert sample_record.duration_seconds == 5400.0

    def test_test_delta(self, sample_record):
        """Test test delta computation."""
        assert sample_record.test_delta == 32

    def test_success_rate(self, sample_record):
        """Test success rate computation."""
        assert sample_record.success_rate == 1.0

    def test_success_rate_partial(self):
        """Test success rate with partial completion."""
        record = ExecutionRecord(
            execution_id="test",
            audit_document="test.md",
            document_title="Test",
            project_name="Test",
            project_path="/test",
            branch="test",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            phaser_version="1.0",
            status=ExecutionStatus.PARTIAL,
            phases_planned=10,
            phases_completed=7,
            baseline_tests=100,
            final_tests=120,
            base_commit="a",
            final_commit="b",
            commit_count=7,
            files_changed=5,
        )
        assert record.success_rate == 0.7

    def test_success_rate_zero_phases(self):
        """Test success rate with zero phases."""
        record = ExecutionRecord(
            execution_id="test",
            audit_document="test.md",
            document_title="Test",
            project_name="Test",
            project_path="/test",
            branch="test",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            phaser_version="1.0",
            status=ExecutionStatus.FAILED,
            phases_planned=0,
            phases_completed=0,
            baseline_tests=100,
            final_tests=100,
            base_commit="a",
            final_commit="a",
            commit_count=0,
            files_changed=0,
        )
        assert record.success_rate == 0.0

    def test_to_dict(self, sample_record):
        """Test serialization to dictionary."""
        data = sample_record.to_dict()
        assert data["schema_version"] == ANALYTICS_SCHEMA_VERSION
        assert data["execution_id"] == "test-123"
        assert data["audit_document"] == "document-7-reverse.md"
        assert data["status"] == "success"
        assert data["duration_seconds"] == 5400.0
        assert data["test_delta"] == 32
        assert len(data["phases"]) == 2

    def test_from_dict(self, sample_record):
        """Test deserialization from dictionary."""
        data = sample_record.to_dict()
        restored = ExecutionRecord.from_dict(data)
        assert restored.execution_id == sample_record.execution_id
        assert restored.status == sample_record.status
        assert restored.phases_planned == sample_record.phases_planned
        assert len(restored.phases) == len(sample_record.phases)

    def test_generate_id(self):
        """Test ID generation."""
        id1 = ExecutionRecord.generate_id()
        id2 = ExecutionRecord.generate_id()
        assert id1 != id2
        assert len(id1) == 36  # UUID format


# =============================================================================
# AggregatedStats Tests
# =============================================================================


class TestAggregatedStats:
    """Tests for AggregatedStats dataclass."""

    @pytest.fixture
    def sample_records(self):
        """Create sample execution records."""
        base = datetime(2024, 12, 1, 10, 0, 0)
        return [
            ExecutionRecord(
                execution_id="1",
                audit_document="doc1.md",
                document_title="Doc 1",
                project_name="Test",
                project_path="/test",
                branch="b1",
                started_at=base,
                completed_at=base + timedelta(hours=1),
                phaser_version="1.0",
                status=ExecutionStatus.SUCCESS,
                phases_planned=5,
                phases_completed=5,
                baseline_tests=100,
                final_tests=120,
                base_commit="a",
                final_commit="b",
                commit_count=5,
                files_changed=10,
            ),
            ExecutionRecord(
                execution_id="2",
                audit_document="doc2.md",
                document_title="Doc 2",
                project_name="Test",
                project_path="/test",
                branch="b2",
                started_at=base + timedelta(days=1),
                completed_at=base + timedelta(days=1, hours=2),
                phaser_version="1.0",
                status=ExecutionStatus.SUCCESS,
                phases_planned=3,
                phases_completed=3,
                baseline_tests=120,
                final_tests=140,
                base_commit="b",
                final_commit="c",
                commit_count=3,
                files_changed=6,
            ),
            ExecutionRecord(
                execution_id="3",
                audit_document="doc3.md",
                document_title="Doc 3",
                project_name="Test",
                project_path="/test",
                branch="b3",
                started_at=base + timedelta(days=2),
                completed_at=base + timedelta(days=2, minutes=30),
                phaser_version="1.0",
                status=ExecutionStatus.FAILED,
                phases_planned=4,
                phases_completed=1,
                baseline_tests=140,
                final_tests=142,
                base_commit="c",
                final_commit="d",
                commit_count=1,
                files_changed=2,
            ),
        ]

    def test_empty(self):
        """Test empty stats."""
        stats = AggregatedStats.empty()
        assert stats.total_executions == 0
        assert stats.success_rate == 0.0
        assert stats.earliest_execution is None

    def test_compute_empty_list(self):
        """Test computing stats from empty list."""
        stats = AggregatedStats.compute([])
        assert stats.total_executions == 0
        assert stats.success_rate == 0.0

    def test_compute_counts(self, sample_records):
        """Test execution counts."""
        stats = AggregatedStats.compute(sample_records)
        assert stats.total_executions == 3
        assert stats.successful == 2
        assert stats.failed == 1
        assert stats.partial == 0

    def test_compute_success_rate(self, sample_records):
        """Test success rate calculation."""
        stats = AggregatedStats.compute(sample_records)
        assert abs(stats.success_rate - 0.6667) < 0.01

    def test_compute_durations(self, sample_records):
        """Test duration calculations."""
        stats = AggregatedStats.compute(sample_records)
        # 1 hour, 2 hours, 30 minutes
        assert stats.min_duration_seconds == 1800.0  # 30 min
        assert stats.max_duration_seconds == 7200.0  # 2 hours
        assert stats.total_duration_seconds == 12600.0  # 3.5 hours

    def test_compute_test_delta(self, sample_records):
        """Test test delta calculations."""
        stats = AggregatedStats.compute(sample_records)
        # 20 + 20 + 2 = 42
        assert stats.total_test_delta == 42
        assert stats.avg_test_delta == 14.0

    def test_compute_phases(self, sample_records):
        """Test phase calculations."""
        stats = AggregatedStats.compute(sample_records)
        assert stats.total_phases_executed == 12  # 5 + 3 + 4
        assert stats.total_phases_completed == 9  # 5 + 3 + 1

    def test_phase_success_rate(self, sample_records):
        """Test phase success rate."""
        stats = AggregatedStats.compute(sample_records)
        assert stats.phase_success_rate == 0.75  # 9/12

    def test_compute_time_range(self, sample_records):
        """Test time range detection."""
        stats = AggregatedStats.compute(sample_records)
        assert stats.earliest_execution == datetime(2024, 12, 1, 10, 0, 0)
        assert stats.latest_execution == datetime(2024, 12, 3, 10, 0, 0)

    def test_to_dict(self, sample_records):
        """Test serialization."""
        stats = AggregatedStats.compute(sample_records)
        data = stats.to_dict()
        assert data["total_executions"] == 3
        assert "success_rate" in data
        assert "phase_success_rate" in data


# =============================================================================
# AnalyticsQuery Tests
# =============================================================================


class TestAnalyticsQuery:
    """Tests for AnalyticsQuery dataclass."""

    @pytest.fixture
    def sample_record(self):
        """Create a sample record for matching tests."""
        return ExecutionRecord(
            execution_id="test",
            audit_document="document-7-reverse.md",
            document_title="Doc 7",
            project_name="Test",
            project_path="/test",
            branch="test",
            started_at=datetime(2024, 12, 6, 10, 0, 0),
            completed_at=datetime(2024, 12, 6, 11, 0, 0),
            phaser_version="1.0",
            status=ExecutionStatus.SUCCESS,
            phases_planned=5,
            phases_completed=5,
            baseline_tests=100,
            final_tests=110,
            base_commit="a",
            final_commit="b",
            commit_count=5,
            files_changed=10,
        )

    def test_default_matches_all(self, sample_record):
        """Test default query matches everything."""
        query = AnalyticsQuery()
        assert query.matches(sample_record)

    def test_since_filter_matches(self, sample_record):
        """Test since filter matches record after date."""
        query = AnalyticsQuery(since=datetime(2024, 12, 1))
        assert query.matches(sample_record)

    def test_since_filter_excludes(self, sample_record):
        """Test since filter excludes record before date."""
        query = AnalyticsQuery(since=datetime(2024, 12, 10))
        assert not query.matches(sample_record)

    def test_until_filter_matches(self, sample_record):
        """Test until filter matches record before date."""
        query = AnalyticsQuery(until=datetime(2024, 12, 10))
        assert query.matches(sample_record)

    def test_until_filter_excludes(self, sample_record):
        """Test until filter excludes record after date."""
        query = AnalyticsQuery(until=datetime(2024, 12, 1))
        assert not query.matches(sample_record)

    def test_status_filter_matches(self, sample_record):
        """Test status filter matches."""
        query = AnalyticsQuery(status=ExecutionStatus.SUCCESS)
        assert query.matches(sample_record)

    def test_status_filter_excludes(self, sample_record):
        """Test status filter excludes non-matching."""
        query = AnalyticsQuery(status=ExecutionStatus.FAILED)
        assert not query.matches(sample_record)

    def test_document_filter_matches(self, sample_record):
        """Test document filter matches substring."""
        query = AnalyticsQuery(document="reverse")
        assert query.matches(sample_record)

    def test_document_filter_case_insensitive(self, sample_record):
        """Test document filter is case insensitive."""
        query = AnalyticsQuery(document="REVERSE")
        assert query.matches(sample_record)

    def test_document_filter_excludes(self, sample_record):
        """Test document filter excludes non-matching."""
        query = AnalyticsQuery(document="analytics")
        assert not query.matches(sample_record)

    def test_combined_filters(self, sample_record):
        """Test multiple filters combined."""
        query = AnalyticsQuery(
            since=datetime(2024, 12, 1),
            until=datetime(2024, 12, 31),
            status=ExecutionStatus.SUCCESS,
            document="reverse",
        )
        assert query.matches(sample_record)

    def test_to_dict(self):
        """Test serialization."""
        query = AnalyticsQuery(
            limit=10,
            since=datetime(2024, 12, 1),
            status=ExecutionStatus.SUCCESS,
        )
        data = query.to_dict()
        assert data["limit"] == 10
        assert data["since"] == "2024-12-01T00:00:00"
        assert data["status"] == "success"


# =============================================================================
# Exception Tests
# =============================================================================


class TestExceptions:
    """Tests for exception classes."""

    def test_analytics_error_is_exception(self):
        """Test AnalyticsError is an Exception."""
        assert issubclass(AnalyticsError, Exception)

    def test_storage_error_is_analytics_error(self):
        """Test StorageError inherits from AnalyticsError."""
        assert issubclass(StorageError, AnalyticsError)

    def test_import_error_is_analytics_error(self):
        """Test ImportError inherits from AnalyticsError."""
        assert issubclass(ImportError, AnalyticsError)

    def test_query_error_is_analytics_error(self):
        """Test QueryError inherits from AnalyticsError."""
        assert issubclass(QueryError, AnalyticsError)

    def test_raise_storage_error(self):
        """Test raising StorageError."""
        with pytest.raises(StorageError):
            raise StorageError("Cannot write file")


# =============================================================================
# Storage Tests
# =============================================================================


class TestStorageOperations:
    """Tests for storage operations."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project = tmp_path / "TestProject"
        project.mkdir()
        return project

    @pytest.fixture
    def sample_record(self):
        """Create a sample execution record."""
        return ExecutionRecord(
            execution_id="12345678-1234-1234-1234-123456789abc",
            audit_document="document-7-reverse.md",
            document_title="Document 7: Reverse Audit",
            project_name="Phaser",
            project_path="/Users/jp/Projects/Phaser",
            branch="audit/2024-12-06-reverse",
            started_at=datetime(2024, 12, 6, 10, 0, 0),
            completed_at=datetime(2024, 12, 6, 11, 30, 0),
            phaser_version="1.6.3",
            status=ExecutionStatus.SUCCESS,
            phases_planned=6,
            phases_completed=6,
            baseline_tests=280,
            final_tests=312,
            base_commit="aaa111",
            final_commit="bbb222",
            commit_count=7,
            files_changed=12,
        )

    def test_get_analytics_dir(self, temp_project):
        """Test analytics directory path."""
        from tools.analytics import get_analytics_dir
        path = get_analytics_dir(temp_project)
        assert path == temp_project / ".phaser" / "analytics"

    def test_get_executions_dir(self, temp_project):
        """Test executions directory path."""
        from tools.analytics import get_executions_dir
        path = get_executions_dir(temp_project)
        assert path == temp_project / ".phaser" / "analytics" / "executions"

    def test_get_index_path(self, temp_project):
        """Test index file path."""
        from tools.analytics import get_index_path
        path = get_index_path(temp_project)
        assert path == temp_project / ".phaser" / "analytics" / "index.json"

    def test_ensure_analytics_dir_creates(self, temp_project):
        """Test directory creation."""
        from tools.analytics import ensure_analytics_dir, get_executions_dir
        ensure_analytics_dir(temp_project)
        assert get_executions_dir(temp_project).exists()

    def test_ensure_analytics_dir_idempotent(self, temp_project):
        """Test directory creation is idempotent."""
        from tools.analytics import ensure_analytics_dir
        ensure_analytics_dir(temp_project)
        ensure_analytics_dir(temp_project)  # Should not raise

    def test_generate_execution_filename(self, sample_record):
        """Test filename generation."""
        from tools.analytics import generate_execution_filename
        filename = generate_execution_filename(sample_record)
        assert filename == "2024-12-06T10-00-00-12345678.json"

    def test_save_execution_creates_file(self, temp_project, sample_record):
        """Test saving creates file."""
        from tools.analytics import save_execution, get_executions_dir
        filepath = save_execution(sample_record, temp_project)
        assert filepath.exists()
        assert filepath.parent == get_executions_dir(temp_project)

    def test_save_execution_updates_index(self, temp_project, sample_record):
        """Test saving updates index."""
        from tools.analytics import save_execution, get_index_path
        save_execution(sample_record, temp_project)
        index_path = get_index_path(temp_project)
        assert index_path.exists()

    def test_load_execution_returns_record(self, temp_project, sample_record):
        """Test loading returns correct record."""
        from tools.analytics import save_execution, load_execution
        save_execution(sample_record, temp_project)
        loaded = load_execution(sample_record.execution_id, temp_project)
        assert loaded.execution_id == sample_record.execution_id
        assert loaded.audit_document == sample_record.audit_document
        assert loaded.status == sample_record.status

    def test_load_execution_not_found(self, temp_project):
        """Test loading non-existent record raises error."""
        from tools.analytics import load_execution, ensure_analytics_dir
        ensure_analytics_dir(temp_project)
        with pytest.raises(StorageError, match="not found"):
            load_execution("nonexistent-id", temp_project)

    def test_load_execution_no_analytics_dir(self, temp_project):
        """Test loading from project without analytics."""
        from tools.analytics import load_execution
        with pytest.raises(StorageError, match="No analytics data"):
            load_execution("any-id", temp_project)

    def test_delete_execution_removes_file(self, temp_project, sample_record):
        """Test deleting removes file."""
        from tools.analytics import save_execution, delete_execution, get_executions_dir
        save_execution(sample_record, temp_project)
        delete_execution(sample_record.execution_id, temp_project)
        files = list(get_executions_dir(temp_project).glob("*.json"))
        assert len(files) == 0

    def test_delete_execution_updates_index(self, temp_project, sample_record):
        """Test deleting updates index."""
        from tools.analytics import save_execution, delete_execution, load_index
        save_execution(sample_record, temp_project)
        delete_execution(sample_record.execution_id, temp_project)
        index = load_index(temp_project)
        assert index["execution_count"] == 0

    def test_delete_execution_not_found(self, temp_project):
        """Test deleting non-existent record raises error."""
        from tools.analytics import delete_execution, ensure_analytics_dir
        ensure_analytics_dir(temp_project)
        with pytest.raises(StorageError, match="not found"):
            delete_execution("nonexistent-id", temp_project)

    def test_list_executions_empty(self, temp_project):
        """Test listing empty analytics."""
        from tools.analytics import list_executions
        records = list_executions(temp_project)
        assert records == []

    def test_list_executions_returns_records(self, temp_project, sample_record):
        """Test listing returns saved records."""
        from tools.analytics import save_execution, list_executions
        save_execution(sample_record, temp_project)
        records = list_executions(temp_project)
        assert len(records) == 1
        assert records[0].execution_id == sample_record.execution_id

    def test_list_executions_sorted_by_date(self, temp_project):
        """Test listing returns records sorted by date."""
        from tools.analytics import save_execution, list_executions

        record1 = ExecutionRecord(
            execution_id="record-1",
            audit_document="doc1.md",
            document_title="Doc 1",
            project_name="Test",
            project_path="/test",
            branch="b1",
            started_at=datetime(2024, 12, 1, 10, 0, 0),
            completed_at=datetime(2024, 12, 1, 11, 0, 0),
            phaser_version="1.0",
            status=ExecutionStatus.SUCCESS,
            phases_planned=1,
            phases_completed=1,
            baseline_tests=100,
            final_tests=110,
            base_commit="a",
            final_commit="b",
            commit_count=1,
            files_changed=1,
        )
        record2 = ExecutionRecord(
            execution_id="record-2",
            audit_document="doc2.md",
            document_title="Doc 2",
            project_name="Test",
            project_path="/test",
            branch="b2",
            started_at=datetime(2024, 12, 5, 10, 0, 0),
            completed_at=datetime(2024, 12, 5, 11, 0, 0),
            phaser_version="1.0",
            status=ExecutionStatus.SUCCESS,
            phases_planned=1,
            phases_completed=1,
            baseline_tests=110,
            final_tests=120,
            base_commit="b",
            final_commit="c",
            commit_count=1,
            files_changed=1,
        )

        save_execution(record1, temp_project)
        save_execution(record2, temp_project)

        records = list_executions(temp_project)
        assert len(records) == 2
        assert records[0].execution_id == "record-2"  # Newer first
        assert records[1].execution_id == "record-1"

    def test_update_index_creates_index(self, temp_project, sample_record):
        """Test update_index creates index file."""
        from tools.analytics import save_execution, get_index_path
        save_execution(sample_record, temp_project)
        assert get_index_path(temp_project).exists()

    def test_load_index_returns_data(self, temp_project, sample_record):
        """Test load_index returns correct data."""
        from tools.analytics import save_execution, load_index
        save_execution(sample_record, temp_project)
        index = load_index(temp_project)
        assert index["execution_count"] == 1
        assert len(index["executions"]) == 1
        assert "stats" in index

    def test_load_index_empty_project(self, temp_project):
        """Test load_index on project without analytics."""
        from tools.analytics import load_index
        index = load_index(temp_project)
        assert index["execution_count"] == 0

    def test_clear_analytics_removes_all(self, temp_project, sample_record):
        """Test clear_analytics removes all data."""
        from tools.analytics import save_execution, clear_analytics, list_executions
        save_execution(sample_record, temp_project)
        count = clear_analytics(temp_project)
        assert count == 1
        assert list_executions(temp_project) == []

    def test_clear_analytics_returns_count(self, temp_project):
        """Test clear_analytics returns correct count."""
        from tools.analytics import save_execution, clear_analytics, ExecutionRecord

        for i in range(3):
            record = ExecutionRecord(
                execution_id=f"record-{i}",
                audit_document=f"doc{i}.md",
                document_title=f"Doc {i}",
                project_name="Test",
                project_path="/test",
                branch=f"b{i}",
                started_at=datetime(2024, 12, i + 1, 10, 0, 0),
                completed_at=datetime(2024, 12, i + 1, 11, 0, 0),
                phaser_version="1.0",
                status=ExecutionStatus.SUCCESS,
                phases_planned=1,
                phases_completed=1,
                baseline_tests=100,
                final_tests=110,
                base_commit="a",
                final_commit="b",
                commit_count=1,
                files_changed=1,
            )
            save_execution(record, temp_project)

        count = clear_analytics(temp_project)
        assert count == 3

    def test_clear_analytics_empty_project(self, temp_project):
        """Test clear_analytics on empty project."""
        from tools.analytics import clear_analytics
        count = clear_analytics(temp_project)
        assert count == 0


# =============================================================================
# Report Parsing Tests
# =============================================================================


class TestReportParsing:
    """Tests for report parsing functions."""

    @pytest.fixture
    def sample_report(self):
        """Load sample execution report."""
        from pathlib import Path
        fixture_path = Path(__file__).parent / "fixtures" / "sample_execution_report.md"
        return fixture_path.read_text()

    @pytest.fixture
    def temp_report(self, tmp_path, sample_report):
        """Create temporary report file."""
        report_path = tmp_path / "EXECUTION_REPORT.md"
        report_path.write_text(sample_report)
        return report_path

    def test_parse_metadata_table(self, sample_report):
        """Test metadata extraction."""
        from tools.analytics import parse_metadata_table
        metadata = parse_metadata_table(sample_report)
        assert metadata["Audit Document"] == "document-7-reverse.md"
        assert metadata["Document Title"] == "Document 7: Reverse Audit"
        assert metadata["Project"] == "Phaser"
        assert metadata["Branch"] == "audit/2024-12-06-reverse"
        assert metadata["Base Commit"] == "a1b2c3d4e5f6"
        assert metadata["Phaser Version"] == "1.6.3"

    def test_parse_metadata_table_empty(self):
        """Test parsing report without metadata."""
        from tools.analytics import parse_metadata_table
        metadata = parse_metadata_table("# No metadata here")
        assert metadata == {}

    def test_parse_phase_table(self, sample_report):
        """Test phase table extraction."""
        from tools.analytics import parse_phase_table
        phases = parse_phase_table(sample_report)
        assert len(phases) == 6
        assert phases[0]["phase_number"] == 36
        assert phases[0]["title"] == "Reverse Audit Specification"
        assert phases[0]["status"] == PhaseStatus.COMPLETED
        assert phases[0]["commit_sha"] == "b2c3d4e"

    def test_parse_phase_table_failed_phase(self):
        """Test parsing failed phase."""
        from tools.analytics import parse_phase_table
        content = """
## Execution Summary

| Phase | Title | Status | Commit |
|-------|-------|--------|--------|
| 1 | First Phase | ❌ |  |
"""
        phases = parse_phase_table(content)
        assert len(phases) == 1
        assert phases[0]["status"] == PhaseStatus.FAILED
        assert phases[0]["commit_sha"] is None

    def test_parse_test_results(self, sample_report):
        """Test test results extraction."""
        from tools.analytics import parse_test_results
        results = parse_test_results(sample_report)
        assert results["baseline"] == 280
        assert results["final"] == 312
        assert results["delta"] == 32

    def test_parse_test_results_negative_delta(self):
        """Test parsing negative test delta."""
        from tools.analytics import parse_test_results
        content = """
## Test Results

**Baseline:** 100 tests
**Final:** 95 tests
**Delta:** -5 tests
"""
        results = parse_test_results(content)
        assert results["delta"] == -5

    def test_parse_execution_result_success(self, sample_report):
        """Test parsing successful result."""
        from tools.analytics import parse_execution_result
        status, completed, planned = parse_execution_result(sample_report)
        assert status == ExecutionStatus.SUCCESS
        assert completed == 6
        assert planned == 6

    def test_parse_execution_result_partial(self):
        """Test parsing partial result."""
        from tools.analytics import parse_execution_result
        content = """
**Result:** ⚠️ Completed with issues

**Phases:** 4 of 6 completed
"""
        status, completed, planned = parse_execution_result(content)
        assert status == ExecutionStatus.PARTIAL
        assert completed == 4
        assert planned == 6

    def test_parse_git_info(self, sample_report):
        """Test git info extraction."""
        from tools.analytics import parse_git_info
        info = parse_git_info(sample_report)
        assert info["commit_count"] == 7
        assert info["files_changed"] == 12
        assert info["final_commit"] == "g7h8i9j"

    def test_parse_execution_report_full(self, sample_report):
        """Test full report parsing."""
        from tools.analytics import parse_execution_report
        data = parse_execution_report(sample_report)
        assert data["audit_document"] == "document-7-reverse.md"
        assert data["status"] == ExecutionStatus.SUCCESS
        assert data["phases_planned"] == 6
        assert data["baseline_tests"] == 280
        assert data["final_tests"] == 312
        assert len(data["phases"]) == 6

    def test_parse_execution_report_missing_metadata(self):
        """Test parsing report without metadata raises error."""
        from tools.analytics import parse_execution_report
        with pytest.raises(ImportError, match="Missing or invalid Metadata"):
            parse_execution_report("# No metadata")

    def test_import_execution_report(self, temp_report):
        """Test importing report creates record."""
        from tools.analytics import import_execution_report
        record = import_execution_report(temp_report)
        assert record.audit_document == "document-7-reverse.md"
        assert record.status == ExecutionStatus.SUCCESS
        assert record.baseline_tests == 280
        assert record.final_tests == 312
        assert len(record.phases) == 6

    def test_import_execution_report_not_found(self, tmp_path):
        """Test importing non-existent report raises error."""
        from tools.analytics import import_execution_report
        with pytest.raises(StorageError, match="not found"):
            import_execution_report(tmp_path / "missing.md")

    def test_import_execution_report_invalid(self, tmp_path):
        """Test importing invalid report raises error."""
        from tools.analytics import import_execution_report
        bad_report = tmp_path / "bad.md"
        bad_report.write_text("Not a valid report")
        with pytest.raises(ImportError):
            import_execution_report(bad_report)

    def test_import_creates_unique_id(self, temp_report):
        """Test each import creates unique ID."""
        from tools.analytics import import_execution_report
        record1 = import_execution_report(temp_report)
        record2 = import_execution_report(temp_report)
        assert record1.execution_id != record2.execution_id


# =============================================================================
# Query Tests
# =============================================================================


class TestQueryOperations:
    """Tests for query operations."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project = tmp_path / "TestProject"
        project.mkdir()
        return project

    @pytest.fixture
    def populated_project(self, temp_project):
        """Create project with sample data."""
        from tools.analytics import save_execution

        records = [
            ExecutionRecord(
                execution_id="success-1",
                audit_document="doc1.md",
                document_title="Doc 1",
                project_name="Test",
                project_path="/test",
                branch="b1",
                started_at=datetime(2024, 12, 1, 10, 0, 0),
                completed_at=datetime(2024, 12, 1, 11, 0, 0),
                phaser_version="1.0",
                status=ExecutionStatus.SUCCESS,
                phases_planned=3,
                phases_completed=3,
                baseline_tests=100,
                final_tests=120,
                base_commit="a",
                final_commit="b",
                commit_count=3,
                files_changed=5,
                phases=[
                    PhaseRecord(1, "P1", PhaseStatus.COMPLETED, "c1"),
                    PhaseRecord(2, "P2", PhaseStatus.COMPLETED, "c2"),
                    PhaseRecord(3, "P3", PhaseStatus.COMPLETED, "c3"),
                ],
            ),
            ExecutionRecord(
                execution_id="success-2",
                audit_document="doc2.md",
                document_title="Doc 2",
                project_name="Test",
                project_path="/test",
                branch="b2",
                started_at=datetime(2024, 12, 5, 10, 0, 0),
                completed_at=datetime(2024, 12, 5, 12, 0, 0),
                phaser_version="1.0",
                status=ExecutionStatus.SUCCESS,
                phases_planned=2,
                phases_completed=2,
                baseline_tests=120,
                final_tests=135,
                base_commit="b",
                final_commit="c",
                commit_count=2,
                files_changed=3,
            ),
            ExecutionRecord(
                execution_id="failed-1",
                audit_document="doc3.md",
                document_title="Doc 3",
                project_name="Test",
                project_path="/test",
                branch="b3",
                started_at=datetime(2024, 12, 10, 10, 0, 0),
                completed_at=datetime(2024, 12, 10, 10, 30, 0),
                phaser_version="1.0",
                status=ExecutionStatus.FAILED,
                phases_planned=4,
                phases_completed=1,
                baseline_tests=135,
                final_tests=138,
                base_commit="c",
                final_commit="d",
                commit_count=1,
                files_changed=2,
                phases=[
                    PhaseRecord(1, "Setup", PhaseStatus.COMPLETED, "c1"),
                    PhaseRecord(2, "Build", PhaseStatus.FAILED, None, error_message="Test failed"),
                    PhaseRecord(3, "Test", PhaseStatus.SKIPPED, None),
                    PhaseRecord(4, "Deploy", PhaseStatus.SKIPPED, None),
                ],
            ),
        ]

        for record in records:
            save_execution(record, temp_project)

        return temp_project

    def test_query_executions_all(self, populated_project):
        """Test querying all executions."""
        from tools.analytics import query_executions
        records = query_executions(populated_project)
        assert len(records) == 3

    def test_query_executions_with_limit(self, populated_project):
        """Test querying with limit."""
        from tools.analytics import query_executions
        query = AnalyticsQuery(limit=2)
        records = query_executions(populated_project, query)
        assert len(records) == 2

    def test_query_executions_by_status(self, populated_project):
        """Test querying by status."""
        from tools.analytics import query_executions
        query = AnalyticsQuery(status=ExecutionStatus.SUCCESS)
        records = query_executions(populated_project, query)
        assert len(records) == 2
        assert all(r.status == ExecutionStatus.SUCCESS for r in records)

    def test_query_executions_by_date_range(self, populated_project):
        """Test querying by date range."""
        from tools.analytics import query_executions
        query = AnalyticsQuery(
            since=datetime(2024, 12, 3),
            until=datetime(2024, 12, 8),
        )
        records = query_executions(populated_project, query)
        assert len(records) == 1
        assert records[0].audit_document == "doc2.md"

    def test_query_executions_by_document(self, populated_project):
        """Test querying by document name."""
        from tools.analytics import query_executions
        query = AnalyticsQuery(document="doc1")
        records = query_executions(populated_project, query)
        assert len(records) == 1
        assert records[0].audit_document == "doc1.md"

    def test_query_executions_combined(self, populated_project):
        """Test combined query parameters."""
        from tools.analytics import query_executions
        query = AnalyticsQuery(
            status=ExecutionStatus.SUCCESS,
            since=datetime(2024, 12, 1),
            limit=1,
        )
        records = query_executions(populated_project, query)
        assert len(records) == 1

    def test_query_executions_empty_result(self, populated_project):
        """Test query with no matches."""
        from tools.analytics import query_executions
        query = AnalyticsQuery(document="nonexistent")
        records = query_executions(populated_project, query)
        assert records == []

    def test_query_executions_sorted_by_date(self, populated_project):
        """Test results are sorted by date descending."""
        from tools.analytics import query_executions
        records = query_executions(populated_project)
        dates = [r.started_at for r in records]
        assert dates == sorted(dates, reverse=True)

    def test_compute_project_stats(self, populated_project):
        """Test computing project statistics."""
        from tools.analytics import compute_project_stats
        stats = compute_project_stats(populated_project)
        assert stats.total_executions == 3
        assert stats.successful == 2
        assert stats.failed == 1

    def test_get_failed_phases(self, populated_project):
        """Test getting failed phases."""
        from tools.analytics import get_failed_phases
        failures = get_failed_phases(populated_project)
        assert len(failures) == 1
        assert failures[0] == (2, "Build", 1)

    def test_get_failed_phases_empty(self, temp_project):
        """Test getting failed phases from empty project."""
        from tools.analytics import get_failed_phases
        failures = get_failed_phases(temp_project)
        assert failures == []

    def test_get_execution_by_document(self, populated_project):
        """Test getting execution by document name."""
        from tools.analytics import get_execution_by_document
        records = get_execution_by_document(populated_project, "doc1")
        assert len(records) == 1
        assert records[0].audit_document == "doc1.md"

    def test_get_recent_failures(self, populated_project):
        """Test getting recent failures."""
        from tools.analytics import get_recent_failures
        failures = get_recent_failures(populated_project)
        assert len(failures) == 1
        assert failures[0].status == ExecutionStatus.FAILED


# =============================================================================
# Formatting Tests
# =============================================================================


class TestOutputFormatting:
    """Tests for output formatting functions."""

    @pytest.fixture
    def sample_records(self):
        """Create sample records for formatting tests."""
        return [
            ExecutionRecord(
                execution_id="test-1",
                audit_document="document-7-reverse.md",
                document_title="Doc 7",
                project_name="Phaser",
                project_path="/test",
                branch="b1",
                started_at=datetime(2024, 12, 6, 10, 0, 0),
                completed_at=datetime(2024, 12, 6, 11, 30, 0),
                phaser_version="1.6.3",
                status=ExecutionStatus.SUCCESS,
                phases_planned=6,
                phases_completed=6,
                baseline_tests=280,
                final_tests=312,
                base_commit="aaa",
                final_commit="bbb",
                commit_count=7,
                files_changed=12,
                phases=[
                    PhaseRecord(1, "Phase One", PhaseStatus.COMPLETED, "abc1234"),
                    PhaseRecord(2, "Phase Two", PhaseStatus.COMPLETED, "def5678"),
                ],
            ),
            ExecutionRecord(
                execution_id="test-2",
                audit_document="document-8-analytics.md",
                document_title="Doc 8",
                project_name="Phaser",
                project_path="/test",
                branch="b2",
                started_at=datetime(2024, 12, 5, 14, 0, 0),
                completed_at=datetime(2024, 12, 5, 14, 45, 0),
                phaser_version="1.7.0",
                status=ExecutionStatus.FAILED,
                phases_planned=4,
                phases_completed=2,
                baseline_tests=312,
                final_tests=320,
                base_commit="bbb",
                final_commit="ccc",
                commit_count=2,
                files_changed=5,
            ),
        ]

    @pytest.fixture
    def sample_stats(self, sample_records):
        """Compute stats from sample records."""
        return AggregatedStats.compute(sample_records)

    def test_format_duration_seconds(self):
        """Test formatting seconds."""
        from tools.analytics import format_duration
        assert format_duration(45) == "45s"

    def test_format_duration_minutes(self):
        """Test formatting minutes."""
        from tools.analytics import format_duration
        assert format_duration(125) == "2m 5s"
        assert format_duration(120) == "2m"

    def test_format_duration_hours(self):
        """Test formatting hours."""
        from tools.analytics import format_duration
        assert format_duration(5400) == "1h 30m"
        assert format_duration(3600) == "1h"

    def test_format_table_basic(self, sample_records, sample_stats):
        """Test basic table formatting."""
        from tools.analytics import format_table
        output = format_table(sample_records, sample_stats)
        assert "document-7-reverse.md" in output
        assert "✅" in output
        assert "❌" in output
        assert "Summary:" in output

    def test_format_table_empty(self):
        """Test table formatting with no records."""
        from tools.analytics import format_table
        output = format_table([], AggregatedStats.empty())
        assert "No analytics data" in output

    def test_format_table_verbose(self, sample_records, sample_stats):
        """Test verbose table formatting."""
        from tools.analytics import format_table
        output = format_table(sample_records, sample_stats, verbose=True)
        assert "Phase 1:" in output
        assert "Phase One" in output

    def test_format_json_valid(self, sample_records, sample_stats):
        """Test JSON formatting produces valid JSON."""
        from tools.analytics import format_json
        output = format_json(sample_records, sample_stats)
        parsed = json.loads(output)
        assert "executions" in parsed
        assert len(parsed["executions"]) == 2

    def test_format_json_includes_stats(self, sample_records, sample_stats):
        """Test JSON includes statistics."""
        from tools.analytics import format_json
        output = format_json(sample_records, sample_stats)
        parsed = json.loads(output)
        assert "stats" in parsed
        assert parsed["stats"]["total_executions"] == 2

    def test_format_json_includes_query(self, sample_records, sample_stats):
        """Test JSON includes query context."""
        from tools.analytics import format_json
        query = AnalyticsQuery(limit=10, status=ExecutionStatus.SUCCESS)
        output = format_json(sample_records, sample_stats, query=query)
        parsed = json.loads(output)
        assert parsed["query"]["limit"] == 10
        assert parsed["query"]["status"] == "success"

    def test_format_markdown_sections(self, sample_records, sample_stats):
        """Test markdown has all sections."""
        from tools.analytics import format_markdown
        output = format_markdown(sample_records, sample_stats)
        assert "# " in output  # Title
        assert "## Summary" in output
        assert "## Recent Executions" in output
        assert "| Metric | Value |" in output

    def test_format_markdown_records(self, sample_records, sample_stats):
        """Test markdown includes record details."""
        from tools.analytics import format_markdown
        output = format_markdown(sample_records, sample_stats)
        assert "document-7-reverse.md" in output
        assert "280 → 312" in output

    def test_format_csv_header(self, sample_records):
        """Test CSV has header row."""
        from tools.analytics import format_csv
        output = format_csv(sample_records)
        lines = output.split("\n")
        assert "execution_id" in lines[0]
        assert "audit_document" in lines[0]
        assert "status" in lines[0]

    def test_format_csv_rows(self, sample_records):
        """Test CSV has data rows."""
        from tools.analytics import format_csv
        output = format_csv(sample_records)
        lines = output.split("\n")
        assert len(lines) == 3  # Header + 2 records

    def test_format_csv_escaping(self, sample_records):
        """Test CSV escapes document names."""
        from tools.analytics import format_csv
        output = format_csv(sample_records)
        assert '"document-7-reverse.md"' in output


# =============================================================================
# CLI Tests
# =============================================================================


class TestCLICommands:
    """Tests for CLI commands."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project = tmp_path / "TestProject"
        project.mkdir()
        return project

    @pytest.fixture
    def cli_runner(self):
        """Create CLI runner."""
        from click.testing import CliRunner
        return CliRunner()

    @pytest.fixture
    def populated_project(self, temp_project):
        """Create project with sample data."""
        from tools.analytics import save_execution

        record = ExecutionRecord(
            execution_id="cli-test-1",
            audit_document="test-doc.md",
            document_title="Test Doc",
            project_name="Test",
            project_path=str(temp_project),
            branch="test",
            started_at=datetime(2024, 12, 6, 10, 0, 0),
            completed_at=datetime(2024, 12, 6, 11, 0, 0),
            phaser_version="1.7.0",
            status=ExecutionStatus.SUCCESS,
            phases_planned=3,
            phases_completed=3,
            baseline_tests=100,
            final_tests=115,
            base_commit="aaa",
            final_commit="bbb",
            commit_count=3,
            files_changed=5,
        )
        save_execution(record, temp_project)
        return temp_project

    def test_analytics_show_default(self, cli_runner, populated_project):
        """Test analytics show command."""
        from tools.cli import cli
        result = cli_runner.invoke(cli, ["analytics", "show", "--project", str(populated_project)])
        assert result.exit_code == 0
        assert "test-doc.md" in result.output

    def test_analytics_show_json(self, cli_runner, populated_project):
        """Test analytics show with JSON format."""
        from tools.cli import cli
        result = cli_runner.invoke(cli, ["analytics", "show", "--format", "json", "--project", str(populated_project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "executions" in data
        assert len(data["executions"]) == 1

    def test_analytics_show_empty(self, cli_runner, temp_project):
        """Test analytics show with no data."""
        from tools.cli import cli
        result = cli_runner.invoke(cli, ["analytics", "show", "--project", str(temp_project)])
        assert result.exit_code == 0
        assert "No analytics data" in result.output

    def test_analytics_export_json(self, cli_runner, populated_project, tmp_path):
        """Test analytics export to file."""
        from tools.cli import cli
        output_file = tmp_path / "export.json"
        result = cli_runner.invoke(cli, [
            "analytics", "export",
            "--format", "json",
            "--output", str(output_file),
            "--project", str(populated_project),
        ])
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert len(data["executions"]) == 1

    def test_analytics_export_csv(self, cli_runner, populated_project):
        """Test analytics export as CSV."""
        from tools.cli import cli
        result = cli_runner.invoke(cli, [
            "analytics", "export",
            "--format", "csv",
            "--project", str(populated_project),
        ])
        assert result.exit_code == 0
        assert "execution_id" in result.output
        assert "test-doc.md" in result.output

    def test_analytics_clear_dry_run(self, cli_runner, populated_project):
        """Test analytics clear dry run."""
        from tools.cli import cli
        result = cli_runner.invoke(cli, [
            "analytics", "clear",
            "--all",
            "--dry-run",
            "--project", str(populated_project),
        ])
        assert result.exit_code == 0
        assert "Would delete" in result.output

    def test_analytics_clear_force(self, cli_runner, populated_project):
        """Test analytics clear with force."""
        from tools.cli import cli
        result = cli_runner.invoke(cli, [
            "analytics", "clear",
            "--all",
            "--force",
            "--project", str(populated_project),
        ])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_analytics_clear_requires_option(self, cli_runner, populated_project):
        """Test analytics clear requires --all or --before."""
        from tools.cli import cli
        result = cli_runner.invoke(cli, [
            "analytics", "clear",
            "--project", str(populated_project),
        ])
        assert result.exit_code != 0
        assert "Must specify" in result.output

    def test_analytics_import_file(self, cli_runner, temp_project, tmp_path):
        """Test analytics import from file."""
        from tools.cli import cli
        from pathlib import Path

        # Create a sample report
        report_path = tmp_path / "EXECUTION_REPORT.md"
        fixture_path = Path(__file__).parent / "fixtures" / "sample_execution_report.md"
        report_path.write_text(fixture_path.read_text())

        result = cli_runner.invoke(cli, [
            "analytics", "import",
            str(report_path),
            "--project", str(temp_project),
        ])
        assert result.exit_code == 0
        assert "Imported" in result.output

    def test_analytics_import_directory(self, cli_runner, temp_project, tmp_path):
        """Test analytics import from directory."""
        from tools.cli import cli
        from pathlib import Path

        # Create sample reports in directory
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        fixture_path = Path(__file__).parent / "fixtures" / "sample_execution_report.md"
        (reports_dir / "EXECUTION_REPORT.md").write_text(fixture_path.read_text())

        result = cli_runner.invoke(cli, [
            "analytics", "import",
            str(reports_dir),
            "--project", str(temp_project),
        ])
        assert result.exit_code == 0
        assert "Imported 1" in result.output


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """End-to-end integration tests."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project = tmp_path / "IntegrationTestProject"
        project.mkdir()
        return project

    @pytest.fixture
    def sample_report_path(self):
        """Get path to sample report fixture."""
        from pathlib import Path
        return Path(__file__).parent / "fixtures" / "sample_execution_report.md"

    def test_full_workflow_import_query_export(self, temp_project, sample_report_path, tmp_path):
        """Test complete workflow: import → query → export."""
        from tools.analytics import (
            import_execution_report,
            save_execution,
            query_executions,
            compute_project_stats,
            format_json,
            AggregatedStats,
        )

        # Import
        record = import_execution_report(sample_report_path, temp_project)
        save_execution(record, temp_project)

        # Query
        records = query_executions(temp_project)
        assert len(records) == 1
        assert records[0].audit_document == "document-7-reverse.md"

        # Stats
        stats = compute_project_stats(temp_project)
        assert stats.total_executions == 1
        assert stats.successful == 1

        # Export
        output = format_json(records, stats)
        data = json.loads(output)
        assert data["stats"]["total_executions"] == 1

    def test_multiple_imports_aggregation(self, temp_project, sample_report_path):
        """Test importing multiple reports and aggregating."""
        from tools.analytics import (
            import_execution_report,
            save_execution,
            compute_project_stats,
            ExecutionRecord,
            ExecutionStatus,
        )

        # Import first report
        record1 = import_execution_report(sample_report_path, temp_project)
        save_execution(record1, temp_project)

        # Create and save a second record
        record2 = ExecutionRecord(
            execution_id=ExecutionRecord.generate_id(),
            audit_document="another-doc.md",
            document_title="Another Doc",
            project_name="Test",
            project_path=str(temp_project),
            branch="test2",
            started_at=datetime(2024, 12, 7, 10, 0, 0),
            completed_at=datetime(2024, 12, 7, 11, 0, 0),
            phaser_version="1.7.0",
            status=ExecutionStatus.SUCCESS,
            phases_planned=3,
            phases_completed=3,
            baseline_tests=312,
            final_tests=350,
            base_commit="x",
            final_commit="y",
            commit_count=3,
            files_changed=8,
        )
        save_execution(record2, temp_project)

        # Verify aggregation
        stats = compute_project_stats(temp_project)
        assert stats.total_executions == 2
        assert stats.successful == 2
        assert stats.total_test_delta == 32 + 38  # Both deltas

    def test_clear_and_reimport(self, temp_project, sample_report_path):
        """Test clearing data and reimporting."""
        from tools.analytics import (
            import_execution_report,
            save_execution,
            clear_analytics,
            list_executions,
        )

        # Import
        record = import_execution_report(sample_report_path, temp_project)
        save_execution(record, temp_project)
        assert len(list_executions(temp_project)) == 1

        # Clear
        count = clear_analytics(temp_project)
        assert count == 1
        assert len(list_executions(temp_project)) == 0

        # Reimport
        record = import_execution_report(sample_report_path, temp_project)
        save_execution(record, temp_project)
        assert len(list_executions(temp_project)) == 1

    def test_query_filter_combinations(self, temp_project):
        """Test various query filter combinations."""
        from tools.analytics import (
            save_execution,
            query_executions,
            AnalyticsQuery,
            ExecutionRecord,
            ExecutionStatus,
        )

        # Create records with different dates and statuses
        for i, (days_ago, status) in enumerate([
            (10, ExecutionStatus.SUCCESS),
            (5, ExecutionStatus.FAILED),
            (3, ExecutionStatus.SUCCESS),
            (1, ExecutionStatus.PARTIAL),
        ]):
            record = ExecutionRecord(
                execution_id=f"query-test-{i}",
                audit_document=f"doc-{i}.md",
                document_title=f"Doc {i}",
                project_name="Test",
                project_path=str(temp_project),
                branch=f"b{i}",
                started_at=datetime(2024, 12, 1) + timedelta(days=10 - days_ago),
                completed_at=datetime(2024, 12, 1) + timedelta(days=10 - days_ago, hours=1),
                phaser_version="1.7.0",
                status=status,
                phases_planned=3,
                phases_completed=3 if status == ExecutionStatus.SUCCESS else 1,
                baseline_tests=100,
                final_tests=110,
                base_commit="a",
                final_commit="b",
                commit_count=3,
                files_changed=5,
            )
            save_execution(record, temp_project)

        # Test various queries
        all_records = query_executions(temp_project)
        assert len(all_records) == 4

        success_only = query_executions(temp_project, AnalyticsQuery(status=ExecutionStatus.SUCCESS))
        assert len(success_only) == 2

        recent = query_executions(temp_project, AnalyticsQuery(since=datetime(2024, 12, 8)))
        assert len(recent) == 2

        limited = query_executions(temp_project, AnalyticsQuery(limit=2))
        assert len(limited) == 2

    def test_cli_full_workflow(self, temp_project, sample_report_path, tmp_path):
        """Test full workflow through CLI."""
        from click.testing import CliRunner
        from tools.cli import cli

        runner = CliRunner()

        # Import via CLI
        result = runner.invoke(cli, [
            "analytics", "import",
            str(sample_report_path),
            "--project", str(temp_project),
        ])
        assert result.exit_code == 0
        assert "Imported" in result.output

        # Show via CLI
        result = runner.invoke(cli, [
            "analytics", "show",
            "--format", "json",
            "--project", str(temp_project),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["executions"]) == 1

        # Export via CLI
        export_path = tmp_path / "export.json"
        result = runner.invoke(cli, [
            "analytics", "export",
            "--output", str(export_path),
            "--project", str(temp_project),
        ])
        assert result.exit_code == 0
        assert export_path.exists()

        # Clear via CLI
        result = runner.invoke(cli, [
            "analytics", "clear",
            "--all", "--force",
            "--project", str(temp_project),
        ])
        assert result.exit_code == 0
        assert "Deleted" in result.output
