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


# =============================================================================
# Report Parsing
# =============================================================================

# Patterns for parsing execution reports
METADATA_TABLE_PATTERN = re.compile(
    r"\|\s*(?P<field>[^|]+?)\s*\|\s*(?P<value>[^|]+?)\s*\|"
)
PHASE_ROW_PATTERN = re.compile(
    r"\|\s*(?P<number>\d+)\s*\|\s*(?P<title>[^|]+?)\s*\|\s*(?P<status>[✅⚠️❌][^\|]*)\s*\|\s*(?P<commit>[a-zA-Z0-9]*)\s*\|"
)
TEST_COUNT_PATTERN = re.compile(r"(\d+)\s*(?:tests?|passed)")
RESULT_PATTERN = re.compile(r"\*\*Result:\*\*\s*(.+)")
PHASES_SUMMARY_PATTERN = re.compile(r"\*\*Phases:\*\*\s*(\d+)\s*of\s*(\d+)")
FILES_CHANGED_PATTERN = re.compile(r"(\d+)\s*files?\s*changed")
COMMITS_COUNT_PATTERN = re.compile(r"\*\*Commits:\*\*\s*(\d+)")


def parse_metadata_table(content: str) -> dict[str, str]:
    """
    Extract key-value pairs from Metadata table.

    Args:
        content: Full report content

    Returns:
        Dictionary of metadata fields
    """
    metadata = {}
    in_metadata = False
    header_skipped = False

    for line in content.split("\n"):
        if "## Metadata" in line:
            in_metadata = True
            continue
        if in_metadata and line.startswith("## "):
            break
        if in_metadata:
            match = METADATA_TABLE_PATTERN.match(line)
            if match:
                field = match.group("field").strip()
                value = match.group("value").strip()
                # Skip header row and separator
                if field in ("Field", "---", "-----", "-------"):
                    header_skipped = True
                    continue
                if header_skipped and field and value and value != "---":
                    metadata[field] = value

    return metadata


def parse_phase_table(content: str) -> list[dict[str, Any]]:
    """
    Extract phase details from Execution Summary table.

    Args:
        content: Full report content

    Returns:
        List of phase dictionaries
    """
    phases = []
    in_summary = False

    for line in content.split("\n"):
        if "## Execution Summary" in line:
            in_summary = True
            continue
        if in_summary and line.startswith("## "):
            break
        if in_summary:
            match = PHASE_ROW_PATTERN.match(line)
            if match:
                phases.append({
                    "phase_number": int(match.group("number")),
                    "title": match.group("title").strip(),
                    "status": PhaseStatus.from_symbol(match.group("status")),
                    "commit_sha": match.group("commit").strip() or None,
                })

    return phases


def parse_test_results(content: str) -> dict[str, int]:
    """
    Extract test counts from Test Results section.

    Args:
        content: Full report content

    Returns:
        Dictionary with baseline, final, delta
    """
    results = {"baseline": 0, "final": 0, "delta": 0}
    in_tests = False

    for line in content.split("\n"):
        if "## Test Results" in line:
            in_tests = True
            continue
        if in_tests and line.startswith("## "):
            break
        if in_tests:
            if "**Baseline:**" in line:
                match = TEST_COUNT_PATTERN.search(line)
                if match:
                    results["baseline"] = int(match.group(1))
            elif "**Final:**" in line:
                match = TEST_COUNT_PATTERN.search(line)
                if match:
                    results["final"] = int(match.group(1))
            elif "**Delta:**" in line:
                # Extract number, handling +/- prefix
                delta_match = re.search(r"[+-]?(\d+)", line)
                if delta_match:
                    sign = -1 if "-" in line.split(delta_match.group(1))[0] else 1
                    results["delta"] = sign * int(delta_match.group(1))

    return results


def parse_execution_result(content: str) -> tuple[ExecutionStatus, int, int]:
    """
    Extract execution result and phase counts.

    Args:
        content: Full report content

    Returns:
        Tuple of (status, phases_completed, phases_planned)
    """
    status = ExecutionStatus.FAILED
    completed = 0
    planned = 0

    for line in content.split("\n"):
        result_match = RESULT_PATTERN.search(line)
        if result_match:
            status = ExecutionStatus.from_report(result_match.group(1))

        phases_match = PHASES_SUMMARY_PATTERN.search(line)
        if phases_match:
            completed = int(phases_match.group(1))
            planned = int(phases_match.group(2))

    return status, completed, planned


def parse_git_info(content: str) -> dict[str, Any]:
    """
    Extract git information from report.

    Args:
        content: Full report content

    Returns:
        Dictionary with commit_count, files_changed
    """
    info = {"commit_count": 0, "files_changed": 0, "final_commit": ""}

    # Find commits count
    commits_match = COMMITS_COUNT_PATTERN.search(content)
    if commits_match:
        info["commit_count"] = int(commits_match.group(1))

    # Find files changed
    files_match = FILES_CHANGED_PATTERN.search(content)
    if files_match:
        info["files_changed"] = int(files_match.group(1))

    # Extract final commit from git log (first line after ``` in Git History)
    in_git_history = False
    in_code_block = False
    for line in content.split("\n"):
        if "## Git History" in line:
            in_git_history = True
            continue
        if in_git_history and line.startswith("## "):
            break
        if in_git_history and line.strip() == "```":
            if not in_code_block:
                in_code_block = True
                continue
            else:
                break
        if in_git_history and in_code_block and line.strip():
            # First non-empty line in code block is the latest commit
            parts = line.strip().split()
            if parts:
                info["final_commit"] = parts[0]
            break

    return info


def parse_execution_report(content: str) -> dict[str, Any]:
    """
    Parse EXECUTION_REPORT.md into structured data.

    Args:
        content: Raw markdown content of report

    Returns:
        Dictionary with all extracted fields

    Raises:
        ImportError: If required sections missing
    """
    metadata = parse_metadata_table(content)
    if not metadata:
        raise ImportError("Missing or invalid Metadata section")

    phases = parse_phase_table(content)
    test_results = parse_test_results(content)
    status, completed, planned = parse_execution_result(content)
    git_info = parse_git_info(content)

    # Parse timestamps
    started_at = None
    completed_at = None
    if "Started" in metadata:
        try:
            started_at = datetime.fromisoformat(
                metadata["Started"].replace("Z", "+00:00")
            )
        except ValueError:
            pass
    if "Completed" in metadata:
        try:
            completed_at = datetime.fromisoformat(
                metadata["Completed"].replace("Z", "+00:00")
            )
        except ValueError:
            pass

    return {
        "audit_document": metadata.get("Audit Document", ""),
        "document_title": metadata.get("Document Title", ""),
        "project_name": metadata.get("Project", ""),
        "project_path": metadata.get("Project Path", ""),
        "branch": metadata.get("Branch", ""),
        "base_commit": metadata.get("Base Commit", ""),
        "started_at": started_at,
        "completed_at": completed_at,
        "phaser_version": metadata.get("Phaser Version", ""),
        "status": status,
        "phases_planned": planned or len(phases),
        "phases_completed": completed,
        "phases": phases,
        "baseline_tests": test_results["baseline"],
        "final_tests": test_results["final"],
        "commit_count": git_info["commit_count"],
        "files_changed": git_info["files_changed"],
        "final_commit": git_info["final_commit"],
    }


def import_execution_report(
    report_path: Path,
    project_dir: Path | None = None,
) -> ExecutionRecord:
    """
    Parse EXECUTION_REPORT.md and create an execution record.

    Args:
        report_path: Path to EXECUTION_REPORT.md
        project_dir: Project directory (inferred if not provided)

    Returns:
        ExecutionRecord with all metrics

    Raises:
        ImportError: If report format is invalid
        StorageError: If file cannot be read
    """
    if not report_path.exists():
        raise StorageError(f"Report file not found: {report_path}")

    try:
        content = report_path.read_text()
    except OSError as e:
        raise StorageError(f"Failed to read report: {e}")

    data = parse_execution_report(content)

    # Validate required fields
    if not data["started_at"] or not data["completed_at"]:
        raise ImportError("Missing or invalid timestamps in report")

    # Create phase records
    phase_records = [
        PhaseRecord(
            phase_number=p["phase_number"],
            title=p["title"],
            status=p["status"],
            commit_sha=p["commit_sha"],
        )
        for p in data["phases"]
    ]

    # Determine project_dir
    if project_dir is None:
        project_dir = report_path.parent

    return ExecutionRecord(
        execution_id=ExecutionRecord.generate_id(),
        audit_document=data["audit_document"],
        document_title=data["document_title"],
        project_name=data["project_name"],
        project_path=data["project_path"],
        branch=data["branch"],
        started_at=data["started_at"].replace(tzinfo=None),
        completed_at=data["completed_at"].replace(tzinfo=None),
        phaser_version=data["phaser_version"],
        status=data["status"],
        phases_planned=data["phases_planned"],
        phases_completed=data["phases_completed"],
        baseline_tests=data["baseline_tests"],
        final_tests=data["final_tests"],
        base_commit=data["base_commit"],
        final_commit=data["final_commit"],
        commit_count=data["commit_count"],
        files_changed=data["files_changed"],
        phases=phase_records,
        report_path=str(report_path),
    )


# =============================================================================
# Query and Aggregation
# =============================================================================


def query_executions(
    project_dir: Path,
    query: AnalyticsQuery | None = None,
) -> list[ExecutionRecord]:
    """
    Query execution records matching criteria.

    Args:
        project_dir: Project root directory
        query: Query parameters (None for all records)

    Returns:
        List of matching ExecutionRecords, sorted by date descending
    """
    if query is None:
        query = AnalyticsQuery()

    records = list_executions(project_dir)

    # Apply filters
    filtered = [r for r in records if query.matches(r)]

    # Apply limit
    if query.limit is not None:
        filtered = filtered[: query.limit]

    return filtered


def compute_project_stats(project_dir: Path) -> AggregatedStats:
    """
    Compute statistics for a project.

    Args:
        project_dir: Project root directory

    Returns:
        AggregatedStats for all executions
    """
    records = list_executions(project_dir)
    return AggregatedStats.compute(records)


def get_failed_phases(
    project_dir: Path,
) -> list[tuple[int, str, int]]:
    """
    Get phases that have failed across all executions.

    Args:
        project_dir: Project root directory

    Returns:
        List of (phase_number, title, failure_count) tuples,
        sorted by failure count descending
    """
    records = list_executions(project_dir)
    failures: dict[tuple[int, str], int] = {}

    for record in records:
        for phase in record.phases:
            if phase.status == PhaseStatus.FAILED:
                key = (phase.phase_number, phase.title)
                failures[key] = failures.get(key, 0) + 1

    # Sort by failure count descending
    sorted_failures = sorted(
        [(num, title, count) for (num, title), count in failures.items()],
        key=lambda x: x[2],
        reverse=True,
    )

    return sorted_failures


def get_execution_by_document(
    project_dir: Path,
    document_name: str,
    latest_only: bool = True,
) -> list[ExecutionRecord]:
    """
    Get executions for a specific document.

    Args:
        project_dir: Project root directory
        document_name: Document name to filter by
        latest_only: If True, return only the most recent

    Returns:
        List of matching ExecutionRecords
    """
    query = AnalyticsQuery(document=document_name, limit=1 if latest_only else None)
    return query_executions(project_dir, query)


def get_recent_failures(
    project_dir: Path,
    limit: int = 5,
) -> list[ExecutionRecord]:
    """
    Get recent failed executions.

    Args:
        project_dir: Project root directory
        limit: Maximum number to return

    Returns:
        List of failed ExecutionRecords
    """
    query = AnalyticsQuery(status=ExecutionStatus.FAILED, limit=limit)
    return query_executions(project_dir, query)


# =============================================================================
# Output Formatting
# =============================================================================


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable form.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "1h 23m" or "45m 12s"
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def format_status_symbol(status: ExecutionStatus) -> str:
    """Get status symbol for display."""
    symbols = {
        ExecutionStatus.SUCCESS: "✅",
        ExecutionStatus.PARTIAL: "⚠️",
        ExecutionStatus.FAILED: "❌",
    }
    return symbols.get(status, "?")


def format_table(
    records: list[ExecutionRecord],
    stats: AggregatedStats,
    verbose: bool = False,
    project_name: str = "",
) -> str:
    """
    Format execution data as ASCII table.

    Args:
        records: Execution records to display
        stats: Aggregated statistics
        verbose: Include per-phase details
        project_name: Project name for header

    Returns:
        Formatted table string
    """
    if not records:
        return "No analytics data found."

    lines = []

    # Header
    title = f"{project_name} Analytics" if project_name else "Phaser Analytics"
    lines.append(f"\n{title} - Last {len(records)} Execution(s)\n")
    lines.append("-" * 70)

    # Table header
    lines.append(f"{'Date':<12} {'Document':<28} {'Status':<8} {'Duration':<10} {'Δ Tests':<8}")
    lines.append("-" * 70)

    # Rows
    for record in records:
        date_str = record.started_at.strftime("%Y-%m-%d")
        doc_name = record.audit_document[:26] + ".." if len(record.audit_document) > 28 else record.audit_document
        status = format_status_symbol(record.status)
        duration = format_duration(record.duration_seconds)
        delta = f"+{record.test_delta}" if record.test_delta >= 0 else str(record.test_delta)

        lines.append(f"{date_str:<12} {doc_name:<28} {status:<8} {duration:<10} {delta:<8}")

        # Verbose: show phases
        if verbose and record.phases:
            lines.append("")
            for phase in record.phases:
                p_status = format_status_symbol(
                    ExecutionStatus.SUCCESS if phase.status == PhaseStatus.COMPLETED
                    else ExecutionStatus.FAILED if phase.status == PhaseStatus.FAILED
                    else ExecutionStatus.PARTIAL
                )
                commit = phase.commit_sha[:7] if phase.commit_sha else "-"
                lines.append(f"    Phase {phase.phase_number}: {phase.title[:30]:<30} {p_status} {commit}")
            lines.append("")

    lines.append("-" * 70)

    # Summary
    success_pct = int(stats.success_rate * 100)
    avg_duration = format_duration(stats.avg_duration_seconds)
    delta_sign = "+" if stats.total_test_delta >= 0 else ""

    lines.append(
        f"Summary: {stats.total_executions} executions | "
        f"{stats.successful} successful ({success_pct}%) | "
        f"Avg: {avg_duration} | "
        f"Total Δ: {delta_sign}{stats.total_test_delta} tests"
    )

    return "\n".join(lines)


def format_json(
    records: list[ExecutionRecord],
    stats: AggregatedStats,
    query: AnalyticsQuery | None = None,
    project_name: str = "",
) -> str:
    """
    Format execution data as JSON.

    Args:
        records: Execution records
        stats: Aggregated statistics
        query: Original query (for context)
        project_name: Project name

    Returns:
        JSON string
    """
    data = {
        "query": query.to_dict() if query else {},
        "project": {
            "name": project_name,
        },
        "executions": [r.to_dict() for r in records],
        "stats": stats.to_dict(),
        "generated_at": datetime.utcnow().isoformat(),
    }
    return json.dumps(data, indent=2)


def format_markdown(
    records: list[ExecutionRecord],
    stats: AggregatedStats,
    project_name: str = "",
) -> str:
    """
    Format execution data as markdown report.

    Args:
        records: Execution records
        stats: Aggregated statistics
        project_name: Project name

    Returns:
        Markdown string
    """
    lines = []

    # Header
    title = f"{project_name} Analytics Report" if project_name else "Phaser Analytics Report"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Executions | {stats.total_executions} |")
    lines.append(f"| Successful | {stats.successful} ({int(stats.success_rate * 100)}%) |")
    lines.append(f"| Partial | {stats.partial} |")
    lines.append(f"| Failed | {stats.failed} |")
    lines.append(f"| Average Duration | {format_duration(stats.avg_duration_seconds)} |")
    lines.append(f"| Total Test Delta | {'+' if stats.total_test_delta >= 0 else ''}{stats.total_test_delta} |")
    lines.append("")

    # Recent executions
    lines.append("## Recent Executions")
    lines.append("")

    for record in records[:10]:  # Limit to 10 for readability
        status = format_status_symbol(record.status)
        lines.append(f"### {record.audit_document}")
        lines.append("")
        lines.append(f"- **Status:** {status} {record.status.value.title()}")
        lines.append(f"- **Date:** {record.started_at.strftime('%Y-%m-%d')}")
        lines.append(f"- **Duration:** {format_duration(record.duration_seconds)}")
        lines.append(f"- **Tests:** {record.baseline_tests} → {record.final_tests} ({'+' if record.test_delta >= 0 else ''}{record.test_delta})")
        lines.append(f"- **Phases:** {record.phases_completed}/{record.phases_planned} completed")
        lines.append("")

    return "\n".join(lines)


def format_csv(records: list[ExecutionRecord]) -> str:
    """
    Format execution data as CSV.

    Args:
        records: Execution records

    Returns:
        CSV string with header row
    """
    lines = []

    # Header
    headers = [
        "execution_id",
        "audit_document",
        "started_at",
        "completed_at",
        "duration_seconds",
        "status",
        "phases_planned",
        "phases_completed",
        "baseline_tests",
        "final_tests",
        "test_delta",
        "commit_count",
        "files_changed",
    ]
    lines.append(",".join(headers))

    # Rows
    for record in records:
        row = [
            record.execution_id,
            f'"{record.audit_document}"',  # Quote for safety
            record.started_at.isoformat(),
            record.completed_at.isoformat(),
            str(record.duration_seconds),
            record.status.value,
            str(record.phases_planned),
            str(record.phases_completed),
            str(record.baseline_tests),
            str(record.final_tests),
            str(record.test_delta),
            str(record.commit_count),
            str(record.files_changed),
        ]
        lines.append(",".join(row))

    return "\n".join(lines)
