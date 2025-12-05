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
