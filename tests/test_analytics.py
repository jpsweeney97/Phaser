"""Tests for analytics module."""

from datetime import datetime, timedelta

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
        now = datetime.utcnow()
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
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
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
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
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
