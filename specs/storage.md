# Phaser v1.2 Storage Specification

## Overview

The storage layer manages persistent state in the `.phaser/` directory. It supports two modes:

- **Global storage** (`~/.phaser/`) — Shared across all projects
- **Project-local storage** (`.phaser/` in project root) — Project-specific data

The implementation auto-detects the appropriate location based on context.

---

## Directory Structure

### Global Storage (`~/.phaser/`)

```
~/.phaser/
├── audits.json           # Audit history (all projects)
├── events.json           # Event log (all events)
├── config.yaml           # User preferences
├── insights.json         # Derived analytics (future)
└── manifests/            # Pre/post audit manifests (Doc 2)
    └── {audit_id}/
        ├── pre.json
        └── post.json
```

### Project-Local Storage (`.phaser/`)

```
{project}/.phaser/
├── audits.json           # Project-specific audits only
├── events.json           # Project-specific events only
└── manifests/            # Project-specific manifests
    └── {audit_id}/
        ├── pre.json
        └── post.json
```

### Location Resolution

```python
def find_phaser_root() -> Path:
    """
    Resolution order:
    1. If PHASER_STORAGE_DIR env var set, use that
    2. If .phaser/ exists in current project, use project-local
    3. Otherwise, use global ~/.phaser/
    """
```

---

## File Formats

| File | Format | Purpose |
|------|--------|---------|
| `audits.json` | JSON | Audit history records |
| `events.json` | JSON | Event log (append-only) |
| `config.yaml` | YAML | User preferences |
| `insights.json` | JSON | Derived analytics (future) |

### Why JSON for Data, YAML for Config?

- **JSON**: Machine-readable, fast parsing, no ambiguity
- **YAML**: Human-editable, supports comments, readable defaults

---

## Schema Definitions

### audits.json

```json
{
  "version": 1,
  "audits": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "project": "Phaser",
      "slug": "v1.2-infrastructure",
      "date": "2025-12-05",
      "status": "completed",
      "phases_total": 6,
      "phases_completed": 6,
      "phases_skipped": 0,
      "started_at": "2025-12-05T10:00:00Z",
      "completed_at": "2025-12-05T12:30:00Z",
      "tags": ["infrastructure", "v1.2"],
      "metadata": {
        "git_branch": "main",
        "git_commit": "abc123"
      }
    }
  ]
}
```

#### Audit Record Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string (UUID) | Yes | Unique identifier |
| `project` | string | Yes | Project name |
| `slug` | string | Yes | Audit identifier |
| `date` | string (YYYY-MM-DD) | Yes | Audit date |
| `status` | enum | Yes | `pending`, `in_progress`, `completed`, `abandoned` |
| `phases_total` | int | Yes | Total phase count |
| `phases_completed` | int | Yes | Completed phase count |
| `phases_skipped` | int | Yes | Skipped phase count |
| `started_at` | string (ISO 8601) | Yes | Start timestamp |
| `completed_at` | string (ISO 8601) | No | Completion timestamp |
| `tags` | array[string] | No | User-defined tags |
| `metadata` | object | No | Arbitrary key-value data |

### events.json

```json
{
  "version": 1,
  "events": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "type": "phase_completed",
      "timestamp": "2025-12-05T10:15:30.123Z",
      "audit_id": "550e8400-e29b-41d4-a716-446655440000",
      "phase": 1,
      "data": {
        "duration": 45.2,
        "files_changed": 2
      }
    }
  ]
}
```

#### Event Record Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string (UUID) | Yes | Unique event identifier |
| `type` | string (EventType) | Yes | Event type enum value |
| `timestamp` | string (ISO 8601) | Yes | Event timestamp with milliseconds |
| `audit_id` | string (UUID) | Yes | Parent audit reference |
| `phase` | int | No | Phase number (for phase events) |
| `data` | object | No | Type-specific payload |

### config.yaml

```yaml
# Phaser configuration
version: 1

storage:
  # Where to store data: "global" (~/.phaser/) or "project" (.phaser/)
  location: global

  # Maximum events to retain (oldest pruned first)
  max_events: 10000

  # Days to retain events (0 = forever)
  retention_days: 90

features:
  # Enable audit diff capture
  diffs: true

  # Enable contract extraction
  contracts: true

  # Enable simulation mode
  simulation: true

  # Enable branch mapping
  branches: true

display:
  # Show verbose output
  verbose: false

  # Color output (auto, always, never)
  color: auto
```

#### Config Default Values

```python
DEFAULT_CONFIG = {
    "version": 1,
    "storage": {
        "location": "global",
        "max_events": 10000,
        "retention_days": 90,
    },
    "features": {
        "diffs": True,
        "contracts": True,
        "simulation": True,
        "branches": True,
    },
    "display": {
        "verbose": False,
        "color": "auto",
    },
}
```

---

## File Naming Conventions

| Pattern | Example | Purpose |
|---------|---------|---------|
| `{type}.json` | `audits.json` | Primary data files |
| `{type}.yaml` | `config.yaml` | Configuration files |
| `{audit_id}/` | `550e8400.../` | Audit-specific subdirectories |
| `*.json.tmp` | `audits.json.tmp` | Temporary files during atomic write |
| `*.json.bak` | `audits.json.bak` | Backup before destructive operations |

---

## Locking and Concurrency

### File Locking Strategy

```python
import fcntl  # Unix
# or
import msvcrt  # Windows

def atomic_write(path: Path, data: str) -> None:
    """
    1. Write to {path}.tmp
    2. Acquire exclusive lock on {path}
    3. Rename {path}.tmp to {path} (atomic on POSIX)
    4. Release lock
    """
```

### Lock Types

| Operation | Lock Type | Scope |
|-----------|-----------|-------|
| Read | Shared (LOCK_SH) | Per-file |
| Write | Exclusive (LOCK_EX) | Per-file |
| Append (events) | Exclusive (LOCK_EX) | Per-file |

### Contention Handling

```python
MAX_RETRIES = 3
RETRY_DELAYS = [0.1, 0.3, 1.0]  # Exponential backoff

def with_retry(operation: Callable) -> Any:
    for i, delay in enumerate(RETRY_DELAYS):
        try:
            return operation()
        except BlockingIOError:
            if i == MAX_RETRIES - 1:
                raise
            time.sleep(delay)
```

---

## Migration Strategy

### Schema Versioning

Each file includes a `version` field at the root:

```json
{
  "version": 1,
  "audits": [...]
}
```

### Migration Process

```python
def migrate_if_needed(path: Path, current_version: int) -> dict:
    """
    1. Read file and check version
    2. If version < current_version, apply migrations in order
    3. Write migrated data back
    4. Return migrated data
    """

MIGRATIONS = {
    # version -> migration function
    2: migrate_v1_to_v2,
    3: migrate_v2_to_v3,
}
```

### Backwards Compatibility

- Migrations are one-way (no downgrades)
- Unknown fields are preserved (forward compatibility)
- Breaking changes require major version bump

---

## Storage Limits and Cleanup

### Default Limits

| Resource | Default Limit | Configurable |
|----------|---------------|--------------|
| Events | 10,000 records | Yes (`max_events`) |
| Event retention | 90 days | Yes (`retention_days`) |
| Audits | Unlimited | No |
| Manifests | Per-audit | Pruned with audit |

### Cleanup Policy

```python
def cleanup_events(storage: PhaserStorage) -> int:
    """
    Remove events that match ANY of:
    1. Older than retention_days (if > 0)
    2. Exceed max_events count (oldest first)

    Returns: number of events removed
    """
```

### Manual Cleanup

```python
# Remove events older than 30 days
storage.clear_events(before=datetime.now() - timedelta(days=30))

# Reset to defaults (preserves audits)
storage.reset_config()
```

---

## Access Patterns

### Read Operations

| Method | Returns | Notes |
|--------|---------|-------|
| `get_audit(id)` | `dict | None` | Single audit by ID |
| `list_audits(project=None)` | `list[dict]` | All or filtered by project |
| `get_events(audit_id=None, event_type=None, since=None)` | `list[dict]` | Filtered event query |
| `get_config()` | `dict` | Config with defaults merged |

### Write Operations

| Method | Returns | Notes |
|--------|---------|-------|
| `save_audit(audit)` | `str` | Returns generated UUID |
| `update_audit(id, updates)` | `bool` | True if found and updated |
| `append_event(event)` | `None` | Appends to event log |
| `set_config(key, value)` | `None` | Dot-notation keys supported |
| `reset_config()` | `None` | Restores defaults |

### Delete Operations

| Method | Returns | Notes |
|--------|---------|-------|
| `clear_events(before=None)` | `int` | Count of removed events |

---

## Error Handling

| Error Condition | Exception | Recovery |
|----------------|-----------|----------|
| Directory not writable | `PermissionError` | User must fix permissions |
| Invalid JSON/YAML | `ValueError` | Log error, use defaults |
| File locked | `BlockingIOError` | Retry with backoff |
| Disk full | `OSError` | Abort, preserve existing data |
| Missing required field | `ValueError` | Reject operation |
| Unknown audit ID | Return `None` / `False` | Caller handles |

---

## Implementation Checklist

- [ ] `PhaserStorage.__init__()` — Auto-detect or accept root path
- [ ] `ensure_directories()` — Create .phaser/ structure
- [ ] `get_path()` — Resolve paths within .phaser/
- [ ] `save_audit()` — Create new audit record
- [ ] `get_audit()` — Retrieve by ID
- [ ] `list_audits()` — List with optional project filter
- [ ] `update_audit()` — Partial update existing audit
- [ ] `append_event()` — Add to event log
- [ ] `get_events()` — Query with filters
- [ ] `clear_events()` — Remove old events
- [ ] `get_config()` — Load with defaults
- [ ] `set_config()` — Update single value
- [ ] `reset_config()` — Restore defaults
- [ ] Atomic writes via temp-then-rename
- [ ] File locking for concurrent access

---

*Phaser v1.2 Storage Specification — Document 1, Phase 2*
