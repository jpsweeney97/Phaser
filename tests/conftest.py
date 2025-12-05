"""Shared pytest fixtures for Phaser tests."""

import shutil
import tempfile
from pathlib import Path

import pytest

from tools.storage import PhaserStorage
from tools.events import EventEmitter


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for tests."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def storage(temp_dir: Path) -> PhaserStorage:
    """Create a PhaserStorage instance with temp directory."""
    return PhaserStorage(root=temp_dir)


@pytest.fixture
def emitter(storage: PhaserStorage) -> EventEmitter:
    """Create an EventEmitter with storage."""
    return EventEmitter(storage=storage)


@pytest.fixture
def emitter_no_storage() -> EventEmitter:
    """Create an EventEmitter without storage (in-memory only)."""
    return EventEmitter(storage=None)
