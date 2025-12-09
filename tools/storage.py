"""
Phaser Storage Layer

Manages persistent storage in .phaser/ directory for audits, events, and configuration.
Supports both global (~/.phaser/) and project-local (.phaser/) storage modes.
"""

from __future__ import annotations

import copy
import fcntl
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


# Default configuration values
DEFAULT_CONFIG: dict[str, Any] = {
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

# Retry configuration for file locking
MAX_RETRIES = 3
RETRY_DELAYS = [0.1, 0.3, 1.0]


def get_global_phaser_dir() -> Path:
    """Get the global .phaser/ directory path (~/.phaser/)."""
    return Path.home() / ".phaser"


def get_project_phaser_dir() -> Path | None:
    """
    Get the project-local .phaser/ directory if it exists.

    Walks up from current directory looking for .phaser/ folder.
    Returns None if not found.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        phaser_dir = parent / ".phaser"
        if phaser_dir.is_dir():
            return phaser_dir
        # Stop at filesystem root or home directory
        if parent == Path.home() or parent == parent.parent:
            break
    return None


def find_phaser_root() -> Path:
    """
    Auto-detect the best storage location.

    Resolution order:
    1. PHASER_STORAGE_DIR environment variable
    2. Project-local .phaser/ if exists
    3. Global ~/.phaser/
    """
    env_dir = os.environ.get("PHASER_STORAGE_DIR")
    if env_dir:
        return Path(env_dir)

    project_dir = get_project_phaser_dir()
    if project_dir:
        return project_dir

    return get_global_phaser_dir()


class PhaserStorage:
    """
    Manages persistent storage in .phaser/ directory.

    Provides CRUD operations for audits, events, and configuration
    with atomic writes and file locking for concurrent access safety.
    """

    def __init__(self, root: Path | None = None) -> None:
        """
        Initialize storage at the given root, or auto-detect location.

        Args:
            root: Explicit storage root directory. If None, auto-detects.
        """
        self._root = root if root else find_phaser_root()
        self._audits_file = self._root / "audits.json"
        self._events_file = self._root / "events.json"
        self._config_file = self._root / "config.yaml"

    @property
    def root(self) -> Path:
        """Get the storage root directory."""
        return self._root

    def ensure_directories(self) -> None:
        """Create .phaser/ directory structure if it doesn't exist."""
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "manifests").mkdir(exist_ok=True)

    def get_path(self, filename: str) -> Path:
        """
        Resolve a path within .phaser/ directory.

        Args:
            filename: Relative filename or path within .phaser/

        Returns:
            Absolute path to the file
        """
        return self._root / filename

    # -------------------------------------------------------------------------
    # Audit Operations
    # -------------------------------------------------------------------------

    def save_audit(self, audit: dict[str, Any]) -> str:
        """
        Save a new audit record.

        Args:
            audit: Audit data dictionary. If 'id' not present, one is generated.

        Returns:
            The audit ID (generated or existing)

        Raises:
            ValueError: If required fields are missing
        """
        self.ensure_directories()

        # Generate ID if not present
        if "id" not in audit:
            audit["id"] = str(uuid.uuid4())

        # Validate required fields
        required = ["project", "slug", "date", "status"]
        missing = [f for f in required if f not in audit]
        if missing:
            raise ValueError(f"Missing required audit fields: {missing}")

        # Load existing audits
        data = self._read_json(self._audits_file, {"version": 1, "audits": []})

        # Append new audit
        data["audits"].append(audit)

        # Write back
        self._write_json(self._audits_file, data)

        return audit["id"]

    def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        """
        Retrieve an audit by ID.

        Args:
            audit_id: The audit UUID

        Returns:
            Audit dictionary if found, None otherwise
        """
        data = self._read_json(self._audits_file, {"version": 1, "audits": []})
        for audit in data["audits"]:
            if audit.get("id") == audit_id:
                return audit
        return None

    def list_audits(self, project: str | None = None) -> list[dict[str, Any]]:
        """
        List all audits, optionally filtered by project.

        Args:
            project: If provided, filter to audits for this project only

        Returns:
            List of audit dictionaries
        """
        data = self._read_json(self._audits_file, {"version": 1, "audits": []})
        audits = data["audits"]

        if project:
            audits = [a for a in audits if a.get("project") == project]

        return audits

    def update_audit(self, audit_id: str, updates: dict[str, Any]) -> bool:
        """
        Update an existing audit record.

        Args:
            audit_id: The audit UUID to update
            updates: Dictionary of fields to update

        Returns:
            True if audit was found and updated, False if not found
        """
        data = self._read_json(self._audits_file, {"version": 1, "audits": []})

        for audit in data["audits"]:
            if audit.get("id") == audit_id:
                audit.update(updates)
                self._write_json(self._audits_file, data)
                return True

        return False

    # -------------------------------------------------------------------------
    # Event Operations
    # -------------------------------------------------------------------------

    def append_event(self, event: dict[str, Any]) -> None:
        """
        Append an event to the event log.

        Args:
            event: Event dictionary to append

        Raises:
            ValueError: If required event fields are missing
        """
        self.ensure_directories()

        # Validate required fields
        required = ["id", "type", "timestamp", "audit_id"]
        missing = [f for f in required if f not in event]
        if missing:
            raise ValueError(f"Missing required event fields: {missing}")

        # Load existing events
        data = self._read_json(self._events_file, {"version": 1, "events": []})

        # Append new event
        data["events"].append(event)

        # Write back
        self._write_json(self._events_file, data)

    def get_events(
        self,
        audit_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query events with optional filters.

        Args:
            audit_id: Filter to events for this audit only
            event_type: Filter to events of this type only
            since: Filter to events after this timestamp

        Returns:
            List of matching event dictionaries, sorted by timestamp
        """
        data = self._read_json(self._events_file, {"version": 1, "events": []})
        events = data["events"]

        # Apply filters
        if audit_id:
            events = [e for e in events if e.get("audit_id") == audit_id]

        if event_type:
            events = [e for e in events if e.get("type") == event_type]

        if since:
            since_str = since.isoformat()
            events = [e for e in events if e.get("timestamp", "") >= since_str]

        # Sort by timestamp
        events.sort(key=lambda e: e.get("timestamp", ""))

        return events

    def clear_events(self, before: datetime | None = None) -> int:
        """
        Remove events from the log.

        Args:
            before: If provided, only remove events before this timestamp.
                    If None, removes all events.

        Returns:
            Number of events removed
        """
        data = self._read_json(self._events_file, {"version": 1, "events": []})
        original_count = len(data["events"])

        if before:
            before_str = before.isoformat()
            data["events"] = [
                e for e in data["events"]
                if e.get("timestamp", "") >= before_str
            ]
        else:
            data["events"] = []

        removed = original_count - len(data["events"])

        if removed > 0:
            self._write_json(self._events_file, data)

        return removed

    # -------------------------------------------------------------------------
    # Config Operations
    # -------------------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        """
        Load configuration with defaults merged in.

        Returns:
            Configuration dictionary with all defaults applied
        """
        if not self._config_file.exists():
            return copy.deepcopy(DEFAULT_CONFIG)

        try:
            with open(self._config_file, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError) as e:
            raise ValueError(f"Failed to parse config file: {e}") from e

        # Deep merge with defaults
        return self._merge_config(DEFAULT_CONFIG, user_config)

    def set_config(self, key: str, value: Any) -> None:
        """
        Update a single configuration value.

        Supports dot-notation for nested keys (e.g., "storage.max_events").

        Args:
            key: Configuration key (dot-notation supported)
            value: New value to set
        """
        self.ensure_directories()

        config = self.get_config()

        # Handle dot-notation keys
        keys = key.split(".")
        target = config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

        # Write config
        self._write_yaml(self._config_file, config)

    def reset_config(self) -> None:
        """Reset configuration to defaults."""
        self.ensure_directories()
        self._write_yaml(self._config_file, DEFAULT_CONFIG)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        """Read JSON file with locking, returning default if not exists."""
        if not path.exists():
            return default.copy()

        try:
            with open(path, encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write JSON file atomically with locking."""
        self._atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False))

    def _write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        """Write YAML file atomically with locking."""
        self._atomic_write(path, yaml.dump(data, default_flow_style=False, sort_keys=False))

    def _atomic_write(self, path: Path, content: str) -> None:
        """
        Write file atomically using temp-then-rename pattern.

        Includes retry logic for handling concurrent access.

        Args:
            path: Destination file path
            content: String content to write

        Raises:
            BlockingIOError: If file lock cannot be acquired after retries
            OSError: If write fails (e.g., disk full, permission denied)
        """
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        try:
            for attempt, delay in enumerate(RETRY_DELAYS):
                try:
                    # Write to temp file
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        try:
                            f.write(content)
                            f.flush()
                            os.fsync(f.fileno())
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

                    # Atomic rename
                    tmp_path.rename(path)
                    return

                except BlockingIOError:
                    if attempt == MAX_RETRIES - 1:
                        raise
                    time.sleep(delay)
        except OSError:
            # Clean up temp file on failure (disk full, permission denied, etc.)
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _merge_config(
        self,
        default: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """Deep merge two config dictionaries, with override taking precedence."""
        result = default.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result
