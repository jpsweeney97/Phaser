# Analytics Specification

> Phaser v1.7 — Execution Metrics and Historical Tracking
> Feature: `phaser analytics [show|export|clear]`

---

## Table of Contents

1. [Overview](#1-overview)
2. [CLI Interface](#2-cli-interface)
3. [Data Model](#3-data-model)
4. [Storage Architecture](#4-storage-architecture)
5. [Data Collection](#5-data-collection)
6. [Report Parsing](#6-report-parsing)
7. [Aggregation and Queries](#7-aggregation-and-queries)
8. [Output Formats](#8-output-formats)
9. [CI Integration](#9-ci-integration)
10. [Data Classes](#10-data-classes)
11. [Core Functions](#11-core-functions)
12. [CLI Implementation](#12-cli-implementation)
13. [Error Handling](#13-error-handling)
14. [Testing Requirements](#14-testing-requirements)
15. [Example Workflow](#15-example-workflow)
16. [Future Considerations](#16-future-considerations)
17. [Glossary](#17-glossary)

---

## 1. Overview

### 1.1 Problem Statement

Currently, Phaser executes audits without capturing historical metrics. Users cannot:

1. Track execution duration trends over time
2. Analyze test delta patterns across audits
3. Identify phases that commonly fail or require retries
4. Generate reports for team visibility or CI pipelines
5. Compare execution performance across projects

This limits visibility into audit effectiveness and makes it difficult to identify process improvements.

### 1.2 Solution

A new analytics subsystem that:

| Capability | Description |
|------------|-------------|
| **Capture** | Record execution metrics during and after audit runs |
| **Store** | Persist historical data in per-project `.phaser/` directory |
| **Query** | Aggregate and filter metrics across executions |
| **Export** | Generate reports in multiple formats (table, JSON, markdown) |

### 1.3 User Workflow After Implementation

```
User: phaser execute audit.md
      [Claude Code executes autonomously]
      [EXECUTION_REPORT.md generated]
      
User: phaser analytics show
      [Displays summary of recent executions]
      
User: phaser analytics show --last 10 --format table
      [Displays tabular summary of last 10 executions]
      
User: phaser analytics export --format json > metrics.json
      [Exports all metrics for CI consumption]
```

### 1.4 Scope

**In Scope (v1.7):**

- Post-execution parsing of EXECUTION_REPORT.md
- Per-execution and per-phase metric storage
- JSON file-based storage in `.phaser/analytics/`
- CLI commands for viewing, exporting, and clearing data
- Aggregation statistics (success rate, average duration, test deltas)
- CI-friendly JSON output format

**Out of Scope (v1.7):**

- Real-time metrics during execution (requires Claude Code hooks)
- SQLite database storage (potential v1.8 enhancement)
- Cross-project analytics dashboard
- Token usage tracking (requires API integration)
- Automatic anomaly detection

### 1.5 Design Decisions

#### 1.5.1 Post-hoc Parsing vs Real-time Capture

**Decision:** Post-hoc parsing of EXECUTION_REPORT.md

**Rationale:**

| Approach | Pros | Cons |
|----------|------|------|
| Post-hoc parsing | Simple, no Claude Code changes, works with existing reports | Limited to data in report |
| Real-time hooks | More granular data, actual durations | Requires Claude Code integration, complex |

Post-hoc parsing provides 80% of the value with 20% of the complexity. Real-time capture can be added in v1.8 if needed.

#### 1.5.2 SQLite vs JSON Files

**Decision:** JSON files (one per execution)

**Rationale:**

| Approach | Pros | Cons |
|----------|------|------|
| JSON files | Human-readable, git-friendly, portable | Slower aggregation at scale |
| SQLite | Fast queries, built-in aggregation | Binary file, harder to inspect |

JSON files are simpler to implement, debug, and version control. SQLite can be introduced if performance becomes an issue (unlikely at typical audit volumes).

#### 1.5.3 Per-project vs Global Storage

**Decision:** Per-project `.phaser/` directory with optional global aggregation

**Rationale:**

- Project isolation matches existing `.audit-meta/` pattern
- Metrics stay with the code they describe
- Global aggregation available via `phaser analytics --global`

---

## 2. CLI Interface

### 2.1 phaser analytics show

```bash
phaser analytics show [OPTIONS]

Options:
  --last N            Show last N executions (default: 5)
  --since DATE        Show executions since DATE (ISO format)
  --until DATE        Show executions until DATE (ISO format)
  --status STATUS     Filter by status: success, partial, failed, all (default: all)
  --format FORMAT     Output format: table, json, markdown (default: table)
  --verbose           Show per-phase details
  --global            Aggregate across all projects in ~/.phaser/

Output:
  - Summary table of executions matching criteria
  - Statistics (success rate, avg duration, test deltas)
```

**Examples:**

```bash
# Show last 5 executions (default)
phaser analytics show

# Show last 20 executions with details
phaser analytics show --last 20 --verbose

# Show all successful executions this month
phaser analytics show --since 2024-12-01 --status success

# JSON output for scripting
phaser analytics show --format json | jq '.executions[0]'

# Global view across all projects
phaser analytics show --global --last 50
```

### 2.2 phaser analytics export

```bash
phaser analytics export [OPTIONS]

Options:
  --format FORMAT     Output format: json, markdown, csv (default: json)
  --output PATH       Write to file instead of stdout
  --since DATE        Export executions since DATE
  --until DATE        Export executions until DATE
  --global            Export from all projects

Output:
  - Complete execution data in specified format
  - Suitable for CI artifacts or external analysis
```

**Examples:**

```bash
# Export all data as JSON
phaser analytics export > analytics.json

# Export as markdown report
phaser analytics export --format markdown --output report.md

# Export recent data as CSV for spreadsheet
phaser analytics export --since 2024-12-01 --format csv > metrics.csv

# Export global data for CI
phaser analytics export --global --format json > ci-metrics.json
```

### 2.3 phaser analytics clear

```bash
phaser analytics clear [OPTIONS]

Options:
  --before DATE       Clear executions before DATE
  --all               Clear all analytics data
  --force             Skip confirmation prompt
  --dry-run           Show what would be deleted

Output:
  - Confirmation of deleted records
  - Summary of remaining data
```

**Examples:**

```bash
# Clear all data (with confirmation)
phaser analytics clear --all

# Clear old data
phaser analytics clear --before 2024-06-01

# Preview deletion
phaser analytics clear --before 2024-06-01 --dry-run
```

### 2.4 phaser analytics import

```bash
phaser analytics import <report-file> [OPTIONS]

Arguments:
  report-file         Path to EXECUTION_REPORT.md (or directory containing reports)

Options:
  --recursive         Scan directory recursively for reports
  --force             Re-import even if already exists

Output:
  - Count of imported executions
  - Any parsing errors encountered
```

**Examples:**

```bash
# Import from a specific report
phaser analytics import EXECUTION_REPORT.md

# Import all reports from archive directory
phaser analytics import ./archived-reports/ --recursive
```

---

## 3. Data Model

### 3.1 Execution Record

An execution record captures the complete state of a single audit run.

```python
@dataclass
class ExecutionRecord:
    """Complete record of a single audit execution."""
    
    # Identity
    execution_id: str             # UUID
    audit_document: str           # "document-7-reverse.md"
    document_title: str           # "Document 7: Reverse Audit"
    
    # Location
    project_name: str             # "Phaser"
    project_path: str             # "/Users/jp/Projects/Phaser"
    branch: str                   # "audit/2024-12-06-bridge"
    
    # Timing
    started_at: datetime          # ISO8601
    completed_at: datetime        # ISO8601
    duration_seconds: float       # Computed from timestamps
    
    # Versions
    phaser_version: str           # "1.6.3"
    
    # Results
    status: ExecutionStatus       # SUCCESS, PARTIAL, FAILED
    phases_planned: int           # Total phases in document
    phases_completed: int         # Phases that succeeded
    
    # Tests
    baseline_tests: int           # Tests before execution
    final_tests: int              # Tests after execution
    test_delta: int               # final - baseline
    
    # Git
    base_commit: str              # Starting commit SHA
    final_commit: str             # Ending commit SHA
    commit_count: int             # Number of commits made
    files_changed: int            # From git diff --stat
    
    # Phases
    phases: list[PhaseRecord]     # Per-phase details
    
    # Raw
    report_path: str              # Path to EXECUTION_REPORT.md
    imported_at: datetime         # When this record was created
```

### 3.2 Phase Record

```python
@dataclass
class PhaseRecord:
    """Record of a single phase within an execution."""
    
    phase_number: int             # 36
    title: str                    # "Reverse Audit Specification"
    status: PhaseStatus           # COMPLETED, FAILED, SKIPPED
    commit_sha: str | None        # Commit hash if completed
    
    # Derived from git log timestamps (if available)
    started_at: datetime | None   # Estimated from commit timestamps
    completed_at: datetime | None # From commit timestamp
    duration_seconds: float | None
    
    # Test changes for this phase
    tests_before: int | None      # If trackable
    tests_after: int | None       # If trackable
    
    # Issues
    error_message: str | None     # If failed
    retry_count: int              # Number of retries attempted
```

### 3.3 Aggregated Statistics

```python
@dataclass
class AggregatedStats:
    """Computed statistics across multiple executions."""
    
    # Counts
    total_executions: int
    successful: int
    partial: int
    failed: int
    
    # Rates
    success_rate: float           # 0.0 to 1.0
    
    # Timing
    avg_duration_seconds: float
    min_duration_seconds: float
    max_duration_seconds: float
    total_duration_seconds: float
    
    # Tests
    total_test_delta: int
    avg_test_delta: float
    
    # Phases
    total_phases_executed: int
    phase_success_rate: float
    
    # Time range
    earliest_execution: datetime
    latest_execution: datetime
```

### 3.4 Enums

```python
class ExecutionStatus(str, Enum):
    SUCCESS = "success"           # All phases completed
    PARTIAL = "partial"           # Some phases completed
    FAILED = "failed"             # Execution failed

class PhaseStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
```

---

## 4. Storage Architecture

### 4.1 Directory Structure

```
{project}/
└── .phaser/
    ├── config.json               # Analytics configuration
    └── analytics/
        ├── index.json            # Index of all executions (fast lookup)
        └── executions/
            ├── 2024-12-06T10-30-00-abc123.json
            ├── 2024-12-06T14-15-00-def456.json
            └── 2024-12-07T09-00-00-ghi789.json

~/.phaser/                        # Global config (optional)
├── config.json                   # Global preferences
└── projects.json                 # Registry of known projects
```

### 4.2 Execution File Format

Each execution is stored as a JSON file named `{timestamp}-{short_id}.json`:

```json
{
  "schema_version": "1.0",
  "execution_id": "abc12345-6789-0def-ghij-klmnopqrstuv",
  "audit_document": "document-7-reverse.md",
  "document_title": "Document 7: Reverse Audit",
  "project_name": "Phaser",
  "project_path": "/Users/jp/Projects/Phaser",
  "branch": "audit/2024-12-06-reverse",
  "started_at": "2024-12-06T10:30:00Z",
  "completed_at": "2024-12-06T11:45:23Z",
  "duration_seconds": 4523.0,
  "phaser_version": "1.6.3",
  "status": "success",
  "phases_planned": 6,
  "phases_completed": 6,
  "baseline_tests": 280,
  "final_tests": 325,
  "test_delta": 45,
  "base_commit": "a1b2c3d4e5f6",
  "final_commit": "z9y8x7w6v5u4",
  "commit_count": 7,
  "files_changed": 12,
  "phases": [
    {
      "phase_number": 36,
      "title": "Reverse Audit Specification",
      "status": "completed",
      "commit_sha": "b2c3d4e5f6g7",
      "completed_at": "2024-12-06T10:45:00Z",
      "duration_seconds": null,
      "tests_before": null,
      "tests_after": null,
      "error_message": null,
      "retry_count": 0
    }
  ],
  "report_path": "/Users/jp/Projects/Phaser/EXECUTION_REPORT.md",
  "imported_at": "2024-12-06T11:46:00Z"
}
```

### 4.3 Index File Format

The index provides fast lookup without reading all execution files:

```json
{
  "schema_version": "1.0",
  "project_name": "Phaser",
  "updated_at": "2024-12-07T09:00:00Z",
  "execution_count": 15,
  "executions": [
    {
      "execution_id": "abc12345",
      "filename": "2024-12-06T10-30-00-abc123.json",
      "audit_document": "document-7-reverse.md",
      "started_at": "2024-12-06T10:30:00Z",
      "status": "success",
      "duration_seconds": 4523.0,
      "test_delta": 45
    }
  ],
  "stats": {
    "total_executions": 15,
    "successful": 13,
    "partial": 1,
    "failed": 1,
    "success_rate": 0.867,
    "avg_duration_seconds": 3200.5,
    "total_test_delta": 180
  }
}
```

### 4.4 Storage Operations

| Operation | Method |
|-----------|--------|
| Create | Write new JSON file + update index |
| Read single | Load JSON file directly |
| Read many | Read from index, load full records as needed |
| Delete | Remove JSON file + update index |
| Query | Filter index entries, load matching records |

### 4.5 Global Project Registry

For `--global` operations, maintain a registry of known projects:

```json
{
  "schema_version": "1.0",
  "projects": [
    {
      "name": "Phaser",
      "path": "/Users/jp/Projects/Phaser",
      "last_seen": "2024-12-07T09:00:00Z",
      "execution_count": 15
    },
    {
      "name": "MyApp",
      "path": "/Users/jp/Projects/MyApp",
      "last_seen": "2024-12-05T14:00:00Z",
      "execution_count": 8
    }
  ]
}
```

---

## 5. Data Collection

### 5.1 Collection Points

Analytics data is collected at two points:

| Point | Trigger | Data Collected |
|-------|---------|----------------|
| Pre-execution | `phaser execute` starts | Baseline tests, start time, phaser version |
| Post-execution | EXECUTION_REPORT.md detected | All metrics from report |

### 5.2 Pre-Execution Hook

Modify `execute_audit()` to record initial state:

```python
def execute_audit(
    audit_path: Path,
    project_dir: Path | None = None,
    *,
    skip_permissions: bool = True,
    force: bool = False,
    record_analytics: bool = True,  # NEW
) -> tuple[PrepareResult, subprocess.CompletedProcess]:
    """Execute an audit document."""
    
    # Existing preparation...
    result = prepare_audit(audit_path, project_dir, force=force)
    
    if record_analytics:
        # Record pre-execution state
        analytics_context = AnalyticsContext.start(
            audit_document=audit_path.name,
            project_dir=result.project_dir,
            document=result.document,
            baseline_tests=parse_baseline_test_count(result.document.prerequisites),
        )
        analytics_context.save_pending()
    
    # Launch Claude Code...
    process = launch_claude_code(result.prompt, result.project_dir, skip_permissions)
    
    return result, process
```

### 5.3 Post-Execution Import

After execution completes, import metrics from the report:

```python
def import_execution_report(
    report_path: Path,
    project_dir: Path | None = None,
) -> ExecutionRecord:
    """
    Parse EXECUTION_REPORT.md and create an execution record.
    
    Args:
        report_path: Path to EXECUTION_REPORT.md
        project_dir: Project directory (inferred from report_path if not provided)
    
    Returns:
        ExecutionRecord with all metrics
    
    Raises:
        ParseError: If report format is invalid
        AnalyticsError: If import fails
    """
```

### 5.4 Automatic Import

Add a CLI option to auto-import after execution:

```bash
phaser execute audit.md --import-analytics
```

Or detect and prompt:

```
Execution complete. EXECUTION_REPORT.md found.
Import analytics? [Y/n]:
```

---

## 6. Report Parsing

### 6.1 Fields to Extract

| Report Section | Fields Extracted |
|----------------|------------------|
| Metadata table | All key-value pairs |
| Execution Summary | Status, phase count, phase table |
| Test Results | Baseline, final, delta |
| Git History | Branch, commit count |
| Files Changed | File count from summary |
| Phases table | Per-phase status and commits |

### 6.2 Parsing Strategy

```python
def parse_execution_report(content: str) -> dict[str, Any]:
    """
    Parse EXECUTION_REPORT.md into structured data.
    
    Extracts:
    - Metadata table (key-value pairs)
    - Execution summary (status, phase table)
    - Test results (baseline, final, delta)
    - Git history (commits, branch)
    - Files changed (count)
    - Per-phase details
    
    Returns:
        Dictionary with all extracted fields
    
    Raises:
        ParseError: If required sections missing
    """
```

### 6.3 Metadata Table Parsing

```python
METADATA_PATTERN = re.compile(
    r'\|\s*(?P<field>[^|]+?)\s*\|\s*(?P<value>[^|]+?)\s*\|'
)

def parse_metadata_table(content: str) -> dict[str, str]:
    """Extract key-value pairs from Metadata table."""
    metadata = {}
    in_metadata = False
    
    for line in content.split('\n'):
        if '## Metadata' in line:
            in_metadata = True
            continue
        if in_metadata and line.startswith('## '):
            break
        if in_metadata:
            match = METADATA_PATTERN.match(line)
            if match and match.group('field') not in ('Field', '---'):
                key = match.group('field').strip()
                value = match.group('value').strip()
                metadata[key] = value
    
    return metadata
```

### 6.4 Phase Table Parsing

```python
PHASE_ROW_PATTERN = re.compile(
    r'\|\s*(?P<number>\d+)\s*\|\s*(?P<title>[^|]+?)\s*\|\s*(?P<status>[✅⚠️❌])\s*\|\s*(?P<commit>[a-f0-9]+)?\s*\|'
)

def parse_phase_table(content: str) -> list[dict]:
    """Extract phase details from Execution Summary table."""
```

### 6.5 Test Results Parsing

```python
TEST_RESULTS_PATTERN = re.compile(
    r'\*\*(?P<label>Baseline|Final|Delta):\*\*\s*\+?(?P<value>-?\d+)'
)

def parse_test_results(content: str) -> dict[str, int]:
    """Extract baseline, final, and delta from Test Results section."""
```

---

## 7. Aggregation and Queries

### 7.1 Query Interface

```python
@dataclass
class AnalyticsQuery:
    """Query parameters for analytics data."""
    
    limit: int | None = None          # Max records to return
    since: datetime | None = None     # Start of date range
    until: datetime | None = None     # End of date range
    status: ExecutionStatus | None = None  # Filter by status
    document: str | None = None       # Filter by document name
    
    def matches(self, record: ExecutionRecord) -> bool:
        """Check if a record matches this query."""
```

### 7.2 Aggregation Functions

```python
def compute_stats(records: list[ExecutionRecord]) -> AggregatedStats:
    """
    Compute aggregated statistics from execution records.
    
    Args:
        records: List of execution records
    
    Returns:
        AggregatedStats with computed values
    """

def compute_phase_failure_rates(records: list[ExecutionRecord]) -> dict[int, float]:
    """
    Compute failure rate per phase number across all executions.
    
    Returns:
        Dictionary mapping phase number to failure rate (0.0 to 1.0)
    """

def compute_duration_trend(records: list[ExecutionRecord]) -> list[tuple[datetime, float]]:
    """
    Compute duration trend over time.
    
    Returns:
        List of (timestamp, duration_seconds) tuples, sorted by time
    """
```

### 7.3 Common Queries

```python
def get_recent_executions(
    project_dir: Path,
    limit: int = 10,
) -> list[ExecutionRecord]:
    """Get most recent executions."""

def get_executions_by_status(
    project_dir: Path,
    status: ExecutionStatus,
) -> list[ExecutionRecord]:
    """Get all executions with a given status."""

def get_failed_phases(
    project_dir: Path,
) -> list[tuple[int, str, int]]:
    """
    Get phases that have failed.
    
    Returns:
        List of (phase_number, title, failure_count) tuples,
        sorted by failure count descending
    """
```

---

## 8. Output Formats

### 8.1 Table Format (Default)

```
╭──────────────────────────────────────────────────────────────────────╮
│                    Phaser Analytics - Last 5 Executions              │
├──────────────────────────────────────────────────────────────────────┤
│ Date       │ Document                 │ Status │ Duration │ Δ Tests │
├────────────┼──────────────────────────┼────────┼──────────┼─────────┤
│ 2024-12-07 │ document-8-analytics.md  │ ✅     │ 1h 15m   │ +45     │
│ 2024-12-06 │ document-7-reverse.md    │ ✅     │ 1h 23m   │ +32     │
│ 2024-12-05 │ document-6-replay.md     │ ⚠️      │ 0h 58m   │ +28     │
│ 2024-12-04 │ document-5-ci.md         │ ✅     │ 2h 05m   │ +67     │
│ 2024-12-03 │ document-4-bridge.md     │ ❌     │ 0h 12m   │ +0      │
╰──────────────────────────────────────────────────────────────────────╯

Summary: 5 executions | 3 successful (60%) | Avg: 1h 11m | Total Δ: +172 tests
```

### 8.2 Verbose Table (--verbose)

```
╭──────────────────────────────────────────────────────────────────────╮
│                    document-7-reverse.md - Details                    │
├──────────────────────────────────────────────────────────────────────┤
│ Started:    2024-12-06T10:30:00Z                                     │
│ Completed:  2024-12-06T11:53:23Z                                     │
│ Duration:   1h 23m 23s                                               │
│ Status:     ✅ All phases completed                                  │
│ Branch:     audit/2024-12-06-reverse                                 │
│ Commits:    7                                                        │
│ Files:      12 changed                                               │
├──────────────────────────────────────────────────────────────────────┤
│ Phase │ Title                          │ Status │ Commit  │ Tests   │
├───────┼────────────────────────────────┼────────┼─────────┼─────────┤
│    36 │ Reverse Audit Specification    │ ✅     │ b2c3d4e │ +8      │
│    37 │ Git Diff Parsing               │ ✅     │ c3d4e5f │ +12     │
│    38 │ Change Detection               │ ✅     │ d4e5f6g │ +5      │
│    39 │ Document Generation            │ ✅     │ e5f6g7h │ +4      │
│    40 │ CLI Integration                │ ✅     │ f6g7h8i │ +2      │
│    41 │ Testing                        │ ✅     │ g7h8i9j │ +1      │
╰──────────────────────────────────────────────────────────────────────╯
```

### 8.3 JSON Format

```json
{
  "query": {
    "limit": 5,
    "since": null,
    "until": null,
    "status": null
  },
  "project": {
    "name": "Phaser",
    "path": "/Users/jp/Projects/Phaser"
  },
  "executions": [
    {
      "execution_id": "abc12345",
      "audit_document": "document-7-reverse.md",
      "started_at": "2024-12-06T10:30:00Z",
      "completed_at": "2024-12-06T11:53:23Z",
      "duration_seconds": 5003,
      "status": "success",
      "phases_planned": 6,
      "phases_completed": 6,
      "baseline_tests": 280,
      "final_tests": 312,
      "test_delta": 32,
      "phases": [...]
    }
  ],
  "stats": {
    "total_executions": 5,
    "successful": 3,
    "partial": 1,
    "failed": 1,
    "success_rate": 0.60,
    "avg_duration_seconds": 4260,
    "total_test_delta": 172
  },
  "generated_at": "2024-12-07T09:00:00Z"
}
```

### 8.4 Markdown Format

```markdown
# Phaser Analytics Report

Generated: 2024-12-07 09:00:00

## Summary

| Metric | Value |
|--------|-------|
| Total Executions | 5 |
| Successful | 3 (60%) |
| Partial | 1 (20%) |
| Failed | 1 (20%) |
| Average Duration | 1h 11m |
| Total Test Delta | +172 |

## Recent Executions

### document-7-reverse.md

- **Status:** ✅ All phases completed
- **Date:** 2024-12-06
- **Duration:** 1h 23m
- **Tests:** 280 → 312 (+32)
- **Phases:** 6/6 completed

...
```

### 8.5 CSV Format

```csv
execution_id,audit_document,started_at,status,duration_seconds,test_delta
abc12345,document-7-reverse.md,2024-12-06T10:30:00Z,success,5003,32
def67890,document-6-replay.md,2024-12-05T14:00:00Z,partial,3480,28
...
```

---

## 9. CI Integration

### 9.1 CI-Friendly Features

| Feature | Purpose |
|---------|---------|
| JSON output | Machine-readable for CI scripts |
| Exit codes | 0=success, 1=failed/partial executions found |
| Summary stats | Quick pass/fail for CI gates |
| Artifact export | Generate reports for CI artifacts |

### 9.2 CI Workflow Example

```yaml
# .github/workflows/audit.yml
name: Execute Audit

on:
  workflow_dispatch:
    inputs:
      audit_file:
        description: 'Audit document to execute'
        required: true

jobs:
  execute:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Execute Audit
        run: phaser execute ${{ inputs.audit_file }} --import-analytics
      
      - name: Export Analytics
        run: phaser analytics export --format json > analytics.json
      
      - name: Upload Analytics
        uses: actions/upload-artifact@v4
        with:
          name: analytics
          path: analytics.json
      
      - name: Check Success Rate
        run: |
          SUCCESS_RATE=$(phaser analytics show --format json | jq '.stats.success_rate')
          if (( $(echo "$SUCCESS_RATE < 0.8" | bc -l) )); then
            echo "Success rate below 80%"
            exit 1
          fi
```

### 9.3 CI-Specific Options

```bash
# Exit with code 1 if any failed executions
phaser analytics show --ci-exit-code

# Output minimal JSON for CI consumption
phaser analytics show --format json --ci-minimal

# Generate badge data
phaser analytics badge --format shields-io
# Output: {"schemaVersion":1,"label":"audits","message":"95%","color":"brightgreen"}
```

---

## 10. Data Classes

### 10.1 Imports

```python
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
```

### 10.2 ExecutionStatus Enum

```python
class ExecutionStatus(str, Enum):
    """Status of an audit execution."""
    
    SUCCESS = "success"       # All phases completed successfully
    PARTIAL = "partial"       # Some phases completed, some failed/skipped
    FAILED = "failed"         # Execution failed entirely
    
    @classmethod
    def from_report(cls, result_text: str) -> "ExecutionStatus":
        """Parse status from execution report result line."""
        if "All phases completed" in result_text:
            return cls.SUCCESS
        elif "Completed with issues" in result_text or "partial" in result_text.lower():
            return cls.PARTIAL
        else:
            return cls.FAILED
```

### 10.3 PhaseStatus Enum

```python
class PhaseStatus(str, Enum):
    """Status of a single phase."""
    
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    
    @classmethod
    def from_symbol(cls, symbol: str) -> "PhaseStatus":
        """Parse status from table symbol."""
        if symbol == "✅":
            return cls.COMPLETED
        elif symbol == "❌":
            return cls.FAILED
        else:
            return cls.SKIPPED
```

### 10.4 PhaseRecord

```python
@dataclass
class PhaseRecord:
    """Record of a single phase within an execution."""
    
    phase_number: int                     # 36
    title: str                            # "Reverse Audit Specification"
    status: PhaseStatus                   # COMPLETED, FAILED, SKIPPED
    commit_sha: str | None = None         # Commit hash if completed
    
    started_at: datetime | None = None    # Estimated from commit timestamps
    completed_at: datetime | None = None  # From commit timestamp
    duration_seconds: float | None = None
    
    tests_before: int | None = None       # If trackable
    tests_after: int | None = None        # If trackable
    
    error_message: str | None = None      # If failed
    retry_count: int = 0                  # Number of retries attempted
    
    def to_dict(self) -> dict[str, Any]:
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
        return cls(
            phase_number=data["phase_number"],
            title=data["title"],
            status=PhaseStatus(data["status"]),
            commit_sha=data.get("commit_sha"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            duration_seconds=data.get("duration_seconds"),
            tests_before=data.get("tests_before"),
            tests_after=data.get("tests_after"),
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
        )
```

### 10.5 ExecutionRecord

```python
@dataclass
class ExecutionRecord:
    """Complete record of a single audit execution."""
    
    # Identity
    execution_id: str                     # UUID
    audit_document: str                   # "document-7-reverse.md"
    document_title: str                   # "Document 7: Reverse Audit"
    
    # Location
    project_name: str                     # "Phaser"
    project_path: str                     # "/Users/jp/Projects/Phaser"
    branch: str                           # "audit/2024-12-06-reverse"
    
    # Timing
    started_at: datetime                  # ISO8601
    completed_at: datetime                # ISO8601
    
    # Versions
    phaser_version: str                   # "1.6.3"
    
    # Results
    status: ExecutionStatus               # SUCCESS, PARTIAL, FAILED
    phases_planned: int                   # Total phases in document
    phases_completed: int                 # Phases that succeeded
    
    # Tests
    baseline_tests: int                   # Tests before execution
    final_tests: int                      # Tests after execution
    
    # Git
    base_commit: str                      # Starting commit SHA
    final_commit: str                     # Ending commit SHA
    commit_count: int                     # Number of commits made
    files_changed: int                    # From git diff --stat
    
    # Phases
    phases: list[PhaseRecord] = field(default_factory=list)
    
    # Raw
    report_path: str = ""                 # Path to EXECUTION_REPORT.md
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
        return {
            "schema_version": "1.0",
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
            imported_at=datetime.fromisoformat(data["imported_at"]) if data.get("imported_at") else datetime.utcnow(),
        )
    
    @classmethod
    def generate_id(cls) -> str:
        """Generate a new execution ID."""
        return str(uuid.uuid4())
```

### 10.6 AggregatedStats

```python
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
        if self.total_executions == 0:
            return 0.0
        return self.successful / self.total_executions
    
    @property
    def phase_success_rate(self) -> float:
        if self.total_phases_executed == 0:
            return 0.0
        return self.total_phases_completed / self.total_phases_executed
    
    def to_dict(self) -> dict[str, Any]:
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
            "earliest_execution": self.earliest_execution.isoformat() if self.earliest_execution else None,
            "latest_execution": self.latest_execution.isoformat() if self.latest_execution else None,
        }
    
    @classmethod
    def compute(cls, records: list[ExecutionRecord]) -> "AggregatedStats":
        """Compute statistics from a list of execution records."""
        if not records:
            return cls(
                total_executions=0,
                successful=0, partial=0, failed=0,
                avg_duration_seconds=0, min_duration_seconds=0,
                max_duration_seconds=0, total_duration_seconds=0,
                total_test_delta=0, avg_test_delta=0,
                total_phases_executed=0, total_phases_completed=0,
                earliest_execution=None, latest_execution=None,
            )
        
        durations = [r.duration_seconds for r in records]
        test_deltas = [r.test_delta for r in records]
        timestamps = [r.started_at for r in records]
        
        return cls(
            total_executions=len(records),
            successful=sum(1 for r in records if r.status == ExecutionStatus.SUCCESS),
            partial=sum(1 for r in records if r.status == ExecutionStatus.PARTIAL),
            failed=sum(1 for r in records if r.status == ExecutionStatus.FAILED),
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
```

### 10.7 AnalyticsQuery

```python
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
        if self.document and self.document not in record.audit_document:
            return False
        return True
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "since": self.since.isoformat() if self.since else None,
            "until": self.until.isoformat() if self.until else None,
            "status": self.status.value if self.status else None,
            "document": self.document,
        }
```

---

## 11. Core Functions

### 11.1 Storage Operations

```python
def get_analytics_dir(project_dir: Path) -> Path:
    """
    Get the analytics directory for a project.
    
    Args:
        project_dir: Project root directory
    
    Returns:
        Path to .phaser/analytics/ directory
    """
    return project_dir / ".phaser" / "analytics"


def ensure_analytics_dir(project_dir: Path) -> Path:
    """
    Ensure analytics directory exists.
    
    Args:
        project_dir: Project root directory
    
    Returns:
        Path to .phaser/analytics/ directory (created if needed)
    """
    analytics_dir = get_analytics_dir(project_dir)
    analytics_dir.mkdir(parents=True, exist_ok=True)
    (analytics_dir / "executions").mkdir(exist_ok=True)
    return analytics_dir


def save_execution(record: ExecutionRecord, project_dir: Path) -> Path:
    """
    Save an execution record to disk.
    
    Args:
        record: ExecutionRecord to save
        project_dir: Project root directory
    
    Returns:
        Path to saved JSON file
    """


def load_execution(execution_id: str, project_dir: Path) -> ExecutionRecord:
    """
    Load an execution record from disk.
    
    Args:
        execution_id: UUID of execution to load
        project_dir: Project root directory
    
    Returns:
        ExecutionRecord
    
    Raises:
        AnalyticsError: If record not found
    """


def delete_execution(execution_id: str, project_dir: Path) -> None:
    """
    Delete an execution record.
    
    Args:
        execution_id: UUID of execution to delete
        project_dir: Project root directory
    
    Raises:
        AnalyticsError: If record not found
    """


def update_index(project_dir: Path) -> None:
    """
    Rebuild the analytics index from execution files.
    
    Args:
        project_dir: Project root directory
    """
```

### 11.2 Report Parsing

```python
def parse_execution_report(content: str) -> dict[str, Any]:
    """
    Parse EXECUTION_REPORT.md into structured data.
    
    Args:
        content: Raw markdown content of report
    
    Returns:
        Dictionary with all extracted fields
    
    Raises:
        ParseError: If required sections missing or malformed
    """


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
        ParseError: If report format is invalid
        AnalyticsError: If import fails
    """


def detect_execution_reports(project_dir: Path) -> list[Path]:
    """
    Find execution reports in project directory.
    
    Args:
        project_dir: Directory to search
    
    Returns:
        List of paths to EXECUTION_REPORT.md files
    """
```

### 11.3 Query and Aggregation

```python
def query_executions(
    project_dir: Path,
    query: AnalyticsQuery,
) -> list[ExecutionRecord]:
    """
    Query execution records matching criteria.
    
    Args:
        project_dir: Project root directory
        query: Query parameters
    
    Returns:
        List of matching ExecutionRecords, sorted by date descending
    """


def compute_stats(records: list[ExecutionRecord]) -> AggregatedStats:
    """
    Compute aggregated statistics from execution records.
    
    Args:
        records: List of execution records
    
    Returns:
        AggregatedStats with computed values
    """


def get_global_executions(
    query: AnalyticsQuery,
) -> list[tuple[str, ExecutionRecord]]:
    """
    Query executions across all known projects.
    
    Args:
        query: Query parameters
    
    Returns:
        List of (project_name, ExecutionRecord) tuples
    """
```

### 11.4 Output Formatting

```python
def format_table(
    records: list[ExecutionRecord],
    stats: AggregatedStats,
    verbose: bool = False,
) -> str:
    """
    Format execution data as ASCII table.
    
    Args:
        records: Execution records to display
        stats: Aggregated statistics
        verbose: Include per-phase details
    
    Returns:
        Formatted table string
    """


def format_json(
    records: list[ExecutionRecord],
    stats: AggregatedStats,
    query: AnalyticsQuery,
    project_name: str,
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


def format_markdown(
    records: list[ExecutionRecord],
    stats: AggregatedStats,
) -> str:
    """
    Format execution data as markdown report.
    
    Args:
        records: Execution records
        stats: Aggregated statistics
    
    Returns:
        Markdown string
    """


def format_csv(records: list[ExecutionRecord]) -> str:
    """
    Format execution data as CSV.
    
    Args:
        records: Execution records
    
    Returns:
        CSV string with header row
    """


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable form.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string like "1h 23m" or "45m 12s"
    """
```

---

## 12. CLI Implementation

### 12.1 Command Group

```python
import click
from pathlib import Path

@click.group()
def analytics():
    """View and manage execution analytics."""
    pass


@cli.add_command
def analytics():
    """Analytics command group."""
    pass
```

### 12.2 show Command

```python
@analytics.command()
@click.option('--last', 'limit', type=int, default=5, help='Number of executions to show')
@click.option('--since', type=click.DateTime(), help='Show executions since date')
@click.option('--until', type=click.DateTime(), help='Show executions until date')
@click.option('--status', type=click.Choice(['success', 'partial', 'failed', 'all']), default='all')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'markdown']), default='table')
@click.option('--verbose', '-v', is_flag=True, help='Show per-phase details')
@click.option('--global', 'global_', is_flag=True, help='Aggregate across all projects')
@click.option('--project', type=click.Path(exists=True), help='Project directory')
def show(limit, since, until, status, output_format, verbose, global_, project):
    """Show execution analytics."""
    project_dir = Path(project) if project else Path.cwd()
    
    query = AnalyticsQuery(
        limit=limit,
        since=since,
        until=until,
        status=ExecutionStatus(status) if status != 'all' else None,
    )
    
    if global_:
        records = get_global_executions(query)
    else:
        records = query_executions(project_dir, query)
    
    stats = compute_stats(records)
    
    if output_format == 'json':
        output = format_json(records, stats, query, project_dir.name)
    elif output_format == 'markdown':
        output = format_markdown(records, stats)
    else:
        output = format_table(records, stats, verbose=verbose)
    
    click.echo(output)
```

### 12.3 export Command

```python
@analytics.command()
@click.option('--format', 'output_format', type=click.Choice(['json', 'markdown', 'csv']), default='json')
@click.option('--output', '-o', type=click.Path(), help='Output file')
@click.option('--since', type=click.DateTime())
@click.option('--until', type=click.DateTime())
@click.option('--global', 'global_', is_flag=True)
@click.option('--project', type=click.Path(exists=True))
def export(output_format, output, since, until, global_, project):
    """Export analytics data."""
    project_dir = Path(project) if project else Path.cwd()
    
    query = AnalyticsQuery(since=since, until=until)
    records = query_executions(project_dir, query)
    stats = compute_stats(records)
    
    if output_format == 'json':
        content = format_json(records, stats, query, project_dir.name)
    elif output_format == 'markdown':
        content = format_markdown(records, stats)
    else:
        content = format_csv(records)
    
    if output:
        Path(output).write_text(content)
        click.echo(f"Exported to {output}")
    else:
        click.echo(content)
```

### 12.4 clear Command

```python
@analytics.command()
@click.option('--before', type=click.DateTime(), help='Clear executions before date')
@click.option('--all', 'clear_all', is_flag=True, help='Clear all data')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted')
@click.option('--project', type=click.Path(exists=True))
def clear(before, clear_all, force, dry_run, project):
    """Clear analytics data."""
    project_dir = Path(project) if project else Path.cwd()
    
    if not clear_all and not before:
        raise click.UsageError("Must specify --all or --before")
    
    query = AnalyticsQuery(until=before) if before else AnalyticsQuery()
    records = query_executions(project_dir, query)
    
    if dry_run:
        click.echo(f"Would delete {len(records)} execution records:")
        for r in records[:10]:
            click.echo(f"  - {r.audit_document} ({r.started_at.date()})")
        if len(records) > 10:
            click.echo(f"  ... and {len(records) - 10} more")
        return
    
    if not force:
        click.confirm(f"Delete {len(records)} execution records?", abort=True)
    
    for record in records:
        delete_execution(record.execution_id, project_dir)
    
    update_index(project_dir)
    click.echo(f"Deleted {len(records)} execution records.")
```

### 12.5 import Command

```python
@analytics.command('import')
@click.argument('report_file', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, help='Scan directory recursively')
@click.option('--force', '-f', is_flag=True, help='Re-import existing records')
@click.option('--project', type=click.Path(exists=True))
def import_cmd(report_file, recursive, force, project):
    """Import execution data from EXECUTION_REPORT.md files."""
    project_dir = Path(project) if project else Path.cwd()
    report_path = Path(report_file)
    
    if report_path.is_dir():
        if recursive:
            reports = list(report_path.rglob('EXECUTION_REPORT.md'))
        else:
            reports = list(report_path.glob('EXECUTION_REPORT.md'))
    else:
        reports = [report_path]
    
    imported = 0
    errors = []
    
    for report in reports:
        try:
            record = import_execution_report(report, project_dir)
            save_execution(record, project_dir)
            imported += 1
            click.echo(f"✓ Imported: {record.audit_document}")
        except Exception as e:
            errors.append((report, str(e)))
            click.echo(f"✗ Failed: {report} - {e}")
    
    update_index(project_dir)
    click.echo(f"\nImported {imported} execution(s).")
    if errors:
        click.echo(f"Failed: {len(errors)}")
```

---

## 13. Error Handling

### 13.1 Exception Classes

```python
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
```

### 13.2 Error Messages

| Scenario | Message |
|----------|---------|
| No analytics data | `No analytics data found. Run 'phaser analytics import EXECUTION_REPORT.md' to import.` |
| Report not found | `Execution report not found: {path}` |
| Invalid report | `Cannot parse execution report: {details}` |
| Storage permission | `Cannot write to analytics directory: {path}` |
| Invalid date | `Invalid date format. Use ISO format: YYYY-MM-DD` |
| Execution not found | `Execution not found: {id}` |

---

## 14. Testing Requirements

### 14.1 Test Categories

| Category | Count | Coverage Target |
|----------|-------|-----------------|
| Data Classes | 25+ | Serialization, deserialization, computed properties |
| Report Parsing | 20+ | All report sections, edge cases, malformed reports |
| Storage | 15+ | CRUD operations, index updates, concurrency |
| Query | 15+ | Filters, sorting, limits, aggregation |
| Output Formatting | 15+ | All formats, edge cases |
| CLI | 20+ | All commands, options, error handling |
| Integration | 5+ | End-to-end workflows |

### 14.2 Key Test Cases

```python
class TestExecutionRecord:
    def test_to_dict_includes_all_fields(self): ...
    def test_from_dict_round_trip(self): ...
    def test_duration_seconds_computed(self): ...
    def test_test_delta_computed(self): ...
    def test_success_rate_computed(self): ...
    def test_generate_id_unique(self): ...


class TestPhaseRecord:
    def test_to_dict_includes_all_fields(self): ...
    def test_from_dict_round_trip(self): ...
    def test_status_from_symbol_completed(self): ...
    def test_status_from_symbol_failed(self): ...
    def test_status_from_symbol_skipped(self): ...


class TestAggregatedStats:
    def test_compute_empty_list(self): ...
    def test_compute_single_record(self): ...
    def test_compute_multiple_records(self): ...
    def test_success_rate_calculation(self): ...
    def test_phase_success_rate_calculation(self): ...
    def test_duration_min_max_avg(self): ...


class TestReportParsing:
    def test_parse_valid_report(self): ...
    def test_parse_metadata_table(self): ...
    def test_parse_phase_table(self): ...
    def test_parse_test_results(self): ...
    def test_parse_git_history(self): ...
    def test_parse_missing_section_error(self): ...
    def test_parse_malformed_table_error(self): ...
    def test_parse_real_report_fixture(self): ...


class TestStorage:
    def test_save_execution_creates_file(self): ...
    def test_save_execution_updates_index(self): ...
    def test_load_execution_returns_record(self): ...
    def test_load_execution_not_found(self): ...
    def test_delete_execution_removes_file(self): ...
    def test_delete_execution_updates_index(self): ...
    def test_update_index_rebuilds(self): ...
    def test_ensure_analytics_dir_creates(self): ...


class TestQuery:
    def test_query_no_filters(self): ...
    def test_query_limit(self): ...
    def test_query_since(self): ...
    def test_query_until(self): ...
    def test_query_status_filter(self): ...
    def test_query_document_filter(self): ...
    def test_query_combined_filters(self): ...
    def test_query_sorted_by_date(self): ...


class TestOutputFormatting:
    def test_format_table_basic(self): ...
    def test_format_table_verbose(self): ...
    def test_format_table_empty(self): ...
    def test_format_json_valid(self): ...
    def test_format_json_includes_stats(self): ...
    def test_format_markdown_sections(self): ...
    def test_format_csv_header(self): ...
    def test_format_csv_escaping(self): ...
    def test_format_duration_hours(self): ...
    def test_format_duration_minutes(self): ...


class TestCLI:
    def test_show_default(self): ...
    def test_show_with_limit(self): ...
    def test_show_json_format(self): ...
    def test_show_verbose(self): ...
    def test_export_json(self): ...
    def test_export_to_file(self): ...
    def test_clear_with_confirmation(self): ...
    def test_clear_dry_run(self): ...
    def test_clear_force_no_confirm(self): ...
    def test_import_single_file(self): ...
    def test_import_directory(self): ...
    def test_import_recursive(self): ...
    def test_error_no_analytics_data(self): ...
    def test_error_invalid_date(self): ...


class TestIntegration:
    def test_full_workflow_import_query_export(self): ...
    def test_import_after_execute(self): ...
    def test_clear_then_import(self): ...
    def test_global_aggregation(self): ...
```

---

## 15. Example Workflow

### 15.1 Basic Usage

```bash
# Execute an audit
$ phaser execute document-7-reverse.md
[... execution proceeds ...]
✓ EXECUTION_REPORT.md generated

# Import analytics
$ phaser analytics import EXECUTION_REPORT.md
✓ Imported: document-7-reverse.md

# View analytics
$ phaser analytics show

╭──────────────────────────────────────────────────────────────────────╮
│                    Phaser Analytics - Last 5 Executions              │
├──────────────────────────────────────────────────────────────────────┤
│ Date       │ Document                 │ Status │ Duration │ Δ Tests │
├────────────┼──────────────────────────┼────────┼──────────┼─────────┤
│ 2024-12-06 │ document-7-reverse.md    │ ✅     │ 1h 23m   │ +32     │
╰──────────────────────────────────────────────────────────────────────╯

Summary: 1 execution | 1 successful (100%) | Avg: 1h 23m | Total Δ: +32 tests
```

### 15.2 Detailed View

```bash
$ phaser analytics show --verbose

╭──────────────────────────────────────────────────────────────────────╮
│                    document-7-reverse.md - Details                    │
├──────────────────────────────────────────────────────────────────────┤
│ Started:    2024-12-06T10:30:00Z                                     │
│ Completed:  2024-12-06T11:53:23Z                                     │
│ Duration:   1h 23m 23s                                               │
│ Status:     ✅ All phases completed                                  │
│ Branch:     audit/2024-12-06-reverse                                 │
├──────────────────────────────────────────────────────────────────────┤
│ Phase │ Title                          │ Status │ Commit  │
├───────┼────────────────────────────────┼────────┼─────────┤
│    36 │ Reverse Audit Specification    │ ✅     │ b2c3d4e │
│    37 │ Git Diff Parsing               │ ✅     │ c3d4e5f │
│    38 │ Change Detection               │ ✅     │ d4e5f6g │
│    39 │ Document Generation            │ ✅     │ e5f6g7h │
│    40 │ CLI Integration                │ ✅     │ f6g7h8i │
│    41 │ Testing                        │ ✅     │ g7h8i9j │
╰──────────────────────────────────────────────────────────────────────╯
```

### 15.3 Export for CI

```bash
$ phaser analytics export --format json > analytics.json
$ cat analytics.json | jq '.stats.success_rate'
1.0
```

### 15.4 Historical Analysis

```bash
# View failed executions from last month
$ phaser analytics show --since 2024-11-01 --status failed

# Clear old data
$ phaser analytics clear --before 2024-06-01 --force
Deleted 23 execution records.
```

---

## 16. Future Considerations

### 16.1 Not In Scope (v1.7)

| Feature | Rationale |
|---------|-----------|
| Real-time capture | Requires Claude Code integration |
| SQLite storage | JSON sufficient for typical volumes |
| Token usage | Requires API integration |
| Web dashboard | CLI-first approach |
| Anomaly detection | Complex analytics, v1.9+ |

### 16.2 Potential v1.8 Features

- **Real-time hooks:** Capture per-phase timing during execution
- **SQLite migration:** For projects with 1000+ executions
- **Trend charts:** ASCII charts for duration/test trends
- **Alerts:** Notify on failure or regression
- **Comparison:** Compare two executions side-by-side

### 16.3 Potential v1.9 Features

- **Token tracking:** Per-phase token usage if API integrated
- **Cross-project dashboard:** Web UI for organization-wide view
- **Anomaly detection:** Flag unusual execution patterns
- **Predictions:** Estimate execution time based on history

---

## 17. Glossary

| Term | Definition |
|------|------------|
| Aggregated Stats | Computed statistics across multiple executions |
| Analytics | Metrics and historical data about audit executions |
| Baseline Tests | Number of tests before an audit begins |
| Execution | A single run of an audit document |
| Execution ID | UUID uniquely identifying an execution |
| Execution Record | Complete data about a single execution |
| Index | Fast-lookup file for execution metadata |
| Phase Record | Data about a single phase within an execution |
| Test Delta | Change in test count (final - baseline) |

---

*Phaser v1.7 — Analytics Specification*
