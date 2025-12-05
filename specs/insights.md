# Insights Specification

> Phaser v1.3 — Analytics and Statistics Feature

---

## Overview

Insights aggregates data from stored audits and events to provide actionable statistics. Users can query patterns, track trends, and identify areas for improvement across their audit history.

---

## Purpose

1. **Understand patterns** — See which issues recur across audits
2. **Track progress** — Monitor improvement over time
3. **Identify hotspots** — Find files/modules with most changes
4. **Inform decisions** — Use data to prioritize future audits

---

## Scope

By default, Insights operates on **project-scoped** data (audits in the current project's `.phaser/` directory). The `--global` flag aggregates across all projects in `~/.phaser/`.

---

## CLI Interface

### phaser insights summary

Show high-level statistics.

```bash
phaser insights summary [OPTIONS]

Options:
  --global          Include all projects (default: current project only)
  --since DATE      Only include audits after this date (YYYY-MM-DD)
  --format TEXT     Output format: text, json (default: text)
```

**Example Output:**

```
Audit Insights Summary
======================
Period: Last 90 days
Scope: Current project

Audits:
  Total: 12
  Completed: 10 (83%)
  In Progress: 2 (17%)
  Failed: 0 (0%)

Phases:
  Total executed: 48
  Success rate: 94%
  Average per audit: 4.0

Top Issues (by contract violations):
  1. no-singleton-pattern: 15 violations
  2. require-tests: 8 violations
  3. no-force-unwrap: 5 violations

Most Changed Files:
  1. src/services/UserService.swift (12 changes)
  2. src/models/AppState.swift (8 changes)
  3. src/views/MainView.swift (6 changes)
```

### phaser insights audits

List audits with statistics.

```bash
phaser insights audits [OPTIONS]

Options:
  --global          Include all projects
  --status TEXT     Filter by status: completed, in_progress, failed
  --since DATE      Only include audits after this date
  --limit INT       Maximum audits to show (default: 20)
  --format TEXT     Output format: text, json, csv (default: text)
```

**Example Output:**

```
Recent Audits
=============

Slug                    Date        Phases  Status     Duration
----                    ----        ------  ------     --------
security-hardening      2025-12-05  6/6     completed  2h 15m
architecture-refactor   2025-12-03  8/8     completed  4h 30m
test-coverage           2025-12-01  4/5     in_progress  -
performance-audit       2025-11-28  5/5     completed  1h 45m
```

### phaser insights contracts

Show contract violation statistics.

```bash
phaser insights contracts [OPTIONS]

Options:
  --global          Include all projects
  --since DATE      Only include violations after this date
  --sort TEXT       Sort by: violations, severity, name (default: violations)
  --format TEXT     Output format: text, json (default: text)
```

**Example Output:**

```
Contract Violation Statistics
=============================

Contract                Severity  Violations  Last Seen
--------                --------  ----------  ---------
no-singleton-pattern    error     15          2025-12-05
require-observable      warning   12          2025-12-04
no-force-unwrap         error     5           2025-12-03
license-required        error     2           2025-11-30
```

### phaser insights files

Show file change statistics.

```bash
phaser insights files [OPTIONS]

Options:
  --global          Include all projects
  --since DATE      Only include changes after this date
  --limit INT       Maximum files to show (default: 20)
  --format TEXT     Output format: text, json (default: text)
```

**Example Output:**

```
Most Changed Files
==================

File                              Changes  Audits  Last Changed
----                              -------  ------  ------------
src/services/UserService.swift    12       4       2025-12-05
src/models/AppState.swift         8        3       2025-12-04
src/views/MainView.swift          6        2       2025-12-03
```

### phaser insights events

Show event statistics.

```bash
phaser insights events [OPTIONS]

Options:
  --global          Include all projects
  --type TEXT       Filter by event type
  --since DATE      Only include events after this date
  --format TEXT     Output format: text, json (default: text)
```

**Example Output:**

```
Event Statistics
================

Event Type              Count   Last Occurred
----------              -----   -------------
audit_started           12      2025-12-05
audit_completed         10      2025-12-05
phase_completed         48      2025-12-05
phase_failed            3       2025-12-02
verification_passed     45      2025-12-05
verification_failed     3       2025-12-02
file_modified           156     2025-12-05
file_created            42      2025-12-04
```

### phaser insights trends

Show trends over time.

```bash
phaser insights trends [OPTIONS]

Options:
  --global          Include all projects
  --period TEXT     Aggregation period: day, week, month (default: week)
  --metric TEXT     Metric to show: audits, phases, violations (default: audits)
  --format TEXT     Output format: text, json (default: text)
```

**Example Output:**

```
Audit Trends (Weekly)
=====================

Week Starting    Audits  Phases  Violations
-------------    ------  ------  ----------
2025-12-02       3       14      8
2025-11-25       4       18      12
2025-11-18       2       8       5
2025-11-11       3       12      10
```

---

## Data Classes

### InsightsSummary

```python
@dataclass
class InsightsSummary:
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

    def to_dict(self) -> dict[str, Any]: ...
```

### AuditStats

```python
@dataclass
class AuditStats:
    id: str
    slug: str
    project: str
    date: str
    status: str
    phase_count: int
    completed_phases: int
    duration_seconds: int | None

    def to_dict(self) -> dict[str, Any]: ...
```

### ContractStats

```python
@dataclass
class ContractStats:
    contract_id: str
    rule_id: str
    severity: str
    violation_count: int
    last_violation: str | None
    affected_files: list[str]

    def to_dict(self) -> dict[str, Any]: ...
```

### FileStats

```python
@dataclass
class FileStats:
    path: str
    change_count: int
    audit_count: int
    last_changed: str
    change_types: dict[str, int]  # created, modified, deleted

    def to_dict(self) -> dict[str, Any]: ...
```

### EventStats

```python
@dataclass
class EventStats:
    event_type: str
    count: int
    last_occurred: str | None

    def to_dict(self) -> dict[str, Any]: ...
```

### TrendPoint

```python
@dataclass
class TrendPoint:
    period_start: str
    period_end: str
    audit_count: int
    phase_count: int
    violation_count: int

    def to_dict(self) -> dict[str, Any]: ...
```

---

## Core Functions

### get_summary

```python
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
```

### get_audit_stats

```python
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
```

### get_contract_stats

```python
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
```

### get_file_stats

```python
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
```

### get_event_stats

```python
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
```

### get_trends

```python
def get_trends(
    storage: PhaserStorage,
    global_scope: bool = False,
    period: str = "week",
    metric: str = "audits",
    since: datetime | None = None,
) -> list[TrendPoint]:
    """
    Get trend data over time.

    Args:
        storage: PhaserStorage instance
        global_scope: If True, include all projects
        period: Aggregation period (day, week, month)
        metric: Metric to aggregate
        since: Only include data after this date

    Returns:
        List of TrendPoint sorted by period
    """
```

---

## Data Sources

Insights aggregates from these storage locations:

| Source | Data Type | Used For |
|--------|-----------|----------|
| `.phaser/audits.json` | Audit records | Audit stats, completion rates |
| `.phaser/events.json` | Event log | Event stats, file changes, timelines |
| `.phaser/contracts/` | Contract definitions | Contract stats (via check results) |
| `~/.phaser/audits.json` | Global audits | Cross-project insights |
| `~/.phaser/events.json` | Global events | Cross-project insights |

---

## Aggregation Strategy

Insights computes statistics **on-the-fly** rather than storing aggregated data. This ensures:

1. **Accuracy** — Always reflects current data
2. **Simplicity** — No sync issues between raw and aggregated data
3. **Flexibility** — Easy to add new metrics

For large datasets (10,000+ events), consider caching. Caching strategy TBD based on real-world usage.

---

## Date Filtering

The `--since` option accepts:

| Format | Example | Meaning |
|--------|---------|---------|
| ISO date | `2025-12-01` | Since start of that day |
| Relative | `7d` | Last 7 days |
| Relative | `4w` | Last 4 weeks |
| Relative | `3m` | Last 3 months |

```bash
# Last 7 days
phaser insights summary --since 7d

# Since specific date
phaser insights summary --since 2025-12-01

# Last month
phaser insights summary --since 1m
```

---

## Output Formats

### Text (Default)

Human-readable tables and summaries. Uses fixed-width columns for alignment.

### JSON

Machine-readable output for scripting and integration:

```json
{
  "summary": {
    "period_start": "2025-09-05",
    "period_end": "2025-12-05",
    "scope": "project",
    "audit_count": 12,
    "completed_count": 10,
    ...
  }
}
```

### CSV (audits, files only)

For spreadsheet import:

```csv
slug,date,phases,status,duration
security-hardening,2025-12-05,6,completed,8100
architecture-refactor,2025-12-03,8,completed,16200
```

---

## Edge Cases

### Empty Storage

If no audits or events exist:

```
Audit Insights Summary
======================
No audit data found.

Run 'phaser diff capture' to start tracking audits.
```

### Missing Fields

Older audit records may lack newer fields. Insights handles gracefully:

- Missing `duration`: Show "-" in output
- Missing `phases`: Show "?" in output
- Missing events: Skip in aggregation

### Large Datasets

For 10,000+ events, performance may degrade. Recommendations:

1. Use `--since` to limit date range
2. Use `--limit` to cap results
3. Future: Add caching layer

---

## Example Usage

### Quick Summary

```bash
phaser insights summary
```

### Last Month's Audits

```bash
phaser insights audits --since 1m --format json
```

### Contract Hotspots

```bash
phaser insights contracts --sort violations
```

### File Churn Analysis

```bash
phaser insights files --limit 10
```

### Weekly Trends

```bash
phaser insights trends --period week --metric violations
```

### Cross-Project View

```bash
phaser insights summary --global
```

---

*Phaser v1.3 — Insights Specification*
