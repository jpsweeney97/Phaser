"""
Analytics - Execution metrics and historical tracking for Phaser.

This module provides functionality to capture, store, query, and report
on audit execution metrics.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# Constants
# =============================================================================

ANALYTICS_SCHEMA_VERSION = "1.0"
ANALYTICS_DIR_NAME = ".phaser"
EXECUTIONS_DIR_NAME = "executions"
INDEX_FILENAME = "index.json"


# =============================================================================
# Exceptions
# =============================================================================


class AnalyticsError(Exception):
    """Base exception for analytics operations."""

    pass


class StorageError(AnalyticsError):
    """Error reading or writing analytics data."""

    pass


class ImportError(AnalyticsError):
    """Error importing execution report."""

    pass


class QueryError(AnalyticsError):
    """Error executing analytics query."""

    pass


# =============================================================================
# Enums
# =============================================================================


class ExecutionStatus(str, Enum):
    """Status of an audit execution."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"

    @classmethod
    def from_report(cls, result_text: str) -> "ExecutionStatus":
        """Parse status from execution report result line."""
        if "All phases completed" in result_text:
            return cls.SUCCESS
        elif "Completed with issues" in result_text or "partial" in result_text.lower():
            return cls.PARTIAL
        else:
            return cls.FAILED


class PhaseStatus(str, Enum):
    """Status of a single phase."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    @classmethod
    def from_symbol(cls, symbol: str) -> "PhaseStatus":
        """Parse status from table symbol."""
        if "✅" in symbol:
            return cls.COMPLETED
        elif "❌" in symbol:
            return cls.FAILED
        else:
            return cls.SKIPPED


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class PhaseRecord:
    """Record of a single phase within an execution."""

    phase_number: int
    title: str
    status: PhaseStatus
    commit_sha: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None

    tests_before: int | None = None
    tests_after: int | None = None

    error_message: str | None = None
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "phase_number": self.phase_number,
            "title": self.title,
            "status": self.status.value,
            "commit_sha": self.commit_sha,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "tests_before": self.tests_before,
            "tests_after": self.tests_after,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhaseRecord":
        """Deserialize from dictionary."""
        return cls(
            phase_number=data["phase_number"],
            title=data["title"],
            status=PhaseStatus(data["status"]),
            commit_sha=data.get("commit_sha"),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            duration_seconds=data.get("duration_seconds"),
            tests_before=data.get("tests_before"),
            tests_after=data.get("tests_after"),
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class ExecutionRecord:
    """Complete record of a single audit execution."""

    # Identity
    execution_id: str
    audit_document: str
    document_title: str

    # Location
    project_name: str
    project_path: str
    branch: str

    # Timing
    started_at: datetime
    completed_at: datetime

    # Versions
    phaser_version: str

    # Results
    status: ExecutionStatus
    phases_planned: int
    phases_completed: int

    # Tests
    baseline_tests: int
    final_tests: int

    # Git
    base_commit: str
    final_commit: str
    commit_count: int
    files_changed: int

    # Phases
    phases: list[PhaseRecord] = field(default_factory=list)

    # Raw
    report_path: str = ""
    imported_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def duration_seconds(self) -> float:
        """Compute duration from timestamps."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def test_delta(self) -> int:
        """Compute test delta."""
        return self.final_tests - self.baseline_tests

    @property
    def success_rate(self) -> float:
        """Phase success rate."""
        if self.phases_planned == 0:
            return 0.0
        return self.phases_completed / self.phases_planned

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "schema_version": ANALYTICS_SCHEMA_VERSION,
            "execution_id": self.execution_id,
            "audit_document": self.audit_document,
            "document_title": self.document_title,
            "project_name": self.project_name,
            "project_path": self.project_path,
            "branch": self.branch,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "phaser_version": self.phaser_version,
            "status": self.status.value,
            "phases_planned": self.phases_planned,
            "phases_completed": self.phases_completed,
            "baseline_tests": self.baseline_tests,
            "final_tests": self.final_tests,
            "test_delta": self.test_delta,
            "base_commit": self.base_commit,
            "final_commit": self.final_commit,
            "commit_count": self.commit_count,
            "files_changed": self.files_changed,
            "phases": [p.to_dict() for p in self.phases],
            "report_path": self.report_path,
            "imported_at": self.imported_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionRecord":
        """Deserialize from dictionary."""
        return cls(
            execution_id=data["execution_id"],
            audit_document=data["audit_document"],
            document_title=data["document_title"],
            project_name=data["project_name"],
            project_path=data["project_path"],
            branch=data["branch"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]),
            phaser_version=data["phaser_version"],
            status=ExecutionStatus(data["status"]),
            phases_planned=data["phases_planned"],
            phases_completed=data["phases_completed"],
            baseline_tests=data["baseline_tests"],
            final_tests=data["final_tests"],
            base_commit=data["base_commit"],
            final_commit=data["final_commit"],
            commit_count=data["commit_count"],
            files_changed=data["files_changed"],
            phases=[PhaseRecord.from_dict(p) for p in data.get("phases", [])],
            report_path=data.get("report_path", ""),
            imported_at=(
                datetime.fromisoformat(data["imported_at"])
                if data.get("imported_at")
                else datetime.utcnow()
            ),
        )

    @classmethod
    def generate_id(cls) -> str:
        """Generate a new execution ID."""
        return str(uuid.uuid4())


@dataclass
class AggregatedStats:
    """Computed statistics across multiple executions."""

    total_executions: int
    successful: int
    partial: int
    failed: int

    avg_duration_seconds: float
    min_duration_seconds: float
    max_duration_seconds: float
    total_duration_seconds: float

    total_test_delta: int
    avg_test_delta: float

    total_phases_executed: int
    total_phases_completed: int

    earliest_execution: datetime | None
    latest_execution: datetime | None

    @property
    def success_rate(self) -> float:
        """Overall success rate."""
        if self.total_executions == 0:
            return 0.0
        return self.successful / self.total_executions

    @property
    def phase_success_rate(self) -> float:
        """Phase-level success rate."""
        if self.total_phases_executed == 0:
            return 0.0
        return self.total_phases_completed / self.total_phases_executed

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_executions": self.total_executions,
            "successful": self.successful,
            "partial": self.partial,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "avg_duration_seconds": self.avg_duration_seconds,
            "min_duration_seconds": self.min_duration_seconds,
            "max_duration_seconds": self.max_duration_seconds,
            "total_duration_seconds": self.total_duration_seconds,
            "total_test_delta": self.total_test_delta,
            "avg_test_delta": self.avg_test_delta,
            "total_phases_executed": self.total_phases_executed,
            "total_phases_completed": self.total_phases_completed,
            "phase_success_rate": self.phase_success_rate,
            "earliest_execution": (
                self.earliest_execution.isoformat() if self.earliest_execution else None
            ),
            "latest_execution": (
                self.latest_execution.isoformat() if self.latest_execution else None
            ),
        }

    @classmethod
    def empty(cls) -> "AggregatedStats":
        """Create empty stats."""
        return cls(
            total_executions=0,
            successful=0,
            partial=0,
            failed=0,
            avg_duration_seconds=0.0,
            min_duration_seconds=0.0,
            max_duration_seconds=0.0,
            total_duration_seconds=0.0,
            total_test_delta=0,
            avg_test_delta=0.0,
            total_phases_executed=0,
            total_phases_completed=0,
            earliest_execution=None,
            latest_execution=None,
        )

    @classmethod
    def compute(cls, records: list[ExecutionRecord]) -> "AggregatedStats":
        """Compute statistics from a list of execution records."""
        if not records:
            return cls.empty()

        durations = [r.duration_seconds for r in records]
        test_deltas = [r.test_delta for r in records]
        timestamps = [r.started_at for r in records]

        return cls(
            total_executions=len(records),
            successful=sum(
                1 for r in records if r.status == ExecutionStatus.SUCCESS
            ),
            partial=sum(
                1 for r in records if r.status == ExecutionStatus.PARTIAL
            ),
            failed=sum(
                1 for r in records if r.status == ExecutionStatus.FAILED
            ),
            avg_duration_seconds=sum(durations) / len(durations),
            min_duration_seconds=min(durations),
            max_duration_seconds=max(durations),
            total_duration_seconds=sum(durations),
            total_test_delta=sum(test_deltas),
            avg_test_delta=sum(test_deltas) / len(test_deltas),
            total_phases_executed=sum(r.phases_planned for r in records),
            total_phases_completed=sum(r.phases_completed for r in records),
            earliest_execution=min(timestamps),
            latest_execution=max(timestamps),
        )


@dataclass
class AnalyticsQuery:
    """Query parameters for analytics data."""

    limit: int | None = None
    since: datetime | None = None
    until: datetime | None = None
    status: ExecutionStatus | None = None
    document: str | None = None

    def matches(self, record: ExecutionRecord) -> bool:
        """Check if a record matches this query."""
        if self.since and record.started_at < self.since:
            return False
        if self.until and record.started_at > self.until:
            return False
        if self.status and record.status != self.status:
            return False
        if self.document and self.document.lower() not in record.audit_document.lower():
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "limit": self.limit,
            "since": self.since.isoformat() if self.since else None,
            "until": self.until.isoformat() if self.until else None,
            "status": self.status.value if self.status else None,
            "document": self.document,
        }


# =============================================================================
# Storage Operations
# =============================================================================


def get_analytics_dir(project_dir: Path) -> Path:
    """
    Get the analytics directory for a project.

    Args:
        project_dir: Project root directory

    Returns:
        Path to .phaser/analytics/ directory
    """
    return project_dir / ANALYTICS_DIR_NAME / "analytics"


def get_executions_dir(project_dir: Path) -> Path:
    """
    Get the executions subdirectory.

    Args:
        project_dir: Project root directory

    Returns:
        Path to .phaser/analytics/executions/ directory
    """
    return get_analytics_dir(project_dir) / EXECUTIONS_DIR_NAME


def get_index_path(project_dir: Path) -> Path:
    """
    Get the index file path.

    Args:
        project_dir: Project root directory

    Returns:
        Path to .phaser/analytics/index.json
    """
    return get_analytics_dir(project_dir) / INDEX_FILENAME


def ensure_analytics_dir(project_dir: Path) -> Path:
    """
    Ensure analytics directory structure exists.

    Args:
        project_dir: Project root directory

    Returns:
        Path to .phaser/analytics/ directory (created if needed)
    """
    analytics_dir = get_analytics_dir(project_dir)
    analytics_dir.mkdir(parents=True, exist_ok=True)
    get_executions_dir(project_dir).mkdir(exist_ok=True)
    return analytics_dir


def generate_execution_filename(record: ExecutionRecord) -> str:
    """
    Generate filename for an execution record.

    Format: {timestamp}-{short_id}.json

    Args:
        record: ExecutionRecord to generate filename for

    Returns:
        Filename string
    """
    timestamp = record.started_at.strftime("%Y-%m-%dT%H-%M-%S")
    short_id = record.execution_id[:8]
    return f"{timestamp}-{short_id}.json"


def save_execution(record: ExecutionRecord, project_dir: Path) -> Path:
    """
    Save an execution record to disk.

    Args:
        record: ExecutionRecord to save
        project_dir: Project root directory

    Returns:
        Path to saved JSON file

    Raises:
        StorageError: If write fails
    """
    ensure_analytics_dir(project_dir)
    executions_dir = get_executions_dir(project_dir)

    filename = generate_execution_filename(record)
    filepath = executions_dir / filename

    try:
        with open(filepath, "w") as f:
            json.dump(record.to_dict(), f, indent=2)
    except OSError as e:
        raise StorageError(f"Failed to save execution record: {e}")

    # Update index
    update_index(project_dir)

    return filepath


def load_execution(execution_id: str, project_dir: Path) -> ExecutionRecord:
    """
    Load an execution record from disk.

    Args:
        execution_id: UUID of execution to load
        project_dir: Project root directory

    Returns:
        ExecutionRecord

    Raises:
        StorageError: If record not found or read fails
    """
    executions_dir = get_executions_dir(project_dir)

    if not executions_dir.exists():
        raise StorageError(f"No analytics data found in {project_dir}")

    # Search for file containing execution_id
    for filepath in executions_dir.glob("*.json"):
        if execution_id[:8] in filepath.name:
            try:
                with open(filepath) as f:
                    data = json.load(f)
                if data.get("execution_id") == execution_id:
                    return ExecutionRecord.from_dict(data)
            except (OSError, json.JSONDecodeError):
                continue

    raise StorageError(f"Execution not found: {execution_id}")


def load_execution_by_path(filepath: Path) -> ExecutionRecord:
    """
    Load an execution record from a specific file.

    Args:
        filepath: Path to JSON file

    Returns:
        ExecutionRecord

    Raises:
        StorageError: If read fails
    """
    try:
        with open(filepath) as f:
            data = json.load(f)
        return ExecutionRecord.from_dict(data)
    except OSError as e:
        raise StorageError(f"Failed to read execution file: {e}")
    except (json.JSONDecodeError, KeyError) as e:
        raise StorageError(f"Invalid execution file format: {e}")


def delete_execution(execution_id: str, project_dir: Path) -> None:
    """
    Delete an execution record.

    Args:
        execution_id: UUID of execution to delete
        project_dir: Project root directory

    Raises:
        StorageError: If record not found or delete fails
    """
    executions_dir = get_executions_dir(project_dir)

    if not executions_dir.exists():
        raise StorageError(f"No analytics data found in {project_dir}")

    # Search for file containing execution_id
    for filepath in executions_dir.glob("*.json"):
        if execution_id[:8] in filepath.name:
            try:
                with open(filepath) as f:
                    data = json.load(f)
                if data.get("execution_id") == execution_id:
                    filepath.unlink()
                    update_index(project_dir)
                    return
            except (OSError, json.JSONDecodeError):
                continue

    raise StorageError(f"Execution not found: {execution_id}")


def list_executions(project_dir: Path) -> list[ExecutionRecord]:
    """
    List all execution records in a project.

    Args:
        project_dir: Project root directory

    Returns:
        List of ExecutionRecords, sorted by start time descending
    """
    executions_dir = get_executions_dir(project_dir)

    if not executions_dir.exists():
        return []

    records = []
    for filepath in executions_dir.glob("*.json"):
        try:
            record = load_execution_by_path(filepath)
            records.append(record)
        except StorageError:
            continue

    # Sort by start time, newest first
    records.sort(key=lambda r: r.started_at, reverse=True)
    return records


def update_index(project_dir: Path) -> None:
    """
    Rebuild the analytics index from execution files.

    Args:
        project_dir: Project root directory
    """
    records = list_executions(project_dir)
    stats = AggregatedStats.compute(records)

    index_data = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "project_name": project_dir.name,
        "updated_at": datetime.utcnow().isoformat(),
        "execution_count": len(records),
        "executions": [
            {
                "execution_id": r.execution_id,
                "filename": generate_execution_filename(r),
                "audit_document": r.audit_document,
                "started_at": r.started_at.isoformat(),
                "status": r.status.value,
                "duration_seconds": r.duration_seconds,
                "test_delta": r.test_delta,
            }
            for r in records
        ],
        "stats": stats.to_dict(),
    }

    index_path = get_index_path(project_dir)
    ensure_analytics_dir(project_dir)

    try:
        with open(index_path, "w") as f:
            json.dump(index_data, f, indent=2)
    except OSError as e:
        raise StorageError(f"Failed to update index: {e}")


def load_index(project_dir: Path) -> dict[str, Any]:
    """
    Load the analytics index.

    Args:
        project_dir: Project root directory

    Returns:
        Index data dictionary

    Raises:
        StorageError: If index not found or invalid
    """
    index_path = get_index_path(project_dir)

    if not index_path.exists():
        return {
            "schema_version": ANALYTICS_SCHEMA_VERSION,
            "project_name": project_dir.name,
            "execution_count": 0,
            "executions": [],
            "stats": AggregatedStats.empty().to_dict(),
        }

    try:
        with open(index_path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise StorageError(f"Failed to load index: {e}")


def clear_analytics(project_dir: Path) -> int:
    """
    Clear all analytics data for a project.

    Args:
        project_dir: Project root directory

    Returns:
        Number of records deleted
    """
    executions_dir = get_executions_dir(project_dir)

    if not executions_dir.exists():
        return 0

    count = 0
    for filepath in executions_dir.glob("*.json"):
        filepath.unlink()
        count += 1

    # Clear index
    index_path = get_index_path(project_dir)
    if index_path.exists():
        index_path.unlink()

    return count
