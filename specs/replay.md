# Replay Specification

> Phaser v1.4 — Audit Replay Feature

---

## Overview

Audit Replay re-runs verification checks from a completed audit against the current codebase. It detects regressions—issues that were fixed during the audit but have since reappeared.

---

## Purpose

1. **Detect regressions** — Find issues that were fixed but came back
2. **Validate stability** — Confirm audit outcomes still hold
3. **Track drift** — Measure how much codebase has changed since audit
4. **Support CI** — Run replay checks in continuous integration

---

## Concepts

### Replay vs Re-execution

| Aspect        | Replay                     | Re-execution      |
| ------------- | -------------------------- | ----------------- |
| Purpose       | Verify outcomes still hold | Redo the work     |
| Modifies code | No                         | Yes               |
| Speed         | Fast (checks only)         | Slow (full audit) |
| Use case      | Regression detection       | Recovery          |

### Regression Types

| Type                   | Description                               | Example                          |
| ---------------------- | ----------------------------------------- | -------------------------------- |
| **Contract Violation** | A contract created by the audit now fails | `no-singleton` contract violated |
| **File Regression**    | File changed back to pre-audit state      | Removed file reappeared          |
| **Pattern Regression** | Forbidden pattern reintroduced            | `.shared` singleton added back   |

### Replay Scope

Replay can check:

1. **Contracts** — All contracts created by the audit
2. **File states** — Files that were created/modified/deleted
3. **Verification commands** — Original phase verification commands

---

## CLI Interface

### phaser replay

Replay an audit and check for regressions.

```bash
phaser replay <audit-slug> [OPTIONS]

Arguments:
  audit-slug          Slug of the audit to replay (or "latest")

Options:
  --root PATH         Root directory to check (default: .)
  --scope TEXT        What to check: all, contracts, files (default: all)
  --fail-on-regression  Exit 1 if any regressions found
  --format TEXT       Output format: text, json (default: text)
  --verbose           Show detailed regression information
  --dry-run           Show what would be checked without checking
```

**Examples:**

```bash
# Replay the most recent audit
phaser replay latest

# Replay a specific audit
phaser replay security-hardening

# Replay with CI integration
phaser replay security-hardening --fail-on-regression

# Check only contracts
phaser replay security-hardening --scope contracts

# Detailed output
phaser replay security-hardening --verbose
```

### phaser replay list

List audits available for replay.

```bash
phaser replay list [OPTIONS]

Options:
  --status TEXT       Filter by status: completed, all (default: completed)
  --limit INT         Maximum audits to show (default: 20)
  --format TEXT       Output format: text, json (default: text)
```

**Example Output:**

```
Audits Available for Replay
===========================

Slug                    Date        Phases  Contracts  Status
----                    ----        ------  ---------  ------
security-hardening      2025-12-05  6       3          completed
architecture-refactor   2025-12-03  8       5          completed
test-coverage           2025-12-01  5       2          completed
```

### phaser replay show

Show details of a past audit for replay.

```bash
phaser replay show <audit-slug> [OPTIONS]

Options:
  --format TEXT       Output format: text, json (default: text)
```

**Example Output:**

```
Audit: security-hardening
=========================

ID: abc-123-def-456
Date: 2025-12-05
Status: completed
Phases: 6

Contracts Created:
  - no-singleton-pattern (error)
  - no-force-unwrap (error)
  - require-tests (warning)

Files Modified: 12
Files Created: 3
Files Deleted: 1

Last Replayed: 2025-12-10T14:30:00Z
Replay Status: 2 regressions detected
```

---

## Data Classes

### ReplayScope (Enum)

```python
class ReplayScope(str, Enum):
    ALL = "all"
    CONTRACTS = "contracts"
    FILES = "files"
```

### RegressionType (Enum)

```python
class RegressionType(str, Enum):
    CONTRACT_VIOLATION = "contract_violation"
    FILE_REGRESSION = "file_regression"
    PATTERN_REGRESSION = "pattern_regression"
```

### Regression

```python
@dataclass
class Regression:
    type: RegressionType
    source: str              # Contract ID, file path, or pattern
    message: str             # Human-readable description
    details: dict[str, Any]  # Additional context
    severity: str            # "error" or "warning"

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Regression": ...
```

### ReplayResult

```python
@dataclass
class ReplayResult:
    audit_id: str
    audit_slug: str
    replayed_at: str         # ISO 8601 timestamp
    scope: ReplayScope

    contracts_checked: int
    contracts_passed: int
    files_checked: int
    files_passed: int

    regressions: list[Regression]

    @property
    def passed(self) -> bool:
        return len(self.regressions) == 0

    @property
    def regression_count(self) -> int:
        return len(self.regressions)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, d: dict) -> "ReplayResult": ...
```

### ReplayableAudit

```python
@dataclass
class ReplayableAudit:
    id: str
    slug: str
    date: str
    status: str
    phase_count: int
    contract_ids: list[str]
    file_changes: list[dict[str, Any]]
    last_replayed: str | None
    last_replay_status: str | None

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, d: dict) -> "ReplayableAudit": ...
```

---

## Core Functions

### replay_audit

```python
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
```

### get_replayable_audits

```python
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
```

### get_audit_contracts

```python
def get_audit_contracts(
    audit_id: str,
    storage: PhaserStorage,
) -> list[Contract]:
    """
    Get contracts created by a specific audit.

    Args:
        audit_id: UUID of the audit
        storage: PhaserStorage instance

    Returns:
        List of Contract instances linked to this audit
    """
```

### get_audit_file_changes

```python
def get_audit_file_changes(
    audit_id: str,
    storage: PhaserStorage,
) -> list[dict[str, Any]]:
    """
    Get file changes from an audit's events.

    Args:
        audit_id: UUID of the audit
        storage: PhaserStorage instance

    Returns:
        List of file change records with type, path, and metadata
    """
```

### check_file_regressions

```python
def check_file_regressions(
    file_changes: list[dict[str, Any]],
    root: Path,
) -> list[Regression]:
    """
    Check if file changes from audit have regressed.

    Checks:
    - Deleted files haven't reappeared
    - Created files still exist
    - Modified files haven't reverted (hash comparison)

    Args:
        file_changes: File change records from audit
        root: Root directory to check

    Returns:
        List of Regression instances for any regressions found
    """
```

### save_replay_result

```python
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
```

### format_replay_result

```python
def format_replay_result(
    result: ReplayResult,
    verbose: bool = False,
) -> str:
    """
    Format replay result for terminal display.

    Args:
        result: ReplayResult to format
        verbose: Include detailed regression information

    Returns:
        Formatted string for display
    """
```

---

## Replay Process

### Algorithm

```
1. Resolve audit slug to audit record
   - "latest" → most recent completed audit
   - Otherwise → find by slug

2. Load audit's associated data
   - Contracts created by this audit
   - File change events from this audit

3. Based on scope, run checks:

   If scope == ALL or CONTRACTS:
     For each contract linked to audit:
       Run contract check against current codebase
       If failed → add CONTRACT_VIOLATION regression

   If scope == ALL or FILES:
     For each file change event:
       If type == "deleted":
         Check file doesn't exist → if exists, add FILE_REGRESSION
       If type == "created":
         Check file still exists → if missing, add FILE_REGRESSION
       If type == "modified" and has hash:
         Compare current hash → if different, note as drift (not regression)

4. Build and return ReplayResult
5. Optionally save result to replay history
```

### Contract Linking

Contracts are linked to audits via the `audit_source.id` field in the contract:

```yaml
audit_source:
  id: 'abc-123-def-456' # Links to audit
  slug: 'security-hardening'
  date: '2025-12-05'
  phase: 3
```

### File Change Tracking

File changes are recorded as events during audit execution:

```json
{
  "id": "evt-123",
  "type": "file_deleted",
  "timestamp": "2025-12-05T10:30:00Z",
  "audit_id": "abc-123-def-456",
  "data": {
    "path": "src/legacy/Singleton.swift",
    "hash_before": "sha256:abc123..."
  }
}
```

---

## Storage

### Replay History

Replay results are stored in `.phaser/replays.json`:

```json
{
  "version": 1,
  "replays": [
    {
      "audit_id": "abc-123",
      "audit_slug": "security-hardening",
      "replayed_at": "2025-12-10T14:30:00Z",
      "scope": "all",
      "contracts_checked": 3,
      "contracts_passed": 2,
      "files_checked": 16,
      "files_passed": 15,
      "regressions": [
        {
          "type": "contract_violation",
          "source": "no-singleton-pattern",
          "message": "Contract 'no-singleton-pattern' now failing",
          "severity": "error"
        }
      ]
    }
  ]
}
```

### Audit Metadata Extension

Audits gain replay-related fields:

```json
{
  "id": "abc-123",
  "slug": "security-hardening",
  "last_replayed": "2025-12-10T14:30:00Z",
  "last_replay_passed": false,
  "replay_count": 5
}
```

---

## Edge Cases

### Skipped Phases

If original audit had skipped phases:

- Only check contracts/files from completed phases
- Report skipped phases in output but don't fail for them

### Missing Contracts

If a contract was deleted since the audit:

- Report as "contract_missing" in output
- Don't count as regression (deliberate removal)

### File Hash Unavailable

If original file hash wasn't recorded:

- Skip hash comparison
- Only check existence for created/deleted files

### Renamed Files

If a file was renamed during audit:

- Track via file_renamed events
- Check new path exists, old path doesn't

### Audit Not Found

```
Error: Audit 'security-hardening' not found.

Available audits:
  - architecture-refactor (2025-12-03)
  - test-coverage (2025-12-01)

Use 'phaser replay list' to see all replayable audits.
```

### No Completed Audits

```
No completed audits available for replay.

Complete an audit first, then use 'phaser replay <slug>'.
```

---

## CI Integration

Run replay in CI to catch regressions:

```yaml
# .github/workflows/phaser.yml
- name: Check for regressions
  run: |
    phaser replay latest --fail-on-regression
```

Exit codes:

| Code | Meaning                                       |
| ---- | --------------------------------------------- |
| 0    | No regressions found                          |
| 1    | Regressions found (with --fail-on-regression) |
| 2    | Audit not found or invalid                    |

---

## Example Usage

### Basic Replay

```bash
# Replay most recent audit
phaser replay latest

# Output:
Replay Results: security-hardening
==================================
Replayed at: 2025-12-05T14:30:00Z

Contracts: 3 checked, 3 passed ✓
Files: 16 checked, 16 passed ✓

No regressions detected.
```

### Replay with Regressions

```bash
phaser replay security-hardening --verbose

# Output:
Replay Results: security-hardening
==================================
Replayed at: 2025-12-05T14:30:00Z

Contracts: 3 checked, 2 passed ✗
Files: 16 checked, 15 passed ✗

Regressions (2):

1. [ERROR] Contract Violation: no-singleton-pattern
   Pattern '\.shared\b' found in:
   - src/services/AuthService.swift:45
   - src/services/NetworkManager.swift:12

2. [ERROR] File Regression: src/legacy/Singleton.swift
   File was deleted but has reappeared.
```

### Programmatic Usage

```python
from tools.replay import replay_audit, ReplayScope
from tools.storage import PhaserStorage
from pathlib import Path

storage = PhaserStorage()
result = replay_audit(
    audit_slug="security-hardening",
    storage=storage,
    root=Path.cwd(),
    scope=ReplayScope.ALL,
)

if not result.passed:
    print(f"Found {result.regression_count} regressions")
    for reg in result.regressions:
        print(f"  - {reg.type}: {reg.message}")
```

---

_Phaser v1.4 — Replay Specification_
