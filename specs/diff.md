# Diff Specification

> Phaser v1.2 — Audit Diffs Feature

---

## Overview

The Diff engine captures the state of a project before and after an audit, computing exactly what changed. This enables transparency, reviewability, and trust in automated changes.

---

## Manifest Format

A manifest is a snapshot of a directory's state at a point in time.

### Schema

```yaml
root: /Users/jp/Projects/MyApp
timestamp: "2025-12-05T10:00:00Z"
file_count: 42
total_size_bytes: 156789
files:
  - path: src/main.py
    type: text
    size: 1234
    sha256: abc123def456...
    content: |
      print('hello')
    is_executable: false
  - path: assets/logo.png
    type: binary
    size: 8192
    sha256: 789xyz...
    content: null
    is_executable: false
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| root | string | Absolute path to manifested directory |
| timestamp | string | ISO 8601 timestamp of capture |
| file_count | int | Number of files in manifest |
| total_size_bytes | int | Sum of all file sizes |
| files | list[FileEntry] | Individual file entries |

### FileEntry Fields

| Field | Type | Description |
|-------|------|-------------|
| path | string | Relative path from root |
| type | string | "text" or "binary" |
| size | int | File size in bytes |
| sha256 | string | SHA-256 hash of content |
| content | string \| null | File content (null for binary) |
| is_executable | bool | Whether file has execute permission |

### Type Detection

Files are classified as binary if:
- They contain null bytes in the first 8KB
- They have binary extensions: `.png`, `.jpg`, `.gif`, `.ico`, `.pdf`, `.zip`, `.tar`, `.gz`, `.exe`, `.dll`, `.so`, `.dylib`, `.woff`, `.woff2`, `.ttf`, `.eot`

All other files are treated as text.

---

## Data Classes

### FileEntry

```python
@dataclass
class FileEntry:
    path: str
    type: str  # "text" or "binary"
    size: int
    sha256: str
    content: str | None  # None for binary files
    is_executable: bool

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "type": self.type,
            "size": self.size,
            "sha256": self.sha256,
            "content": self.content,
            "is_executable": self.is_executable,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileEntry":
        return cls(
            path=d["path"],
            type=d["type"],
            size=d["size"],
            sha256=d["sha256"],
            content=d.get("content"),
            is_executable=d.get("is_executable", False),
        )
```

### Manifest

```python
@dataclass
class Manifest:
    root: str
    timestamp: str
    file_count: int
    total_size_bytes: int
    files: list[FileEntry]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "timestamp": self.timestamp,
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "files": [f.to_dict() for f in self.files],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Manifest":
        return cls(
            root=d["root"],
            timestamp=d["timestamp"],
            file_count=d["file_count"],
            total_size_bytes=d["total_size_bytes"],
            files=[FileEntry.from_dict(f) for f in d["files"]],
        )

    def save(self, path: Path) -> None:
        """Save manifest to YAML file."""
        import yaml
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        """Load manifest from YAML file."""
        import yaml
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))
```

### FileChange

```python
@dataclass
class FileChange:
    path: str
    change_type: str  # "added", "modified", "deleted"
    before_hash: str | None
    after_hash: str | None
    before_size: int | None
    after_size: int | None
    diff_lines: list[str] | None  # Unified diff for text files

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "change_type": self.change_type,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "before_size": self.before_size,
            "after_size": self.after_size,
            "diff_lines": self.diff_lines,
        }
```

### DiffResult

```python
@dataclass
class DiffResult:
    before_timestamp: str
    after_timestamp: str
    added: list[FileChange]
    modified: list[FileChange]
    deleted: list[FileChange]
    unchanged_count: int

    def to_dict(self) -> dict:
        return {
            "before_timestamp": self.before_timestamp,
            "after_timestamp": self.after_timestamp,
            "added": [c.to_dict() for c in self.added],
            "modified": [c.to_dict() for c in self.modified],
            "deleted": [c.to_dict() for c in self.deleted],
            "unchanged_count": self.unchanged_count,
        }

    def summary(self) -> str:
        """One-line summary of changes."""
        parts = []
        if self.added:
            parts.append(f"+{len(self.added)} added")
        if self.modified:
            parts.append(f"~{len(self.modified)} modified")
        if self.deleted:
            parts.append(f"-{len(self.deleted)} deleted")
        if not parts:
            return "No changes"
        return ", ".join(parts)

    def detailed(self) -> str:
        """Full unified diff output."""
        lines = []
        for change in self.added:
            lines.append(f"Added: {change.path}")
        for change in self.modified:
            lines.append(f"Modified: {change.path}")
            if change.diff_lines:
                lines.extend(change.diff_lines)
        for change in self.deleted:
            lines.append(f"Deleted: {change.path}")
        return "\n".join(lines)
```

---

## Core Operations

### capture_manifest

```python
def capture_manifest(
    root: Path,
    exclude_patterns: list[str] | None = None,
) -> Manifest:
    """
    Capture current state of directory as manifest.

    Args:
        root: Directory to capture
        exclude_patterns: Glob patterns to exclude (e.g., [".git", ".audit"])

    Returns:
        Manifest snapshot of directory state

    Behavior:
        - Walks directory tree recursively
        - Respects .gitignore if present
        - Applies exclude_patterns
        - Computes SHA-256 hash for each file
        - Reads content for text files only
        - Records executable permission
    """
```

### compare_manifests

```python
def compare_manifests(
    before: Manifest,
    after: Manifest,
    include_diff: bool = True,
    max_diff_size: int = 100_000,
) -> DiffResult:
    """
    Compare two manifests and return differences.

    Args:
        before: Earlier manifest
        after: Later manifest
        include_diff: Whether to compute unified diff for text files
        max_diff_size: Skip diff for files larger than this (bytes)

    Returns:
        DiffResult with added, modified, deleted files

    Algorithm:
        1. Build path -> FileEntry maps for both manifests
        2. Added = paths in after but not before
        3. Deleted = paths in before but not after
        4. Modified = paths in both where sha256 differs
        5. For modified text files, compute unified diff
    """
```

### compute_file_diff

```python
def compute_file_diff(
    before_content: str,
    after_content: str,
    path: str,
) -> list[str]:
    """
    Compute unified diff between two file contents.

    Args:
        before_content: Original file content
        after_content: New file content
        path: File path (for diff header)

    Returns:
        List of diff lines in unified format

    Uses difflib.unified_diff with:
        - fromfile: f"a/{path}"
        - tofile: f"b/{path}"
        - lineterm: ""
    """
```

---

## Storage Integration

### save_manifest_to_storage

```python
def save_manifest_to_storage(
    storage: PhaserStorage,
    manifest: Manifest,
    audit_id: str,
    stage: str,  # "pre" or "post"
) -> Path:
    """
    Save manifest to .phaser/manifests/ directory.

    Path format: .phaser/manifests/{audit_id}-{stage}.yaml

    Returns the path where manifest was saved.
    """
```

### load_manifests_for_audit

```python
def load_manifests_for_audit(
    storage: PhaserStorage,
    audit_id: str,
) -> tuple[Manifest | None, Manifest | None]:
    """
    Load pre and post manifests for an audit.

    Returns:
        (pre_manifest, post_manifest) - either may be None if not found
    """
```

---

## Output Formats

### JSON

Machine-readable format for storage and API consumption.

```json
{
  "before_timestamp": "2025-12-05T10:00:00Z",
  "after_timestamp": "2025-12-05T12:00:00Z",
  "added": [
    {"path": "src/new_file.py", "change_type": "added", ...}
  ],
  "modified": [...],
  "deleted": [...],
  "unchanged_count": 38
}
```

### Summary

Human-readable one-liner for quick overview.

```
+3 added, ~12 modified, -1 deleted
```

### Detailed

Full unified diff output for review.

```
Added: src/new_file.py
Modified: src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -10,3 +10,5 @@
 def main():
     print("hello")
+    print("world")

Deleted: src/old_file.py
```

---

## Edge Cases

### Binary Files

- Detected by content inspection (null bytes) or extension
- Hash comparison only, no content diff
- diff_lines is always None for binary files
- Changes reported as modified if hash differs

### Large Files

- Files larger than max_diff_size skip content diff
- Hash comparison still performed
- diff_lines set to ["(diff skipped: file too large)"]
- Default threshold: 100KB

### Symlinks

- Resolved to target content (follow symlinks)
- Symlink target path not preserved
- Broken symlinks are skipped with warning

### Permissions

- Only executable bit tracked (is_executable)
- Permission-only changes don't trigger "modified"
- Future: could track full mode if needed

### Empty Files

- Valid entries with size=0
- content is empty string for text, None for binary
- sha256 is hash of empty content

### Encoding

- UTF-8 assumed for text files
- Files that fail UTF-8 decode treated as binary
- No BOM handling (treated as content)

---

## Event Integration

When diff operations complete, emit events via EventEmitter:

| Event | When | Payload |
|-------|------|---------|
| FILE_CREATED | File in post but not pre | path, size, audit_id |
| FILE_MODIFIED | File in both, hash differs | path, before_size, after_size, audit_id |
| FILE_DELETED | File in pre but not post | path, audit_id |

Events are emitted during `on_audit_complete` in audit_hooks.py.

---

## CLI Interface

```bash
# Capture manifest
python -m tools.diff capture <root> [-o output.yaml]

# Compare manifests
python -m tools.diff compare <before.yaml> <after.yaml> [--format json|summary|detailed]
```

### capture command

```
Usage: python -m tools.diff capture [OPTIONS] ROOT

  Capture manifest of directory.

Arguments:
  ROOT  Directory to capture (must exist)

Options:
  -o, --output PATH  Output file (default: stdout)
  --exclude TEXT     Patterns to exclude (can repeat)
```

### compare command

```
Usage: python -m tools.diff compare [OPTIONS] BEFORE AFTER

  Compare two manifests.

Arguments:
  BEFORE  Path to before manifest
  AFTER   Path to after manifest

Options:
  --format [json|summary|detailed]  Output format (default: summary)
  --no-diff                         Skip unified diff computation
```

---

## Implementation Notes

1. **Reuse serialize.py**: The existing tools/serialize.py has file collection and gitignore parsing logic. Leverage where possible.

2. **difflib.unified_diff**: Use Python's built-in for text comparison. Returns generator of lines.

3. **pathlib**: Use Path throughout for cross-platform compatibility.

4. **YAML for manifests**: Human-readable, supports multiline content strings.

5. **Lazy content loading**: For large directories, consider streaming rather than loading all content into memory.

---

*Phaser v1.2 — Diff Specification*
