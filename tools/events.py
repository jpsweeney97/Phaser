"""
Phaser Event System

Provides typed events, emission, subscription, and replay capabilities
for tracking audit activities. Integrates with PhaserStorage for persistence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from tools.storage import PhaserStorage


class EventType(str, Enum):
    """All valid event types in the Phaser system."""

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


@dataclass(frozen=True)
class Event:
    """
    Immutable audit event record.

    Events capture discrete actions during audit execution,
    enabling replay, analysis, and real-time monitoring.
    """

    id: str
    type: EventType
    timestamp: str
    audit_id: str
    phase: int | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary for JSON storage."""
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "audit_id": self.audit_id,
            "phase": self.phase,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Event:
        """Deserialize event from dictionary."""
        return cls(
            id=d["id"],
            type=EventType(d["type"]),
            timestamp=d["timestamp"],
            audit_id=d["audit_id"],
            phase=d.get("phase"),
            data=d.get("data", {}),
        )


class EventEmitter:
    """
    Emits and manages audit events.

    Supports subscription for real-time notifications,
    persistence via PhaserStorage, and replay of historical events.
    """

    def __init__(self, storage: PhaserStorage | None = None) -> None:
        """
        Initialize the event emitter.

        Args:
            storage: Optional storage for event persistence.
                     If None, events are emitted but not persisted.
        """
        self._storage = storage
        self._subscribers: list[Callable[[Event], None]] = []

    def emit(
        self,
        event_type: EventType,
        audit_id: str,
        phase: int | None = None,
        **data: Any,
    ) -> Event:
        """
        Create and emit an event.

        Args:
            event_type: Type of event to emit
            audit_id: Parent audit UUID
            phase: Phase number (optional, for phase-related events)
            **data: Type-specific payload data

        Returns:
            The created Event object
        """
        event = Event(
            id=str(uuid.uuid4()),
            type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            audit_id=audit_id,
            phase=phase,
            data=dict(data),
        )

        # Persist to storage if available
        if self._storage:
            self._storage.append_event(event.to_dict())

        # Notify subscribers
        self._notify_subscribers(event)

        return event

    def subscribe(self, callback: Callable[[Event], None]) -> None:
        """
        Register a callback to receive events.

        Args:
            callback: Function to call with each emitted event
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Event], None]) -> None:
        """
        Remove a callback from the subscriber list.

        Args:
            callback: The callback to remove
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def replay(
        self,
        audit_id: str,
        callback: Callable[[Event], None],
    ) -> int:
        """
        Replay historical events for an audit.

        Loads events from storage and calls the callback for each,
        in chronological order.

        Args:
            audit_id: The audit UUID to replay events for
            callback: Function to call with each historical event

        Returns:
            Number of events replayed

        Raises:
            RuntimeError: If no storage is configured
        """
        if not self._storage:
            raise RuntimeError("Cannot replay events without storage configured")

        events = self._storage.get_events(audit_id=audit_id)

        for event_dict in events:
            event = Event.from_dict(event_dict)
            callback(event)

        return len(events)

    def _notify_subscribers(self, event: Event) -> None:
        """
        Notify all subscribers of an event.

        Subscriber exceptions are logged but do not stop notification
        of other subscribers or event emission.
        """
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                # Log error but continue to other subscribers
                # In production, this would use proper logging
                pass


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------


def emit_audit_started(
    emitter: EventEmitter,
    audit_id: str,
    project: str,
    slug: str,
    phases_total: int,
    **kwargs: Any,
) -> Event:
    """
    Emit an audit_started event.

    Args:
        emitter: The EventEmitter to use
        audit_id: The audit UUID
        project: Project name
        slug: Audit identifier
        phases_total: Total number of phases
        **kwargs: Additional payload data

    Returns:
        The emitted Event
    """
    return emitter.emit(
        EventType.AUDIT_STARTED,
        audit_id,
        project=project,
        slug=slug,
        phases_total=phases_total,
        **kwargs,
    )


def emit_audit_completed(
    emitter: EventEmitter,
    audit_id: str,
    duration_seconds: float,
    phases_completed: int,
    phases_skipped: int,
    **kwargs: Any,
) -> Event:
    """
    Emit an audit_completed event.

    Args:
        emitter: The EventEmitter to use
        audit_id: The audit UUID
        duration_seconds: Total audit duration
        phases_completed: Count of completed phases
        phases_skipped: Count of skipped phases
        **kwargs: Additional payload data

    Returns:
        The emitted Event
    """
    return emitter.emit(
        EventType.AUDIT_COMPLETED,
        audit_id,
        duration_seconds=duration_seconds,
        phases_completed=phases_completed,
        phases_skipped=phases_skipped,
        **kwargs,
    )


def emit_phase_started(
    emitter: EventEmitter,
    audit_id: str,
    phase: int,
    description: str,
    **kwargs: Any,
) -> Event:
    """
    Emit a phase_started event.

    Args:
        emitter: The EventEmitter to use
        audit_id: The audit UUID
        phase: Phase number (1-indexed)
        description: Phase title/description
        **kwargs: Additional payload data

    Returns:
        The emitted Event
    """
    return emitter.emit(
        EventType.PHASE_STARTED,
        audit_id,
        phase=phase,
        description=description,
        **kwargs,
    )


def emit_phase_completed(
    emitter: EventEmitter,
    audit_id: str,
    phase: int,
    duration_seconds: float,
    **kwargs: Any,
) -> Event:
    """
    Emit a phase_completed event.

    Args:
        emitter: The EventEmitter to use
        audit_id: The audit UUID
        phase: Phase number (1-indexed)
        duration_seconds: Phase execution time
        **kwargs: Additional payload data

    Returns:
        The emitted Event
    """
    return emitter.emit(
        EventType.PHASE_COMPLETED,
        audit_id,
        phase=phase,
        duration_seconds=duration_seconds,
        **kwargs,
    )


def emit_phase_failed(
    emitter: EventEmitter,
    audit_id: str,
    phase: int,
    error: str,
    attempts: int = 1,
    **kwargs: Any,
) -> Event:
    """
    Emit a phase_failed event.

    Args:
        emitter: The EventEmitter to use
        audit_id: The audit UUID
        phase: Phase number (1-indexed)
        error: Error message
        attempts: Number of retry attempts made
        **kwargs: Additional payload data

    Returns:
        The emitted Event
    """
    return emitter.emit(
        EventType.PHASE_FAILED,
        audit_id,
        phase=phase,
        error=error,
        attempts=attempts,
        **kwargs,
    )


def emit_phase_skipped(
    emitter: EventEmitter,
    audit_id: str,
    phase: int,
    reason: str = "user_request",
    **kwargs: Any,
) -> Event:
    """
    Emit a phase_skipped event.

    Args:
        emitter: The EventEmitter to use
        audit_id: The audit UUID
        phase: Phase number (1-indexed)
        reason: Why the phase was skipped
        **kwargs: Additional payload data

    Returns:
        The emitted Event
    """
    return emitter.emit(
        EventType.PHASE_SKIPPED,
        audit_id,
        phase=phase,
        reason=reason,
        **kwargs,
    )
