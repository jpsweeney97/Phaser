#!/usr/bin/env python3
"""
Phaser Post-Audit Serializer

Standalone workspace serializer for generating post-audit manifests.
Zero external dependencies — uses only Python standard library.

Usage:
    python serialize.py --root /path/to/project --output manifest.yaml

Output format matches Phaser manifest.yaml schema:
    root: /absolute/path
    timestamp: ISO8601
    file_count: N
    total_size_bytes: N
    files:
      - path: relative/path
        type: text|binary
        size: N
        sha256: hex
        content: |
          file contents
        is_executable: true|false
"""

import argparse
import base64
import fnmatch
import hashlib
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Directories to always exclude
DEFAULT_EXCLUDES = frozenset({
    ".git",
    ".DS_Store",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".audit",
    ".env",
    "*.egg-info",
    "dist",
    "build",
})

# Hidden directories to include (most hidden dirs are excluded)
ALLOWED_HIDDEN_DIRS = frozenset({
    ".github",
    ".config",
    ".circleci",
})

# Hidden files to include
ALLOWED_HIDDEN_FILES = frozenset({
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".prettierrc",
    ".eslintrc",
    ".dockerignore",
})

# Maximum file size (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum total manifest size (100 MB)
MAX_TOTAL_SIZE = 100 * 1024 * 1024


def parse_gitignore(root: Path) -> list[str]:
    """Parse .gitignore and return patterns list."""
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return []

    patterns: list[str] = []
    try:
        content = gitignore_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            # Skip empty lines and comments
            if stripped and not stripped.startswith("#"):
                patterns.append(stripped)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read .gitignore: {e}", file=sys.stderr)

    return patterns


def matches_gitignore(relative_path: str, pattern: str) -> bool:
    """Check if path matches a gitignore pattern (simplified implementation)."""
    # Skip negation patterns (not supported)
    if pattern.startswith("!"):
        return False

    # Handle directory-only patterns (ending with /)
    if pattern.endswith("/"):
        dir_pattern = pattern[:-1]
        parts = relative_path.split("/")
        # Match any directory component
        return any(fnmatch.fnmatch(part, dir_pattern) for part in parts[:-1])

    # Handle rooted patterns (starting with /)
    if pattern.startswith("/"):
        return fnmatch.fnmatch(relative_path, pattern[1:])

    # Handle patterns with / in the middle (match from root)
    if "/" in pattern:
        return fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(
            relative_path, "**/" + pattern
        )

    # Simple pattern — match against basename or any component
    basename = relative_path.rsplit("/", 1)[-1]
    if fnmatch.fnmatch(basename, pattern):
        return True

    # Also try each path component
    for part in relative_path.split("/"):
        if fnmatch.fnmatch(part, pattern):
            return True

    return False


def is_ignored(relative_path: str, patterns: list[str]) -> bool:
    """Check if path should be ignored based on gitignore patterns."""
    for pattern in patterns:
        if matches_gitignore(relative_path, pattern):
            return True
    return False


def should_include_directory(name: str, rel_path: str, patterns: list[str]) -> bool:
    """Determine if a directory should be traversed."""
    # Check default excludes
    if name in DEFAULT_EXCLUDES:
        return False

    # Check glob patterns in default excludes
    for exclude in DEFAULT_EXCLUDES:
        if "*" in exclude and fnmatch.fnmatch(name, exclude):
            return False

    # Handle hidden directories
    if name.startswith(".") and name not in ALLOWED_HIDDEN_DIRS:
        return False

    # Check gitignore
    dir_rel_path = rel_path + "/" if rel_path else name + "/"
    if is_ignored(dir_rel_path.rstrip("/"), patterns):
        return False
    if is_ignored(dir_rel_path, patterns):
        return False

    return True


def should_include_file(name: str, rel_path: str, patterns: list[str]) -> bool:
    """Determine if a file should be included."""
    # Check default excludes
    if name in DEFAULT_EXCLUDES:
        return False

    # Handle hidden files
    if name.startswith(".") and name not in ALLOWED_HIDDEN_FILES:
        return False

    # Check gitignore
    if is_ignored(rel_path, patterns):
        return False

    return True


def collect_files(root: Path, patterns: list[str]) -> list[Path]:
    """Walk directory tree and collect files to serialize."""
    collected: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        current = Path(dirpath)
        try:
            rel_dir = current.relative_to(root)
            rel_dir_str = rel_dir.as_posix() if str(rel_dir) != "." else ""
        except ValueError:
            continue

        # Filter directories (modifies in-place to control recursion)
        dirnames[:] = sorted(
            d
            for d in dirnames
            if should_include_directory(
                d, f"{rel_dir_str}/{d}".lstrip("/") if rel_dir_str else d, patterns
            )
        )

        # Collect files
        for filename in sorted(filenames):
            rel_path = f"{rel_dir_str}/{filename}".lstrip("/") if rel_dir_str else filename
            if should_include_file(filename, rel_path, patterns):
                collected.append(current / filename)

    return collected


def read_file_node(path: Path, root: Path) -> Optional[dict]:
    """Read file and return manifest node dict, or None on error."""
    try:
        stat_info = path.stat()
    except OSError as e:
        print(f"Warning: Cannot stat {path}: {e}", file=sys.stderr)
        return None

    # Skip files exceeding size limit
    if stat_info.st_size > MAX_FILE_SIZE:
        print(
            f"Warning: Skipping {path} ({stat_info.st_size:,} bytes exceeds {MAX_FILE_SIZE:,} limit)",
            file=sys.stderr,
        )
        return None

    try:
        raw_bytes = path.read_bytes()
    except OSError as e:
        print(f"Warning: Cannot read {path}: {e}", file=sys.stderr)
        return None

    # Detect text vs binary
    try:
        content = raw_bytes.decode("utf-8")
        file_type = "text"
    except UnicodeDecodeError:
        content = base64.b64encode(raw_bytes).decode("ascii")
        file_type = "binary"

    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as e:
        print(f"Warning: Path escapes root {path}: {e}", file=sys.stderr)
        return None

    is_exec = bool(stat_info.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

    return {
        "path": relative,
        "type": file_type,
        "size": stat_info.st_size,
        "sha256": sha256_hash,
        "content": content,
        "is_executable": is_exec,
    }


def serialize_workspace(root: Path) -> dict:
    """Serialize workspace to manifest dictionary."""
    root = root.resolve()

    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    patterns = parse_gitignore(root)
    file_paths = collect_files(root, patterns)

    nodes: list[dict] = []
    total_size = 0

    for path in file_paths:
        # Check total size limit
        if total_size > MAX_TOTAL_SIZE:
            print(
                f"Warning: Total size exceeds {MAX_TOTAL_SIZE:,} bytes, stopping collection",
                file=sys.stderr,
            )
            break

        node = read_file_node(path, root)
        if node is not None:
            nodes.append(node)
            total_size += node["size"]

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "root": str(root),
        "timestamp": timestamp,
        "file_count": len(nodes),
        "total_size_bytes": total_size,
        "files": nodes,
    }


def yaml_escape(s: str) -> str:
    """Escape string for safe YAML output."""
    if not s:
        return "''"

    # Check if quoting needed
    needs_quotes = False

    # Reserved words
    if s.lower() in ("true", "false", "null", "yes", "no", "on", "off", "~"):
        needs_quotes = True

    # Starts with special char
    if s[0] in " -?:,[]{}#&*!|>'\"%@`":
        needs_quotes = True

    # Contains special chars
    if any(c in s for c in ":#[]{},"):
        needs_quotes = True

    # Ends with space
    if s.endswith(" "):
        needs_quotes = True

    # Looks like number
    try:
        float(s)
        needs_quotes = True
    except ValueError:
        pass

    if needs_quotes:
        # Use single quotes, escape internal single quotes
        return "'" + s.replace("'", "''") + "'"

    return s


def to_yaml(manifest: dict) -> str:
    """Convert manifest to YAML string using only stdlib."""
    lines: list[str] = []

    # Header fields
    lines.append(f"root: {yaml_escape(manifest['root'])}")
    lines.append(f"timestamp: '{manifest['timestamp']}'")
    lines.append(f"file_count: {manifest['file_count']}")
    lines.append(f"total_size_bytes: {manifest['total_size_bytes']}")
    lines.append("files:")

    for node in manifest["files"]:
        lines.append(f"  - path: {yaml_escape(node['path'])}")
        lines.append(f"    type: {node['type']}")
        lines.append(f"    size: {node['size']}")
        lines.append(f"    sha256: {node['sha256']}")

        content = node["content"]
        if not content:
            lines.append("    content: ''")
        elif "\n" in content or len(content) > 80:
            # Use literal block scalar for multiline or long content
            lines.append("    content: |")
            for content_line in content.split("\n"):
                lines.append(f"      {content_line}")
        else:
            lines.append(f"    content: {yaml_escape(content)}")

        lines.append(f"    is_executable: {str(node['is_executable']).lower()}")

    return "\n".join(lines) + "\n"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Serialize workspace to YAML manifest for Phaser post-audit validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python serialize.py --root . --output manifest.yaml
    python serialize.py --root ~/Projects/MyApp -o post-audit.yaml

Output is compatible with Phaser manifest format for diff comparison.
        """,
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Workspace root directory (default: current directory)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output YAML file path",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else Path.cwd() / args.output

    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Serializing {root}...", file=sys.stderr)

    try:
        manifest = serialize_workspace(root)
    except Exception as e:
        print(f"Error during serialization: {e}", file=sys.stderr)
        return 1

    yaml_content = to_yaml(manifest)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml_content, encoding="utf-8")
    except OSError as e:
        print(f"Error writing {output}: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f"Serialized {manifest['file_count']} files "
            f"({manifest['total_size_bytes']:,} bytes) to {output}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
