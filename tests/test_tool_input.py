"""Tests for tool input parsing and reconstruction."""

from pathlib import Path

import pytest

from tools.tool_input import (
    ProposedFile,
    ReconstructionResult,
    is_valid_text,
    reconstruct,
    reconstruct_edit,
    reconstruct_write,
)


class TestIsValidText:
    def test_normal_text(self) -> None:
        assert is_valid_text("Hello, world!\n")

    def test_empty_string(self) -> None:
        assert is_valid_text("")

    def test_null_bytes(self) -> None:
        assert not is_valid_text("hello\x00world")

    def test_high_binary_ratio(self) -> None:
        binary = "".join(chr(i) for i in range(1, 20))
        assert not is_valid_text(binary)


class TestReconstructWrite:
    def test_simple_write(self) -> None:
        result = reconstruct_write({"file_path": "/tmp/test.py", "content": "print('hello')"})
        assert not result.skipped
        assert len(result.files) == 1
        assert result.files[0].content == "print('hello')"

    def test_missing_path(self) -> None:
        result = reconstruct_write({"content": "test"})
        assert result.skipped
        assert result.skip_reason is not None
        assert "file_path" in result.skip_reason

    def test_binary_content(self) -> None:
        result = reconstruct_write({"file_path": "/tmp/test.bin", "content": "hello\x00world"})
        assert result.skipped
        assert result.skip_reason is not None
        assert "Binary" in result.skip_reason


class TestReconstructEdit:
    def test_simple_edit(self, tmp_path: Path) -> None:
        # Create file with known content
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        result = reconstruct_edit(
            {"file_path": str(test_file), "old_str": "hello", "new_str": "world"}
        )

        assert not result.skipped
        assert len(result.files) == 1
        assert result.files[0].content == "print('world')"

    def test_file_not_found(self) -> None:
        result = reconstruct_edit(
            {"file_path": "/nonexistent/file.py", "old_str": "a", "new_str": "b"}
        )
        assert result.skipped
        assert result.skip_reason is not None
        assert "not found" in result.skip_reason

    def test_old_str_not_found(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        result = reconstruct_edit(
            {"file_path": str(test_file), "old_str": "goodbye", "new_str": "world"}
        )
        assert result.skipped
        assert result.skip_reason is not None
        assert "old_str not found" in result.skip_reason


class TestReconstruct:
    def test_dispatch_write(self) -> None:
        result = reconstruct(
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/t.py", "content": "x"}}
        )
        assert not result.skipped

    def test_dispatch_edit(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("old")

        result = reconstruct(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(test_file), "old_str": "old", "new_str": "new"},
            }
        )
        assert not result.skipped

    def test_unknown_tool(self) -> None:
        result = reconstruct({"tool_name": "Unknown", "tool_input": {}})
        assert result.skipped
        assert result.skip_reason is not None
        assert "Unknown tool" in result.skip_reason
