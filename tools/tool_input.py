"""Parse hook input and reconstruct proposed file state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ProposedFile:
    """Represents a file's proposed state after an edit."""

    path: str
    content: str
    is_new: bool


@dataclass
class ReconstructionResult:
    """Result of reconstructing proposed state from hook input."""

    files: list[ProposedFile]
    skipped: bool
    skip_reason: Optional[str]


def is_valid_text(content: str) -> bool:
    """Check if content appears to be valid text (not binary)."""
    if not content:
        return True
    # Check for null bytes (common in binary)
    if "\x00" in content:
        return False
    # Check for high ratio of non-printable characters
    non_printable = sum(1 for c in content if ord(c) < 32 and c not in "\n\r\t")
    if len(content) > 0 and non_printable / len(content) > 0.1:
        return False
    return True


def reconstruct_write(tool_input: dict) -> ReconstructionResult:
    """Reconstruct state for Write operation."""
    path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    if not path:
        return ReconstructionResult([], True, "Missing file_path")

    if not is_valid_text(content):
        return ReconstructionResult([], True, "Binary content detected")

    return ReconstructionResult(
        files=[ProposedFile(path=path, content=content, is_new=not Path(path).exists())],
        skipped=False,
        skip_reason=None,
    )


def reconstruct_edit(tool_input: dict) -> ReconstructionResult:
    """Reconstruct state for Edit operation."""
    path = tool_input.get("file_path", "")
    old_str = tool_input.get("old_str", "")
    new_str = tool_input.get("new_str", "")

    if not path:
        return ReconstructionResult([], True, "Missing file_path")

    file_path = Path(path)
    if not file_path.exists():
        return ReconstructionResult([], True, f"File not found: {path}")

    try:
        current = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ReconstructionResult([], True, "Binary file detected")
    except OSError as e:
        return ReconstructionResult([], True, f"Cannot read file: {e}")

    if old_str not in current:
        return ReconstructionResult([], True, "old_str not found in file")

    # Apply replacement (first occurrence only)
    proposed = current.replace(old_str, new_str, 1)

    return ReconstructionResult(
        files=[ProposedFile(path=path, content=proposed, is_new=False)],
        skipped=False,
        skip_reason=None,
    )


def reconstruct(hook_input: dict) -> ReconstructionResult:
    """Reconstruct proposed file state from hook input."""
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name == "Write":
        return reconstruct_write(tool_input)
    elif tool_name == "Edit":
        return reconstruct_edit(tool_input)
    else:
        return ReconstructionResult([], True, f"Unknown tool: {tool_name}")
