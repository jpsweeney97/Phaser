"""
Phaser Insights

Analytics and statistics from stored audits and events.
Provides summary, trend, and detailed statistics for audit history.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from tools.storage import PhaserStorage


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class InsightsSummary:
    """High-level summary statistics."""

    period_start: str | None
    period_end: str | None
    scope: str  # "project" or "global"

    audit_count: int
    completed_count: int
    in_progress_count: int
    failed_count: int

    phase_count: int
    phase_success_rate: float
    avg_phases_per_audit: float

    top_violations: list[tuple[str, int]]  # (contract_id, count)
    most_changed_files: list[tuple[str, int]]  # (path, change_count)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "scope": self.scope,
            "audit_count": self.audit_count,
            "completed_count": self.completed_count,
            "in_progress_count": self.in_progress_count,
            "failed_count": self.failed_count,
            "phase_count": self.phase_count,
            "phase_success_rate": self.phase_success_rate,
            "avg_phases_per_audit": self.avg_phases_per_audit,
            "top_violations": [
                {"contract_id": cid, "count": cnt}
                for cid, cnt in self.top_violations
            ],
            "most_changed_files": [
                {"path": path, "count": cnt}
                for path, cnt in self.most_changed_files
            ],
        }


@dataclass
class AuditStats:
    """Statistics for a single audit."""

    id: str
    slug: str
    project: str
    date: str
    status: str
    phase_count: int
    completed_phases: int
    duration_seconds: int | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "slug": self.slug,
            "project": self.project,
            "date": self.date,
            "status": self.status,
            "phase_count": self.phase_count,
            "completed_phases": self.completed_phases,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ContractStats:
    """Statistics for a contract's violations."""

    contract_id: str
    rule_id: str
    severity: str
    violation_count: int
    last_violation: str | None
    affected_files: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "contract_id": self.contract_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "violation_count": self.violation_count,
            "last_violation": self.last_violation,
            "affected_files": self.affected_files,
        }


@dataclass
class FileStats:
    """Statistics for file changes."""

    path: str
    change_count: int
    audit_count: int
    last_changed: str
    change_types: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "change_count": self.change_count,
            "audit_count": self.audit_count,
            "last_changed": self.last_changed,
            "change_types": self.change_types,
        }


@dataclass
class EventStats:
    """Statistics for event types."""

    event_type: str
    count: int
    last_occurred: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "count": self.count,
            "last_occurred": self.last_occurred,
        }


@dataclass
class TrendPoint:
    """A single point in trend data."""

    period_start: str
    period_end: str
    audit_count: int
    phase_count: int
    violation_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "audit_count": self.audit_count,
            "phase_count": self.phase_count,
            "violation_count": self.violation_count,
        }


# =============================================================================
# Date Utilities
# =============================================================================


def parse_since(since_str: str) -> datetime:
    """
    Parse a since string into a datetime.

    Supports:
        - ISO date: "2025-12-01"
        - Relative: "7d" (7 days), "4w" (4 weeks), "3m" (3 months)

    Args:
        since_str: Date string to parse

    Returns:
        datetime object

    Raises:
        ValueError: If format is not recognized
    """
    # Try ISO date format
    try:
        return datetime.fromisoformat(since_str).replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Try relative format
    match = re.match(r"^(\d+)([dwm])$", since_str.lower())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        now = datetime.now(timezone.utc)

        if unit == "d":
            return now - timedelta(days=amount)
        elif unit == "w":
            return now - timedelta(weeks=amount)
        elif unit == "m":
            return now - timedelta(days=amount * 30)  # Approximate

    raise ValueError(
        f"Invalid date format: {since_str}. "
        "Use ISO date (2025-12-01) or relative (7d, 4w, 3m)."
    )


def get_period_bounds(
    period: str,
    reference: datetime,
) -> tuple[datetime, datetime]:
    """
    Get the start and end of a period containing the reference date.

    Args:
        period: Period type (day, week, month)
        reference: Reference datetime

    Returns:
        Tuple of (start, end) datetimes
    """
    if period == "day":
        start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        # Start of week (Monday)
        start = reference - timedelta(days=reference.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(weeks=1)
    elif period == "month":
        start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Next month
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:
        raise ValueError(f"Invalid period: {period}. Use day, week, or month.")

    return start, end


# =============================================================================
# Core Functions
# =============================================================================


def get_summary(
    storage: PhaserStorage,
    global_scope: bool = False,
    since: datetime | None = None,
) -> InsightsSummary:
    """
    Generate summary statistics.

    Args:
        storage: PhaserStorage instance
        global_scope: If True, include all projects
        since: Only include data after this date

    Returns:
        InsightsSummary with aggregated statistics
    """
    # Get audits
    audits = storage.list_audits()

    # Filter by date if specified
    if since:
        since_str = since.isoformat()
        audits = [a for a in audits if a.get("date", "") >= since_str[:10]]

    # Count by status
    completed = sum(1 for a in audits if a.get("status") == "completed")
    in_progress = sum(1 for a in audits if a.get("status") == "in_progress")
    failed = sum(1 for a in audits if a.get("status") == "failed")

    # Get events for phase and file stats
    events = storage.get_events()

    if since:
        since_str = since.isoformat()
        events = [e for e in events if e.get("timestamp", "") >= since_str]

    # Count phases
    phase_completed = sum(1 for e in events if e.get("type") == "phase_completed")
    phase_failed = sum(1 for e in events if e.get("type") == "phase_failed")
    phase_count = phase_completed + phase_failed

    if phase_count > 0:
        phase_success_rate = phase_completed / phase_count
    else:
        phase_success_rate = 0.0

    if len(audits) > 0:
        avg_phases = phase_count / len(audits)
    else:
        avg_phases = 0.0

    # Count file changes
    file_changes: Counter[str] = Counter()
    for event in events:
        if event.get("type") in ("file_created", "file_modified", "file_deleted"):
            path = event.get("data", {}).get("path", "")
            if path:
                file_changes[path] += 1

    most_changed = file_changes.most_common(10)

    # Count violations (from verification_failed events)
    violation_counts: Counter[str] = Counter()
    for event in events:
        if event.get("type") == "verification_failed":
            contract_id = event.get("data", {}).get("contract_id", "unknown")
            violation_counts[contract_id] += 1

    top_violations = violation_counts.most_common(10)

    # Determine period bounds
    now = datetime.now(timezone.utc)
    period_end = now.isoformat()[:10]
    period_start = since.isoformat()[:10] if since else None

    return InsightsSummary(
        period_start=period_start,
        period_end=period_end,
        scope="global" if global_scope else "project",
        audit_count=len(audits),
        completed_count=completed,
        in_progress_count=in_progress,
        failed_count=failed,
        phase_count=phase_count,
        phase_success_rate=phase_success_rate,
        avg_phases_per_audit=avg_phases,
        top_violations=top_violations,
        most_changed_files=most_changed,
    )


def get_audit_stats(
    storage: PhaserStorage,
    global_scope: bool = False,
    status: str | None = None,
    since: datetime | None = None,
    limit: int = 20,
) -> list[AuditStats]:
    """
    Get statistics for audits.

    Args:
        storage: PhaserStorage instance
        global_scope: If True, include all projects
        status: Filter by status
        since: Only include audits after this date
        limit: Maximum audits to return

    Returns:
        List of AuditStats
    """
    audits = storage.list_audits()

    # Filter by status
    if status:
        audits = [a for a in audits if a.get("status") == status]

    # Filter by date
    if since:
        since_str = since.isoformat()[:10]
        audits = [a for a in audits if a.get("date", "") >= since_str]

    # Sort by date descending
    audits.sort(key=lambda a: a.get("date", ""), reverse=True)

    # Limit
    audits = audits[:limit]

    # Get event counts per audit
    events = storage.get_events()
    audit_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        audit_id = event.get("audit_id")
        if audit_id:
            audit_events[audit_id].append(event)

    results = []
    for audit in audits:
        audit_id = audit.get("id", "")
        related_events = audit_events.get(audit_id, [])

        # Count phases
        phase_completed = sum(
            1 for e in related_events if e.get("type") == "phase_completed"
        )
        phase_started = sum(
            1 for e in related_events if e.get("type") == "phase_started"
        )

        # Calculate duration from events
        start_events = [
            e for e in related_events if e.get("type") == "audit_started"
        ]
        end_events = [
            e for e in related_events if e.get("type") == "audit_completed"
        ]

        duration = None
        if start_events and end_events:
            try:
                start_time = datetime.fromisoformat(
                    start_events[0].get("timestamp", "").replace("Z", "+00:00")
                )
                end_time = datetime.fromisoformat(
                    end_events[0].get("timestamp", "").replace("Z", "+00:00")
                )
                duration = int((end_time - start_time).total_seconds())
            except (ValueError, TypeError):
                pass

        results.append(
            AuditStats(
                id=audit_id,
                slug=audit.get("slug", ""),
                project=audit.get("project", ""),
                date=audit.get("date", ""),
                status=audit.get("status", "unknown"),
                phase_count=phase_started,
                completed_phases=phase_completed,
                duration_seconds=duration,
            )
        )

    return results


def get_contract_stats(
    storage: PhaserStorage,
    global_scope: bool = False,
    since: datetime | None = None,
    sort_by: str = "violations",
) -> list[ContractStats]:
    """
    Get violation statistics for contracts.

    Args:
        storage: PhaserStorage instance
        global_scope: If True, include all projects
        since: Only include violations after this date
        sort_by: Sort order (violations, severity, name)

    Returns:
        List of ContractStats
    """
    # Get events
    events = storage.get_events()

    if since:
        since_str = since.isoformat()
        events = [e for e in events if e.get("timestamp", "") >= since_str]

    # Aggregate violations by contract
    contract_violations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("type") == "verification_failed":
            data = event.get("data", {})
            contract_id = data.get("contract_id", "unknown")
            contract_violations[contract_id].append(event)

    # Build stats
    results = []
    for contract_id, violations in contract_violations.items():
        # Get affected files
        affected_files = set()
        for v in violations:
            path = v.get("data", {}).get("path")
            if path:
                affected_files.add(path)

        # Get last violation time
        sorted_violations = sorted(
            violations,
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )
        last_violation = sorted_violations[0].get("timestamp") if sorted_violations else None

        # Try to get severity from event data
        severity = "error"
        if violations:
            severity = violations[0].get("data", {}).get("severity", "error")

        results.append(
            ContractStats(
                contract_id=contract_id,
                rule_id=contract_id,  # May differ in full implementation
                severity=severity,
                violation_count=len(violations),
                last_violation=last_violation,
                affected_files=list(affected_files),
            )
        )

    # Sort
    if sort_by == "violations":
        results.sort(key=lambda s: s.violation_count, reverse=True)
    elif sort_by == "severity":
        severity_order = {"error": 0, "warning": 1}
        results.sort(key=lambda s: severity_order.get(s.severity, 2))
    elif sort_by == "name":
        results.sort(key=lambda s: s.contract_id)

    return results


def get_file_stats(
    storage: PhaserStorage,
    global_scope: bool = False,
    since: datetime | None = None,
    limit: int = 20,
) -> list[FileStats]:
    """
    Get change statistics for files.

    Args:
        storage: PhaserStorage instance
        global_scope: If True, include all projects
        since: Only include changes after this date
        limit: Maximum files to return

    Returns:
        List of FileStats sorted by change count
    """
    events = storage.get_events()

    if since:
        since_str = since.isoformat()
        events = [e for e in events if e.get("timestamp", "") >= since_str]

    # Aggregate by file
    file_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "changes": 0,
            "audits": set(),
            "last_changed": "",
            "types": Counter(),
        }
    )

    for event in events:
        event_type = event.get("type", "")
        if event_type in ("file_created", "file_modified", "file_deleted"):
            path = event.get("data", {}).get("path", "")
            if not path:
                continue

            file_data[path]["changes"] += 1
            file_data[path]["audits"].add(event.get("audit_id", ""))
            file_data[path]["types"][event_type.replace("file_", "")] += 1

            timestamp = event.get("timestamp", "")
            if timestamp > file_data[path]["last_changed"]:
                file_data[path]["last_changed"] = timestamp

    # Build stats
    results = []
    for path, data in file_data.items():
        results.append(
            FileStats(
                path=path,
                change_count=data["changes"],
                audit_count=len(data["audits"]),
                last_changed=data["last_changed"],
                change_types=dict(data["types"]),
            )
        )

    # Sort by change count and limit
    results.sort(key=lambda s: s.change_count, reverse=True)
    return results[:limit]


def get_event_stats(
    storage: PhaserStorage,
    global_scope: bool = False,
    event_type: str | None = None,
    since: datetime | None = None,
) -> list[EventStats]:
    """
    Get statistics for events.

    Args:
        storage: PhaserStorage instance
        global_scope: If True, include all projects
        event_type: Filter by event type
        since: Only include events after this date

    Returns:
        List of EventStats
    """
    events = storage.get_events()

    if since:
        since_str = since.isoformat()
        events = [e for e in events if e.get("timestamp", "") >= since_str]

    if event_type:
        events = [e for e in events if e.get("type") == event_type]

    # Aggregate by type
    type_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "last": ""}
    )

    for event in events:
        etype = event.get("type", "unknown")
        type_data[etype]["count"] += 1
        timestamp = event.get("timestamp", "")
        if timestamp > type_data[etype]["last"]:
            type_data[etype]["last"] = timestamp

    # Build stats
    results = []
    for etype, data in type_data.items():
        results.append(
            EventStats(
                event_type=etype,
                count=data["count"],
                last_occurred=data["last"] if data["last"] else None,
            )
        )

    # Sort by count
    results.sort(key=lambda s: s.count, reverse=True)
    return results


def get_trends(
    storage: PhaserStorage,
    global_scope: bool = False,
    period: str = "week",
    since: datetime | None = None,
    num_periods: int = 8,
) -> list[TrendPoint]:
    """
    Get trend data over time.

    Args:
        storage: PhaserStorage instance
        global_scope: If True, include all projects
        period: Aggregation period (day, week, month)
        since: Only include data after this date
        num_periods: Number of periods to include

    Returns:
        List of TrendPoint sorted by period (oldest first)
    """
    # Calculate period boundaries
    now = datetime.now(timezone.utc)
    periods: list[tuple[datetime, datetime]] = []

    current = now
    for _ in range(num_periods):
        start, end = get_period_bounds(period, current)
        periods.append((start, end))
        # Move to previous period
        current = start - timedelta(seconds=1)

    # Reverse to get chronological order
    periods.reverse()

    # Apply since filter
    if since:
        periods = [(s, e) for s, e in periods if e > since]

    # Get data
    audits = storage.list_audits()
    events = storage.get_events()

    # Build trend points
    results = []
    for start, end in periods:
        start_str = start.isoformat()
        end_str = end.isoformat()

        # Count audits in period
        period_audits = [
            a
            for a in audits
            if start_str[:10] <= a.get("date", "") < end_str[:10]
        ]

        # Count phases and violations in period
        period_events = [
            e
            for e in events
            if start_str <= e.get("timestamp", "") < end_str
        ]

        phase_count = sum(
            1 for e in period_events if e.get("type") == "phase_completed"
        )
        violation_count = sum(
            1 for e in period_events if e.get("type") == "verification_failed"
        )

        results.append(
            TrendPoint(
                period_start=start_str[:10],
                period_end=end_str[:10],
                audit_count=len(period_audits),
                phase_count=phase_count,
                violation_count=violation_count,
            )
        )

    return results


# =============================================================================
# Formatting Functions
# =============================================================================


def format_summary(summary: InsightsSummary) -> str:
    """Format summary for terminal display."""
    lines = [
        "Audit Insights Summary",
        "======================",
    ]

    if summary.period_start:
        lines.append(f"Period: {summary.period_start} to {summary.period_end}")
    else:
        lines.append(f"Period: All time (through {summary.period_end})")

    lines.append(f"Scope: {summary.scope.title()}")
    lines.append("")

    if summary.audit_count == 0:
        lines.append("No audit data found.")
        lines.append("")
        lines.append("Run 'phaser diff capture' to start tracking audits.")
        return "\n".join(lines)

    # Audit stats
    lines.append("Audits:")
    lines.append(f"  Total: {summary.audit_count}")
    if summary.audit_count > 0:
        pct_complete = (summary.completed_count / summary.audit_count) * 100
        pct_progress = (summary.in_progress_count / summary.audit_count) * 100
        pct_failed = (summary.failed_count / summary.audit_count) * 100
        lines.append(f"  Completed: {summary.completed_count} ({pct_complete:.0f}%)")
        lines.append(f"  In Progress: {summary.in_progress_count} ({pct_progress:.0f}%)")
        lines.append(f"  Failed: {summary.failed_count} ({pct_failed:.0f}%)")

    lines.append("")

    # Phase stats
    lines.append("Phases:")
    lines.append(f"  Total executed: {summary.phase_count}")
    lines.append(f"  Success rate: {summary.phase_success_rate * 100:.0f}%")
    lines.append(f"  Average per audit: {summary.avg_phases_per_audit:.1f}")

    # Top violations
    if summary.top_violations:
        lines.append("")
        lines.append("Top Issues (by violations):")
        for i, (contract_id, count) in enumerate(summary.top_violations[:5], 1):
            lines.append(f"  {i}. {contract_id}: {count} violations")

    # Most changed files
    if summary.most_changed_files:
        lines.append("")
        lines.append("Most Changed Files:")
        for i, (path, count) in enumerate(summary.most_changed_files[:5], 1):
            # Truncate long paths
            display_path = path if len(path) <= 40 else "..." + path[-37:]
            lines.append(f"  {i}. {display_path} ({count} changes)")

    return "\n".join(lines)


def format_audit_stats(stats: list[AuditStats]) -> str:
    """Format audit stats as a table."""
    if not stats:
        return "No audits found."

    lines = [
        "Recent Audits",
        "=============",
        "",
        f"{'Slug':<24} {'Date':<12} {'Phases':<8} {'Status':<12} {'Duration':<10}",
        f"{'-' * 24} {'-' * 12} {'-' * 8} {'-' * 12} {'-' * 10}",
    ]

    for s in stats:
        phases = f"{s.completed_phases}/{s.phase_count}" if s.phase_count else "?"
        duration = "-"
        if s.duration_seconds:
            hours = s.duration_seconds // 3600
            minutes = (s.duration_seconds % 3600) // 60
            duration = f"{hours}h {minutes}m"

        slug = s.slug[:24] if len(s.slug) <= 24 else s.slug[:21] + "..."
        lines.append(f"{slug:<24} {s.date:<12} {phases:<8} {s.status:<12} {duration:<10}")

    return "\n".join(lines)


def format_contract_stats(stats: list[ContractStats]) -> str:
    """Format contract stats as a table."""
    if not stats:
        return "No contract violations found."

    lines = [
        "Contract Violation Statistics",
        "=============================",
        "",
        f"{'Contract':<24} {'Severity':<10} {'Violations':<12} {'Last Seen':<12}",
        f"{'-' * 24} {'-' * 10} {'-' * 12} {'-' * 12}",
    ]

    for s in stats:
        contract = s.contract_id[:24] if len(s.contract_id) <= 24 else s.contract_id[:21] + "..."
        last = s.last_violation[:10] if s.last_violation else "-"
        lines.append(f"{contract:<24} {s.severity:<10} {s.violation_count:<12} {last:<12}")

    return "\n".join(lines)


def format_file_stats(stats: list[FileStats]) -> str:
    """Format file stats as a table."""
    if not stats:
        return "No file changes found."

    lines = [
        "Most Changed Files",
        "==================",
        "",
        f"{'File':<40} {'Changes':<10} {'Audits':<8} {'Last Changed':<12}",
        f"{'-' * 40} {'-' * 10} {'-' * 8} {'-' * 12}",
    ]

    for s in stats:
        path = s.path if len(s.path) <= 40 else "..." + s.path[-37:]
        last = s.last_changed[:10] if s.last_changed else "-"
        lines.append(f"{path:<40} {s.change_count:<10} {s.audit_count:<8} {last:<12}")

    return "\n".join(lines)


def format_event_stats(stats: list[EventStats]) -> str:
    """Format event stats as a table."""
    if not stats:
        return "No events found."

    lines = [
        "Event Statistics",
        "================",
        "",
        f"{'Event Type':<24} {'Count':<10} {'Last Occurred':<20}",
        f"{'-' * 24} {'-' * 10} {'-' * 20}",
    ]

    for s in stats:
        last = s.last_occurred[:19] if s.last_occurred else "-"
        lines.append(f"{s.event_type:<24} {s.count:<10} {last:<20}")

    return "\n".join(lines)


def format_trends(trends: list[TrendPoint], metric: str = "audits") -> str:
    """Format trend data as a table."""
    if not trends:
        return "No trend data available."

    period_label = "Week Starting" if len(trends) > 1 else "Period"

    lines = [
        f"Trends ({metric.title()})",
        "=" * 40,
        "",
        f"{period_label:<16} {'Audits':<10} {'Phases':<10} {'Violations':<12}",
        f"{'-' * 16} {'-' * 10} {'-' * 10} {'-' * 12}",
    ]

    for t in trends:
        lines.append(
            f"{t.period_start:<16} {t.audit_count:<10} {t.phase_count:<10} {t.violation_count:<12}"
        )

    return "\n".join(lines)


def format_duration(seconds: int) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


# =============================================================================
# CLI Interface
# =============================================================================


@click.group()
def cli() -> None:
    """Analytics and statistics from audit history."""
    pass


@cli.command()
@click.option("--global", "global_scope", is_flag=True, help="Include all projects")
@click.option("--since", default=None, help="Only include data after this date")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def summary(global_scope: bool, since: str | None, output_format: str) -> None:
    """
    Show high-level audit statistics.

    Displays summary of audits, phases, violations, and file changes.

    Examples:

        phaser insights summary

        phaser insights summary --since 7d

        phaser insights summary --global --format json
    """
    import json

    from tools.storage import PhaserStorage

    storage = PhaserStorage()

    since_dt = None
    if since:
        try:
            since_dt = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    result = get_summary(storage, global_scope=global_scope, since=since_dt)

    if output_format == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        click.echo(format_summary(result))


@cli.command()
@click.option("--global", "global_scope", is_flag=True, help="Include all projects")
@click.option("--status", type=click.Choice(["completed", "in_progress", "failed"]), help="Filter by status")
@click.option("--since", default=None, help="Only include audits after this date")
@click.option("--limit", default=20, help="Maximum audits to show")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "csv"]),
    default="text",
    help="Output format",
)
def audits(
    global_scope: bool,
    status: str | None,
    since: str | None,
    limit: int,
    output_format: str,
) -> None:
    """
    List audits with statistics.

    Shows recent audits with phase counts and duration.

    Examples:

        phaser insights audits

        phaser insights audits --status completed --limit 10

        phaser insights audits --since 1m --format csv
    """
    import json

    from tools.storage import PhaserStorage

    storage = PhaserStorage()

    since_dt = None
    if since:
        try:
            since_dt = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    results = get_audit_stats(
        storage,
        global_scope=global_scope,
        status=status,
        since=since_dt,
        limit=limit,
    )

    if output_format == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    elif output_format == "csv":
        click.echo("slug,date,phases,status,duration")
        for r in results:
            phases = f"{r.completed_phases}/{r.phase_count}"
            duration = r.duration_seconds or ""
            click.echo(f"{r.slug},{r.date},{phases},{r.status},{duration}")
    else:
        click.echo(format_audit_stats(results))


@cli.command()
@click.option("--global", "global_scope", is_flag=True, help="Include all projects")
@click.option("--since", default=None, help="Only include violations after this date")
@click.option(
    "--sort",
    "sort_by",
    type=click.Choice(["violations", "severity", "name"]),
    default="violations",
    help="Sort order",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def contracts(
    global_scope: bool,
    since: str | None,
    sort_by: str,
    output_format: str,
) -> None:
    """
    Show contract violation statistics.

    Lists contracts with violation counts and last occurrence.

    Examples:

        phaser insights contracts

        phaser insights contracts --sort severity

        phaser insights contracts --since 2w --format json
    """
    import json

    from tools.storage import PhaserStorage

    storage = PhaserStorage()

    since_dt = None
    if since:
        try:
            since_dt = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    results = get_contract_stats(
        storage,
        global_scope=global_scope,
        since=since_dt,
        sort_by=sort_by,
    )

    if output_format == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        click.echo(format_contract_stats(results))


@cli.command()
@click.option("--global", "global_scope", is_flag=True, help="Include all projects")
@click.option("--since", default=None, help="Only include changes after this date")
@click.option("--limit", default=20, help="Maximum files to show")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def files(
    global_scope: bool,
    since: str | None,
    limit: int,
    output_format: str,
) -> None:
    """
    Show file change statistics.

    Lists files with most changes across audits.

    Examples:

        phaser insights files

        phaser insights files --limit 10

        phaser insights files --since 1m --format json
    """
    import json

    from tools.storage import PhaserStorage

    storage = PhaserStorage()

    since_dt = None
    if since:
        try:
            since_dt = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    results = get_file_stats(
        storage,
        global_scope=global_scope,
        since=since_dt,
        limit=limit,
    )

    if output_format == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        click.echo(format_file_stats(results))


@cli.command()
@click.option("--global", "global_scope", is_flag=True, help="Include all projects")
@click.option("--type", "event_type", default=None, help="Filter by event type")
@click.option("--since", default=None, help="Only include events after this date")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def events(
    global_scope: bool,
    event_type: str | None,
    since: str | None,
    output_format: str,
) -> None:
    """
    Show event statistics.

    Lists event types with counts and last occurrence.

    Examples:

        phaser insights events

        phaser insights events --type phase_completed

        phaser insights events --since 7d --format json
    """
    import json

    from tools.storage import PhaserStorage

    storage = PhaserStorage()

    since_dt = None
    if since:
        try:
            since_dt = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    results = get_event_stats(
        storage,
        global_scope=global_scope,
        event_type=event_type,
        since=since_dt,
    )

    if output_format == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        click.echo(format_event_stats(results))


@cli.command()
@click.option("--global", "global_scope", is_flag=True, help="Include all projects")
@click.option(
    "--period",
    type=click.Choice(["day", "week", "month"]),
    default="week",
    help="Aggregation period",
)
@click.option(
    "--metric",
    type=click.Choice(["audits", "phases", "violations"]),
    default="audits",
    help="Metric to show",
)
@click.option("--since", default=None, help="Only include data after this date")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def trends(
    global_scope: bool,
    period: str,
    metric: str,
    since: str | None,
    output_format: str,
) -> None:
    """
    Show trends over time.

    Displays audit activity aggregated by period.

    Examples:

        phaser insights trends

        phaser insights trends --period month --metric violations

        phaser insights trends --since 3m --format json
    """
    import json

    from tools.storage import PhaserStorage

    storage = PhaserStorage()

    since_dt = None
    if since:
        try:
            since_dt = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    results = get_trends(
        storage,
        global_scope=global_scope,
        period=period,
        since=since_dt,
    )

    if output_format == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        click.echo(format_trends(results, metric))
