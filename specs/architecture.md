# Phaser v1.2 Architecture Specification

## Overview

Phaser v1.2 introduces the **Learning Loop** infrastructure: a persistent storage layer and event system that enables audit history tracking, replay capabilities, and cross-audit insights. This foundation supports all subsequent v1.2 features:

- **Audit Diffs** — Compare codebase state before/after audits
- **Audit Contracts** — Extract and enforce rules from audit patterns
- **Simulation** — Dry-run audits without file modifications
- **Branches** — Map audits to git branches for parallel work

### Design Principles

1. **Self-contained tools** — Each module works standalone without requiring the full system
2. **Fail fast** — Errors surface immediately with actionable context
3. **Atomic operations** — File writes are crash-safe via temp-then-rename
4. **Minimal dependencies** — Only pyyaml, click, pytest required

---

## Components

### Directory Structure

```
Phaser/
├── specs/                    # Specifications (this audit creates)
│   ├── architecture.md       # System design (this file)
│   ├── storage.md            # Storage layer spec
│   └── events.md             # Event system spec
│
├── tools/                    # Implementation modules
│   ├── __init__.py           # Package marker
│   ├── storage.py            # PhaserStorage class
│   ├── events.py             # EventEmitter class
│   ├── diff.py               # (Doc 2) Manifest diffing
│   ├── contracts.py          # (Doc 2) Rule enforcement
│   ├── simulate.py           # (Doc 3) Dry-run engine
│   └── branches.py           # (Doc 3) Branch mapping
│
├── tests/                    # Test suites
│   ├── __init__.py
│   ├── conftest.py           # Shared fixtures
│   ├── test_storage.py
│   └── test_events.py
│
├── templates/                # (Existing) Audit templates
│   ├── CONTEXT.template.md
│   ├── CURRENT.template.md
│   └── phase.template.md
│
└── .phaser/                  # Runtime storage (created by tools)
    ├── audits.json           # Audit history
    ├── events.json           # Event log
    └── config.yaml           # User preferences
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `PhaserStorage` | Manages `.phaser/` directory, provides CRUD for audits/events/config |
| `EventEmitter` | Emits typed events, notifies subscribers, integrates with storage |
| `Event` | Immutable event record with serialization |
| `EventType` | Enum of all valid event types |

---

## Data Flow

### Event Emission Flow

```
User Action (e.g., phase completion)
         │
         ▼
┌─────────────────┐
│  EventEmitter   │
│    .emit()      │
└────────┬────────┘
         │
         ├──────────────────────┐
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   Subscribers   │    │  PhaserStorage  │
│  (callbacks)    │    │ .append_event() │
└─────────────────┘    └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  .phaser/       │
                       │  events.json    │
                       └─────────────────┘
```

### Audit Lifecycle Flow

```
1. Setup Block Parsed
   └── emit: audit_started
   └── storage.save_audit()

2. Phase Execution (per phase)
   ├── emit: phase_started
   ├── Execute instructions
   ├── Run verification
   │   ├── emit: verification_passed (or failed)
   └── emit: phase_completed (or failed/skipped)
       └── storage.update_audit()

3. All Phases Done
   └── emit: audit_completed
   └── storage.update_audit(status="completed")
   └── Archive & cleanup
```

### Storage Access Patterns

| Operation | Method | File Modified |
|-----------|--------|---------------|
| Start audit | `save_audit()` | audits.json |
| Complete phase | `update_audit()` | audits.json |
| Log event | `append_event()` | events.json |
| Query history | `list_audits()` | (read only) |
| Replay events | `get_events()` | (read only) |
| User prefs | `get_config()` / `set_config()` | config.yaml |

---

## Interfaces

### PhaserStorage Interface

```python
class PhaserStorage:
    """Manages persistent storage in .phaser/ directory."""

    def __init__(self, root: Path | None = None) -> None:
        """Initialize storage at given root, or auto-detect location."""

    # Directory management
    def ensure_directories(self) -> None: ...
    def get_path(self, filename: str) -> Path: ...

    # Audit CRUD
    def save_audit(self, audit: dict) -> str: ...
    def get_audit(self, audit_id: str) -> dict | None: ...
    def list_audits(self, project: str | None = None) -> list[dict]: ...
    def update_audit(self, audit_id: str, updates: dict) -> bool: ...

    # Event operations
    def append_event(self, event: dict) -> None: ...
    def get_events(
        self,
        audit_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[dict]: ...
    def clear_events(self, before: datetime | None = None) -> int: ...

    # Config operations
    def get_config(self) -> dict: ...
    def set_config(self, key: str, value: Any) -> None: ...
    def reset_config(self) -> None: ...
```

### EventEmitter Interface

```python
class EventEmitter:
    """Emits and manages audit events."""

    def __init__(self, storage: PhaserStorage | None = None) -> None:
        """Initialize with optional storage for persistence."""

    def emit(
        self,
        event_type: EventType,
        audit_id: str,
        phase: int | None = None,
        **data: Any,
    ) -> Event: ...

    def subscribe(self, callback: Callable[[Event], None]) -> None: ...
    def unsubscribe(self, callback: Callable[[Event], None]) -> None: ...
    def replay(self, audit_id: str, callback: Callable[[Event], None]) -> int: ...
```

### Event Interface

```python
@dataclass(frozen=True)
class Event:
    """Immutable audit event record."""

    id: str              # UUID
    type: EventType      # Event type enum
    timestamp: str       # ISO 8601
    audit_id: str        # Parent audit UUID
    phase: int | None    # Phase number (if applicable)
    data: dict           # Type-specific payload

    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, d: dict) -> Event: ...
```

---

## Extension Points

### Adding New Event Types

1. Add value to `EventType` enum in `tools/events.py`
2. Document payload schema in `specs/events.md`
3. Add convenience function if commonly emitted

### Adding New Storage Files

1. Define schema in `specs/storage.md`
2. Add `_read_{file}()` and `_write_{file}()` private methods
3. Add public CRUD methods following existing patterns
4. Ensure atomic writes via temp-then-rename

### Future Integration Points

| Feature | Integration |
|---------|-------------|
| Diffs | Storage stores pre/post manifests; Events emit file_created/modified/deleted |
| Contracts | Storage persists rules; Events emit contract_violation |
| Simulation | EventEmitter in "dry-run" mode skips storage persistence |
| Branches | Storage maps audit_id → branch_name |

---

## Error Handling

### Storage Errors

| Error | Handling |
|-------|----------|
| Directory not writable | Raise `PermissionError` with path |
| File corrupted (invalid JSON/YAML) | Raise `ValueError` with parse error |
| Concurrent write conflict | Retry with exponential backoff (3 attempts) |
| Disk full | Raise `OSError`, do not corrupt existing files |

### Event Errors

| Error | Handling |
|-------|----------|
| Invalid event type | Raise `ValueError` immediately |
| Subscriber exception | Log error, continue to other subscribers |
| Storage unavailable | Emit succeeds (in-memory), log warning |

---

## Security Considerations

1. **No code execution** — Storage/Events never execute user-provided code
2. **Path validation** — All file paths validated against `.phaser/` boundary
3. **No network access** — All operations are local filesystem only
4. **Audit trail** — Events provide tamper-evident history

---

## Testing Strategy

| Layer | Test Type | Coverage Target |
|-------|-----------|-----------------|
| Storage | Unit tests with temp directories | >90% |
| Events | Unit tests with mock storage | >90% |
| Integration | End-to-end audit lifecycle | Key paths |

---

*Phaser v1.2 Architecture Specification — Document 1, Phase 1*
