# Phaser v1.2 Event Specification

## Overview

The event system captures audit activities as typed, immutable records. Events enable:

- **Replay** — Reconstruct audit timeline for debugging
- **Insights** — Analyze patterns across audits
- **Streaming** — Real-time progress monitoring
- **CI Integration** — Machine-readable audit results

---

## Event Types

### Audit Lifecycle Events

| Type | Trigger | Description |
|------|---------|-------------|
| `audit_started` | Setup block parsed | New audit initialized |
| `audit_completed` | All phases done | Audit finished successfully |
| `audit_abandoned` | User abandons | Audit terminated early |

### Phase Events

| Type | Trigger | Description |
|------|---------|-------------|
| `phase_started` | Phase execution begins | Starting phase N |
| `phase_completed` | Phase verified | Phase N succeeded |
| `phase_failed` | Verification fails after retries | Phase N failed |
| `phase_skipped` | User skips | Phase N skipped |

### Verification Events

| Type | Trigger | Description |
|------|---------|-------------|
| `verification_passed` | Verify command exits 0 | Command succeeded |
| `verification_failed` | Verify command exits non-0 | Command failed |

### File Events

| Type | Trigger | Description |
|------|---------|-------------|
| `file_created` | New file written | File added to project |
| `file_modified` | Existing file changed | File content updated |
| `file_deleted` | File removed | File deleted from project |

---

## Event Schema

### Base Schema

All events share these fields:

```json
{
  "id": "string (UUID v4)",
  "type": "string (EventType enum)",
  "timestamp": "string (ISO 8601 with milliseconds)",
  "audit_id": "string (UUID v4)",
  "phase": "int | null",
  "data": "object"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique event identifier (UUID v4) |
| `type` | EventType | Yes | Event type from enum |
| `timestamp` | string | Yes | ISO 8601 with milliseconds (`2025-12-05T10:15:30.123Z`) |
| `audit_id` | string | Yes | Parent audit UUID |
| `phase` | int \| null | No | Phase number (1-indexed, null for audit-level events) |
| `data` | object | No | Type-specific payload (defaults to `{}`) |

### Type-Specific Payloads

#### audit_started

```json
{
  "data": {
    "project": "Phaser",
    "slug": "v1.2-infrastructure",
    "phases_total": 6,
    "git_branch": "main",
    "git_commit": "abc123def"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Project name |
| `slug` | string | Audit identifier |
| `phases_total` | int | Total number of phases |
| `git_branch` | string | Current git branch (optional) |
| `git_commit` | string | Current commit SHA (optional) |

#### audit_completed

```json
{
  "data": {
    "duration_seconds": 5400.5,
    "phases_completed": 6,
    "phases_skipped": 0,
    "files_created": 8,
    "files_modified": 2,
    "files_deleted": 0
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `duration_seconds` | float | Total audit duration |
| `phases_completed` | int | Count of completed phases |
| `phases_skipped` | int | Count of skipped phases |
| `files_created` | int | Total files created |
| `files_modified` | int | Total files modified |
| `files_deleted` | int | Total files deleted |

#### audit_abandoned

```json
{
  "data": {
    "reason": "user_request",
    "phases_completed": 2,
    "phases_remaining": 4
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `reason` | string | Why abandoned (`user_request`, `error`, `timeout`) |
| `phases_completed` | int | Phases finished before abandon |
| `phases_remaining` | int | Phases not started |

#### phase_started

```json
{
  "phase": 3,
  "data": {
    "description": "Event Specification",
    "file": ".audit/phases/03-events-spec.md"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Phase title |
| `file` | string | Phase file path |

#### phase_completed

```json
{
  "phase": 3,
  "data": {
    "duration_seconds": 120.5,
    "files_created": 1,
    "files_modified": 0,
    "verification_count": 6
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `duration_seconds` | float | Phase execution time |
| `files_created` | int | Files created in phase |
| `files_modified` | int | Files modified in phase |
| `verification_count` | int | Number of verify commands run |

#### phase_failed

```json
{
  "phase": 3,
  "data": {
    "error": "Verification command failed: grep -q \"Schema\" specs/events.md",
    "attempts": 3,
    "duration_seconds": 45.2
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error` | string | Error message |
| `attempts` | int | Number of retry attempts |
| `duration_seconds` | float | Total time including retries |

#### phase_skipped

```json
{
  "phase": 3,
  "data": {
    "reason": "user_request"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `reason` | string | Why skipped (`user_request`, `dependency_failed`) |

#### verification_passed

```json
{
  "phase": 3,
  "data": {
    "command": "grep -q \"Schema\" specs/events.md",
    "exit_code": 0,
    "duration_ms": 12
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Command that was run |
| `exit_code` | int | Exit code (always 0) |
| `duration_ms` | int | Execution time in milliseconds |

#### verification_failed

```json
{
  "phase": 3,
  "data": {
    "command": "python -m pytest tests/ -v",
    "exit_code": 1,
    "duration_ms": 3500,
    "output": "FAILED tests/test_events.py::test_emit - AssertionError"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Command that was run |
| `exit_code` | int | Non-zero exit code |
| `duration_ms` | int | Execution time in milliseconds |
| `output` | string | Truncated stderr/stdout (max 1000 chars) |

#### file_created

```json
{
  "phase": 3,
  "data": {
    "path": "specs/events.md",
    "size_bytes": 4521
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Relative file path |
| `size_bytes` | int | File size in bytes |

#### file_modified

```json
{
  "phase": 3,
  "data": {
    "path": ".audit/CONTEXT.md",
    "size_bytes": 2100,
    "lines_added": 5,
    "lines_removed": 2
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Relative file path |
| `size_bytes` | int | New file size |
| `lines_added` | int | Lines added |
| `lines_removed` | int | Lines removed |

#### file_deleted

```json
{
  "phase": 3,
  "data": {
    "path": "old_file.txt"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Relative file path |

---

## Event Lifecycle

### 1. Emission

```
User Action
    │
    ▼
EventEmitter.emit(type, audit_id, phase?, **data)
    │
    ├─── Generate UUID
    ├─── Generate timestamp
    ├─── Create Event instance
    │
    ▼
Event object created
```

### 2. Persistence

```
Event object
    │
    ▼
EventEmitter (if storage attached)
    │
    ├─── event.to_dict()
    ├─── storage.append_event(dict)
    │
    ▼
Written to events.json
```

### 3. Subscription

```
Event object
    │
    ▼
EventEmitter._subscribers
    │
    ├─── callback_1(event)
    ├─── callback_2(event)
    └─── callback_N(event)
    │
    ▼
All subscribers notified (synchronous)
```

### 4. Query

```
storage.get_events(audit_id?, event_type?, since?)
    │
    ├─── Read events.json
    ├─── Apply filters
    ├─── Sort by timestamp
    │
    ▼
list[dict] returned
```

### 5. Replay

```
emitter.replay(audit_id, callback)
    │
    ├─── storage.get_events(audit_id=audit_id)
    ├─── Sort by timestamp
    ├─── For each event:
    │        └─── callback(Event.from_dict(e))
    │
    ▼
int (count of events replayed)
```

---

## Subscription Patterns

### Basic Subscription

```python
def on_event(event: Event) -> None:
    print(f"[{event.type}] {event.timestamp}")

emitter.subscribe(on_event)
```

### Filtered Subscription

```python
def on_phase_event(event: Event) -> None:
    if event.type.startswith("phase_"):
        print(f"Phase {event.phase}: {event.type}")

emitter.subscribe(on_phase_event)
```

### Unsubscription

```python
emitter.unsubscribe(on_event)
```

### Subscriber Error Handling

```python
# If a subscriber raises an exception:
# 1. Log the error
# 2. Continue to remaining subscribers
# 3. Do NOT re-raise (event emission succeeds)
```

---

## Event Versioning

### Current Version: 1

The event schema is versioned to support future changes:

```json
{
  "version": 1,
  "events": [...]
}
```

### Versioning Rules

1. **Additive changes** (new optional fields) — No version bump
2. **New event types** — No version bump
3. **Field type changes** — Version bump required
4. **Field removal** — Version bump required
5. **Required field addition** — Version bump required

### Forward Compatibility

- Unknown fields are preserved when reading/writing
- Unknown event types are preserved but not processed
- Newer clients can read older event files

### Backward Compatibility

- Older clients may not understand new event types
- Migration applied on first read if version mismatch

---

## Implementation Reference

### EventType Enum

```python
from enum import Enum

class EventType(str, Enum):
    # Audit lifecycle
    AUDIT_STARTED = "audit_started"
    AUDIT_COMPLETED = "audit_completed"
    AUDIT_ABANDONED = "audit_abandoned"

    # Phase events
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    PHASE_SKIPPED = "phase_skipped"

    # Verification events
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"

    # File events
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
```

### Event Dataclass

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class Event:
    id: str
    type: EventType
    timestamp: str
    audit_id: str
    phase: int | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "audit_id": self.audit_id,
            "phase": self.phase,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Event":
        return cls(
            id=d["id"],
            type=EventType(d["type"]),
            timestamp=d["timestamp"],
            audit_id=d["audit_id"],
            phase=d.get("phase"),
            data=d.get("data", {}),
        )
```

### Convenience Functions

```python
def emit_audit_started(
    emitter: EventEmitter,
    audit_id: str,
    project: str,
    slug: str,
    phases_total: int,
    **kwargs: Any,
) -> Event:
    return emitter.emit(
        EventType.AUDIT_STARTED,
        audit_id,
        project=project,
        slug=slug,
        phases_total=phases_total,
        **kwargs,
    )

def emit_phase_completed(
    emitter: EventEmitter,
    audit_id: str,
    phase: int,
    duration_seconds: float,
    **kwargs: Any,
) -> Event:
    return emitter.emit(
        EventType.PHASE_COMPLETED,
        audit_id,
        phase=phase,
        duration_seconds=duration_seconds,
        **kwargs,
    )
```

---

## Implementation Checklist

- [ ] `EventType` enum with all 12 event types
- [ ] `Event` dataclass with `to_dict()` and `from_dict()`
- [ ] `EventEmitter.__init__()` with optional storage
- [ ] `EventEmitter.emit()` — create and dispatch event
- [ ] `EventEmitter.subscribe()` — register callback
- [ ] `EventEmitter.unsubscribe()` — remove callback
- [ ] `EventEmitter.replay()` — replay historical events
- [ ] Convenience functions for common events
- [ ] Storage integration (persist on emit)
- [ ] Subscriber error isolation

---

*Phaser v1.2 Event Specification — Document 1, Phase 3*
