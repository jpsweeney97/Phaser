"""Tests for the Phaser event system."""

import pytest

from tools.events import (
    Event,
    EventEmitter,
    EventType,
    emit_audit_started,
    emit_phase_completed,
    emit_phase_started,
    emit_phase_failed,
    emit_phase_skipped,
)
from tools.storage import PhaserStorage


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self) -> None:
        """Verify all event types have correct string values."""
        assert EventType.AUDIT_STARTED.value == "audit_started"
        assert EventType.AUDIT_COMPLETED.value == "audit_completed"
        assert EventType.AUDIT_ABANDONED.value == "audit_abandoned"
        assert EventType.PHASE_STARTED.value == "phase_started"
        assert EventType.PHASE_COMPLETED.value == "phase_completed"
        assert EventType.PHASE_FAILED.value == "phase_failed"
        assert EventType.PHASE_SKIPPED.value == "phase_skipped"
        assert EventType.VERIFICATION_PASSED.value == "verification_passed"
        assert EventType.VERIFICATION_FAILED.value == "verification_failed"
        assert EventType.FILE_CREATED.value == "file_created"
        assert EventType.FILE_MODIFIED.value == "file_modified"
        assert EventType.FILE_DELETED.value == "file_deleted"

    def test_event_type_count(self) -> None:
        """Verify all 12 event types are defined."""
        assert len(EventType) == 12


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_creation(self) -> None:
        """Verify Event can be created with all fields."""
        event = Event(
            id="test-id",
            type=EventType.PHASE_COMPLETED,
            timestamp="2025-12-05T10:00:00.000Z",
            audit_id="audit-123",
            phase=3,
            data={"duration": 45.0},
        )

        assert event.id == "test-id"
        assert event.type == EventType.PHASE_COMPLETED
        assert event.timestamp == "2025-12-05T10:00:00.000Z"
        assert event.audit_id == "audit-123"
        assert event.phase == 3
        assert event.data == {"duration": 45.0}

    def test_event_creation_minimal(self) -> None:
        """Verify Event can be created with minimal fields."""
        event = Event(
            id="test-id",
            type=EventType.AUDIT_STARTED,
            timestamp="2025-12-05T10:00:00.000Z",
            audit_id="audit-123",
        )

        assert event.phase is None
        assert event.data == {}

    def test_event_is_immutable(self) -> None:
        """Verify Event is frozen (immutable)."""
        event = Event(
            id="test-id",
            type=EventType.AUDIT_STARTED,
            timestamp="2025-12-05T10:00:00.000Z",
            audit_id="audit-123",
        )

        with pytest.raises(AttributeError):
            event.id = "new-id"  # type: ignore

    def test_event_to_dict(self) -> None:
        """Verify Event serializes to dictionary correctly."""
        event = Event(
            id="test-id",
            type=EventType.PHASE_COMPLETED,
            timestamp="2025-12-05T10:00:00.000Z",
            audit_id="audit-123",
            phase=3,
            data={"duration": 45.0},
        )

        d = event.to_dict()

        assert d["id"] == "test-id"
        assert d["type"] == "phase_completed"  # String value, not enum
        assert d["timestamp"] == "2025-12-05T10:00:00.000Z"
        assert d["audit_id"] == "audit-123"
        assert d["phase"] == 3
        assert d["data"] == {"duration": 45.0}

    def test_event_from_dict(self) -> None:
        """Verify Event deserializes from dictionary correctly."""
        d = {
            "id": "test-id",
            "type": "phase_completed",
            "timestamp": "2025-12-05T10:00:00.000Z",
            "audit_id": "audit-123",
            "phase": 3,
            "data": {"duration": 45.0},
        }

        event = Event.from_dict(d)

        assert event.id == "test-id"
        assert event.type == EventType.PHASE_COMPLETED
        assert event.timestamp == "2025-12-05T10:00:00.000Z"
        assert event.audit_id == "audit-123"
        assert event.phase == 3
        assert event.data == {"duration": 45.0}

    def test_event_roundtrip(self) -> None:
        """Verify Event survives serialization roundtrip."""
        original = Event(
            id="test-id",
            type=EventType.PHASE_COMPLETED,
            timestamp="2025-12-05T10:00:00.000Z",
            audit_id="audit-123",
            phase=3,
            data={"duration": 45.0},
        )

        restored = Event.from_dict(original.to_dict())

        assert restored == original


class TestEventEmitter:
    """Tests for EventEmitter class."""

    def test_emitter_emit_creates_event(self, emitter: EventEmitter) -> None:
        """Verify emit() returns an Event object."""
        event = emitter.emit(
            EventType.PHASE_STARTED,
            audit_id="audit-123",
            phase=1,
            description="Test phase",
        )

        assert isinstance(event, Event)
        assert event.type == EventType.PHASE_STARTED
        assert event.audit_id == "audit-123"
        assert event.phase == 1
        assert event.data["description"] == "Test phase"

    def test_emitter_emit_generates_id(self, emitter: EventEmitter) -> None:
        """Verify emit() generates a UUID for the event."""
        event = emitter.emit(
            EventType.AUDIT_STARTED,
            audit_id="audit-123",
        )

        assert event.id is not None
        assert len(event.id) == 36  # UUID format

    def test_emitter_emit_generates_timestamp(self, emitter: EventEmitter) -> None:
        """Verify emit() generates a timestamp."""
        event = emitter.emit(
            EventType.AUDIT_STARTED,
            audit_id="audit-123",
        )

        assert event.timestamp is not None
        assert "T" in event.timestamp  # ISO 8601 format

    def test_emitter_emit_persists_to_storage(
        self,
        storage: PhaserStorage,
        emitter: EventEmitter,
    ) -> None:
        """Verify events are persisted to storage."""
        emitter.emit(
            EventType.PHASE_COMPLETED,
            audit_id="audit-123",
            phase=1,
        )

        events = storage.get_events()
        assert len(events) == 1
        assert events[0]["type"] == "phase_completed"

    def test_emitter_without_storage(self, emitter_no_storage: EventEmitter) -> None:
        """Verify emitter works without storage (in-memory only)."""
        event = emitter_no_storage.emit(
            EventType.AUDIT_STARTED,
            audit_id="audit-123",
        )

        assert event is not None
        assert event.type == EventType.AUDIT_STARTED

    def test_emitter_subscribe_receives_events(self, emitter: EventEmitter) -> None:
        """Verify subscribers receive emitted events."""
        received: list[Event] = []

        def callback(event: Event) -> None:
            received.append(event)

        emitter.subscribe(callback)
        emitter.emit(EventType.AUDIT_STARTED, audit_id="audit-123")

        assert len(received) == 1
        assert received[0].type == EventType.AUDIT_STARTED

    def test_emitter_multiple_subscribers(self, emitter: EventEmitter) -> None:
        """Verify multiple subscribers all receive events."""
        received1: list[Event] = []
        received2: list[Event] = []

        emitter.subscribe(lambda e: received1.append(e))
        emitter.subscribe(lambda e: received2.append(e))
        emitter.emit(EventType.AUDIT_STARTED, audit_id="audit-123")

        assert len(received1) == 1
        assert len(received2) == 1

    def test_emitter_unsubscribe(self, emitter: EventEmitter) -> None:
        """Verify unsubscribed callbacks don't receive events."""
        received: list[Event] = []

        def callback(event: Event) -> None:
            received.append(event)

        emitter.subscribe(callback)
        emitter.emit(EventType.AUDIT_STARTED, audit_id="audit-123")
        emitter.unsubscribe(callback)
        emitter.emit(EventType.AUDIT_COMPLETED, audit_id="audit-123")

        assert len(received) == 1
        assert received[0].type == EventType.AUDIT_STARTED

    def test_emitter_subscribe_idempotent(self, emitter: EventEmitter) -> None:
        """Verify subscribing twice doesn't cause duplicate calls."""
        received: list[Event] = []

        def callback(event: Event) -> None:
            received.append(event)

        emitter.subscribe(callback)
        emitter.subscribe(callback)  # Subscribe again
        emitter.emit(EventType.AUDIT_STARTED, audit_id="audit-123")

        assert len(received) == 1

    def test_emitter_subscriber_exception_isolated(self, emitter: EventEmitter) -> None:
        """Verify subscriber exceptions don't break other subscribers."""
        received: list[Event] = []

        def bad_callback(event: Event) -> None:
            raise RuntimeError("Subscriber error")

        def good_callback(event: Event) -> None:
            received.append(event)

        emitter.subscribe(bad_callback)
        emitter.subscribe(good_callback)

        # Should not raise, and good_callback should still receive event
        emitter.emit(EventType.AUDIT_STARTED, audit_id="audit-123")

        assert len(received) == 1

    def test_emitter_replay(
        self,
        storage: PhaserStorage,
        emitter: EventEmitter,
    ) -> None:
        """Verify replay() calls callback for historical events."""
        # Emit some events
        emitter.emit(EventType.PHASE_STARTED, audit_id="audit-123", phase=1)
        emitter.emit(EventType.PHASE_COMPLETED, audit_id="audit-123", phase=1)
        emitter.emit(EventType.PHASE_STARTED, audit_id="other-audit", phase=1)

        # Replay events for specific audit
        replayed: list[Event] = []
        count = emitter.replay("audit-123", lambda e: replayed.append(e))

        assert count == 2
        assert len(replayed) == 2
        assert all(e.audit_id == "audit-123" for e in replayed)

    def test_emitter_replay_without_storage_raises(
        self,
        emitter_no_storage: EventEmitter,
    ) -> None:
        """Verify replay() raises when no storage configured."""
        with pytest.raises(RuntimeError, match="Cannot replay events without storage"):
            emitter_no_storage.replay("audit-123", lambda e: None)


class TestConvenienceFunctions:
    """Tests for convenience emit functions."""

    def test_emit_audit_started(self, emitter: EventEmitter) -> None:
        """Verify emit_audit_started convenience function."""
        event = emit_audit_started(
            emitter,
            audit_id="audit-123",
            project="TestProject",
            slug="test-audit",
            phases_total=6,
        )

        assert event.type == EventType.AUDIT_STARTED
        assert event.data["project"] == "TestProject"
        assert event.data["slug"] == "test-audit"
        assert event.data["phases_total"] == 6

    def test_emit_phase_started(self, emitter: EventEmitter) -> None:
        """Verify emit_phase_started convenience function."""
        event = emit_phase_started(
            emitter,
            audit_id="audit-123",
            phase=3,
            description="Event Specification",
        )

        assert event.type == EventType.PHASE_STARTED
        assert event.phase == 3
        assert event.data["description"] == "Event Specification"

    def test_emit_phase_completed(self, emitter: EventEmitter) -> None:
        """Verify emit_phase_completed convenience function."""
        event = emit_phase_completed(
            emitter,
            audit_id="audit-123",
            phase=3,
            duration_seconds=45.5,
        )

        assert event.type == EventType.PHASE_COMPLETED
        assert event.phase == 3
        assert event.data["duration_seconds"] == 45.5

    def test_emit_phase_failed(self, emitter: EventEmitter) -> None:
        """Verify emit_phase_failed convenience function."""
        event = emit_phase_failed(
            emitter,
            audit_id="audit-123",
            phase=3,
            error="Verification failed",
            attempts=3,
        )

        assert event.type == EventType.PHASE_FAILED
        assert event.phase == 3
        assert event.data["error"] == "Verification failed"
        assert event.data["attempts"] == 3

    def test_emit_phase_skipped(self, emitter: EventEmitter) -> None:
        """Verify emit_phase_skipped convenience function."""
        event = emit_phase_skipped(
            emitter,
            audit_id="audit-123",
            phase=3,
            reason="user_request",
        )

        assert event.type == EventType.PHASE_SKIPPED
        assert event.phase == 3
        assert event.data["reason"] == "user_request"
