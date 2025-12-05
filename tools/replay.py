"""
Phaser Audit Replay

Re-run verification checks from past audits to detect regressions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from tools.storage import PhaserStorage


# =============================================================================
# Enums
# =============================================================================


class ReplayScope(str, Enum):
    """Scope of replay checks."""

    ALL = "all"
    CONTRACTS = "contracts"
    FILES = "files"


class RegressionType(str, Enum):
    """Type of regression detected."""

    CONTRACT_VIOLATION = "contract_violation"
    FILE_REGRESSION = "file_regression"
    PATTERN_REGRESSION = "pattern_regression"
    CONTRACT_MISSING = "contract_missing"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Regression:
    """A single regression detected during replay."""

    type: RegressionType
    source: str  # Contract ID, file path, or pattern
    message: str  # Human-readable description
    severity: str = "error"  # "error" or "warning"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "source": self.source,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Regression:
        """Create from dictionary."""
        return cls(
            type=RegressionType(d["type"]),
            source=d["source"],
            message=d["message"],
            severity=d.get("severity", "error"),
            details=d.get("details", {}),
        )


@dataclass
class ReplayResult:
    """Result of replaying an audit."""

    audit_id: str
    audit_slug: str
    replayed_at: str  # ISO 8601 timestamp
    scope: ReplayScope

    contracts_checked: int = 0
    contracts_passed: int = 0
    files_checked: int = 0
    files_passed: int = 0

    regressions: list[Regression] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if replay passed with no regressions."""
        return len(self.regressions) == 0

    @property
    def regression_count(self) -> int:
        """Count of regressions found."""
        return len(self.regressions)

    @property
    def error_count(self) -> int:
        """Count of error-severity regressions."""
        return sum(1 for r in self.regressions if r.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of warning-severity regressions."""
        return sum(1 for r in self.regressions if r.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "audit_id": self.audit_id,
            "audit_slug": self.audit_slug,
            "replayed_at": self.replayed_at,
            "scope": self.scope.value,
            "contracts_checked": self.contracts_checked,
            "contracts_passed": self.contracts_passed,
            "files_checked": self.files_checked,
            "files_passed": self.files_passed,
            "regressions": [r.to_dict() for r in self.regressions],
            "passed": self.passed,
            "regression_count": self.regression_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReplayResult:
        """Create from dictionary."""
        return cls(
            audit_id=d["audit_id"],
            audit_slug=d["audit_slug"],
            replayed_at=d["replayed_at"],
            scope=ReplayScope(d["scope"]),
            contracts_checked=d.get("contracts_checked", 0),
            contracts_passed=d.get("contracts_passed", 0),
            files_checked=d.get("files_checked", 0),
            files_passed=d.get("files_passed", 0),
            regressions=[Regression.from_dict(r) for r in d.get("regressions", [])],
        )


@dataclass
class ReplayableAudit:
    """An audit that can be replayed."""

    id: str
    slug: str
    date: str
    status: str
    phase_count: int = 0
    contract_ids: list[str] = field(default_factory=list)
    file_change_count: int = 0
    last_replayed: str | None = None
    last_replay_passed: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "slug": self.slug,
            "date": self.date,
            "status": self.status,
            "phase_count": self.phase_count,
            "contract_ids": self.contract_ids,
            "file_change_count": self.file_change_count,
            "last_replayed": self.last_replayed,
            "last_replay_passed": self.last_replay_passed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReplayableAudit:
        """Create from dictionary."""
        return cls(
            id=d["id"],
            slug=d["slug"],
            date=d["date"],
            status=d["status"],
            phase_count=d.get("phase_count", 0),
            contract_ids=d.get("contract_ids", []),
            file_change_count=d.get("file_change_count", 0),
            last_replayed=d.get("last_replayed"),
            last_replay_passed=d.get("last_replay_passed"),
        )


@dataclass
class FileChange:
    """A file change recorded during an audit."""

    path: str
    change_type: str  # "created", "modified", "deleted", "renamed"
    timestamp: str
    audit_id: str
    hash_before: str | None = None
    hash_after: str | None = None
    old_path: str | None = None  # For renames

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "path": self.path,
            "change_type": self.change_type,
            "timestamp": self.timestamp,
            "audit_id": self.audit_id,
        }
        if self.hash_before:
            result["hash_before"] = self.hash_before
        if self.hash_after:
            result["hash_after"] = self.hash_after
        if self.old_path:
            result["old_path"] = self.old_path
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileChange:
        """Create from dictionary."""
        return cls(
            path=d["path"],
            change_type=d["change_type"],
            timestamp=d["timestamp"],
            audit_id=d["audit_id"],
            hash_before=d.get("hash_before"),
            hash_after=d.get("hash_after"),
            old_path=d.get("old_path"),
        )


# =============================================================================
# Helper Functions
# =============================================================================


def now_iso() -> str:
    """Get current time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# =============================================================================
# Replay Engine Functions
# =============================================================================


def get_audit_by_slug(
    slug: str,
    storage: PhaserStorage,
) -> dict[str, Any] | None:
    """
    Get audit record by slug.

    Args:
        slug: Audit slug (or "latest" for most recent completed)
        storage: PhaserStorage instance

    Returns:
        Audit dict if found, None otherwise
    """
    audits = storage.list_audits()

    if slug == "latest":
        # Find most recent completed audit
        completed = [a for a in audits if a.get("status") == "completed"]
        if not completed:
            return None
        completed.sort(key=lambda a: a.get("date", ""), reverse=True)
        return completed[0]

    # Find by slug
    for audit in audits:
        if audit.get("slug") == slug:
            return audit

    return None


def get_audit_contracts(
    audit_id: str,
    storage: PhaserStorage,
) -> list[Any]:
    """
    Get contracts created by a specific audit.

    Args:
        audit_id: UUID of the audit
        storage: PhaserStorage instance

    Returns:
        List of Contract instances linked to this audit
    """
    from tools.contracts import load_contracts

    all_contracts = load_contracts(storage, enabled_only=False)

    # Filter to contracts from this audit
    return [
        c for c in all_contracts
        if c.audit_source and c.audit_source.id == audit_id
    ]


def get_audit_file_changes(
    audit_id: str,
    storage: PhaserStorage,
) -> list[FileChange]:
    """
    Get file changes from an audit's events.

    Args:
        audit_id: UUID of the audit
        storage: PhaserStorage instance

    Returns:
        List of FileChange records
    """
    events = storage.get_events(audit_id=audit_id)

    file_changes = []
    for event in events:
        event_type = event.get("type", "")
        if event_type in ("file_created", "file_modified", "file_deleted", "file_renamed"):
            data = event.get("data", {})
            change_type = event_type.replace("file_", "")

            file_changes.append(
                FileChange(
                    path=data.get("path", ""),
                    change_type=change_type,
                    timestamp=event.get("timestamp", ""),
                    audit_id=audit_id,
                    hash_before=data.get("hash_before"),
                    hash_after=data.get("hash_after"),
                    old_path=data.get("old_path"),
                )
            )

    return file_changes


def check_contract_regressions(
    contracts: list[Any],
    root: Path,
) -> tuple[int, int, list[Regression]]:
    """
    Check contracts for regressions.

    Args:
        contracts: List of Contract instances to check
        root: Root directory to check against

    Returns:
        Tuple of (checked_count, passed_count, regressions)
    """
    from tools.contracts import check_contract

    checked = 0
    passed = 0
    regressions = []

    for contract in contracts:
        checked += 1
        result = check_contract(contract, root)

        if result.passed:
            passed += 1
        else:
            # Contract failed - this is a regression
            violation_details = [v.to_dict() for v in result.violations]
            severity = contract.rule.severity.value if hasattr(contract.rule.severity, 'value') else str(contract.rule.severity)
            regressions.append(
                Regression(
                    type=RegressionType.CONTRACT_VIOLATION,
                    source=contract.rule.id,
                    message=f"Contract '{contract.rule.id}' now failing",
                    severity=severity,
                    details={
                        "violations": violation_details,
                        "violation_count": len(result.violations),
                    },
                )
            )

    return checked, passed, regressions


def check_file_regressions(
    file_changes: list[FileChange],
    root: Path,
) -> tuple[int, int, list[Regression]]:
    """
    Check file changes for regressions.

    Args:
        file_changes: List of FileChange records
        root: Root directory to check

    Returns:
        Tuple of (checked_count, passed_count, regressions)
    """
    checked = 0
    passed = 0
    regressions = []

    for change in file_changes:
        file_path = root / change.path
        checked += 1

        if change.change_type == "deleted":
            # File was deleted - should not exist
            if file_path.exists():
                regressions.append(
                    Regression(
                        type=RegressionType.FILE_REGRESSION,
                        source=change.path,
                        message=f"Deleted file has reappeared: {change.path}",
                        severity="error",
                        details={"expected": "deleted", "actual": "exists"},
                    )
                )
            else:
                passed += 1

        elif change.change_type == "created":
            # File was created - should exist
            if not file_path.exists():
                regressions.append(
                    Regression(
                        type=RegressionType.FILE_REGRESSION,
                        source=change.path,
                        message=f"Created file is now missing: {change.path}",
                        severity="error",
                        details={"expected": "exists", "actual": "missing"},
                    )
                )
            else:
                passed += 1

        elif change.change_type == "modified":
            # File was modified - check it still exists
            # Note: We don't treat content changes as regressions unless
            # we have hash information to compare
            if not file_path.exists():
                regressions.append(
                    Regression(
                        type=RegressionType.FILE_REGRESSION,
                        source=change.path,
                        message=f"Modified file is now missing: {change.path}",
                        severity="error",
                        details={"expected": "exists", "actual": "missing"},
                    )
                )
            else:
                passed += 1

        elif change.change_type == "renamed":
            # File was renamed - new path should exist, old shouldn't
            if not file_path.exists():
                regressions.append(
                    Regression(
                        type=RegressionType.FILE_REGRESSION,
                        source=change.path,
                        message=f"Renamed file is now missing: {change.path}",
                        severity="error",
                        details={
                            "expected": "exists",
                            "actual": "missing",
                            "old_path": change.old_path,
                        },
                    )
                )
            elif change.old_path:
                old_file_path = root / change.old_path
                if old_file_path.exists():
                    regressions.append(
                        Regression(
                            type=RegressionType.FILE_REGRESSION,
                            source=change.old_path,
                            message=f"Old path of renamed file still exists: {change.old_path}",
                            severity="warning",
                            details={
                                "old_path": change.old_path,
                                "new_path": change.path,
                            },
                        )
                    )
                else:
                    passed += 1
            else:
                passed += 1

        else:
            # Unknown change type - skip
            checked -= 1

    return checked, passed, regressions


def replay_audit(
    audit_slug: str,
    storage: PhaserStorage,
    root: Path,
    scope: ReplayScope = ReplayScope.ALL,
) -> ReplayResult:
    """
    Replay an audit and check for regressions.

    Args:
        audit_slug: Slug of the audit to replay (or "latest")
        storage: PhaserStorage instance
        root: Root directory to check against
        scope: What to check (all, contracts, files)

    Returns:
        ReplayResult with regression information

    Raises:
        ValueError: If audit not found or not replayable
    """
    # Find the audit
    audit = get_audit_by_slug(audit_slug, storage)
    if not audit:
        available = storage.list_audits()
        available_slugs = [a.get("slug") for a in available if a.get("status") == "completed"]
        raise ValueError(
            f"Audit '{audit_slug}' not found.\n"
            f"Available audits: {', '.join(available_slugs) if available_slugs else 'none'}"
        )

    audit_id = audit.get("id", "")
    actual_slug = audit.get("slug", audit_slug)

    # Initialize result
    result = ReplayResult(
        audit_id=audit_id,
        audit_slug=actual_slug,
        replayed_at=now_iso(),
        scope=scope,
    )

    all_regressions: list[Regression] = []

    # Check contracts if in scope
    if scope in (ReplayScope.ALL, ReplayScope.CONTRACTS):
        contracts = get_audit_contracts(audit_id, storage)
        checked, passed, regressions = check_contract_regressions(contracts, root)
        result.contracts_checked = checked
        result.contracts_passed = passed
        all_regressions.extend(regressions)

    # Check files if in scope
    if scope in (ReplayScope.ALL, ReplayScope.FILES):
        file_changes = get_audit_file_changes(audit_id, storage)
        checked, passed, regressions = check_file_regressions(file_changes, root)
        result.files_checked = checked
        result.files_passed = passed
        all_regressions.extend(regressions)

    result.regressions = all_regressions

    return result


def get_replayable_audits(
    storage: PhaserStorage,
    status: str = "completed",
    limit: int = 20,
) -> list[ReplayableAudit]:
    """
    Get list of audits that can be replayed.

    Args:
        storage: PhaserStorage instance
        status: Filter by status (completed, all)
        limit: Maximum audits to return

    Returns:
        List of ReplayableAudit instances
    """
    audits = storage.list_audits()

    # Filter by status
    if status != "all":
        audits = [a for a in audits if a.get("status") == status]

    # Sort by date descending
    audits.sort(key=lambda a: a.get("date", ""), reverse=True)

    # Limit
    audits = audits[:limit]

    # Convert to ReplayableAudit
    results = []
    for audit in audits:
        audit_id = audit.get("id", "")

        # Get contract count
        try:
            contracts = get_audit_contracts(audit_id, storage)
            contract_ids = [c.rule.id for c in contracts]
        except Exception:
            contract_ids = []

        # Get file change count
        try:
            file_changes = get_audit_file_changes(audit_id, storage)
            file_change_count = len(file_changes)
        except Exception:
            file_change_count = 0

        # Get phase count from events
        try:
            events = storage.get_events(audit_id=audit_id)
            phase_count = sum(1 for e in events if e.get("type") == "phase_completed")
        except Exception:
            phase_count = 0

        results.append(
            ReplayableAudit(
                id=audit_id,
                slug=audit.get("slug", ""),
                date=audit.get("date", ""),
                status=audit.get("status", ""),
                phase_count=phase_count,
                contract_ids=contract_ids,
                file_change_count=file_change_count,
                last_replayed=audit.get("last_replayed"),
                last_replay_passed=audit.get("last_replay_passed"),
            )
        )

    return results


def save_replay_result(
    result: ReplayResult,
    storage: PhaserStorage,
) -> None:
    """
    Save replay result to storage for history tracking.

    Args:
        result: ReplayResult to save
        storage: PhaserStorage instance
    """
    import json

    storage.ensure_directories()

    # Load existing replays
    replays_path = storage.get_path("replays.json")

    if replays_path.exists():
        with open(replays_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"version": 1, "replays": []}

    # Append new result
    data["replays"].append(result.to_dict())

    # Keep only last 100 replays
    if len(data["replays"]) > 100:
        data["replays"] = data["replays"][-100:]

    # Write back
    with open(replays_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Update audit record with replay info
    storage.update_audit(
        result.audit_id,
        {
            "last_replayed": result.replayed_at,
            "last_replay_passed": result.passed,
        },
    )
