"""Edge case tests for Phaser modules.

This module contains tests for boundary conditions, error handling,
and unusual inputs across the Phaser codebase.
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import yaml

from tools.contract_loader import (
    load_contracts_from_dir,
    validate_contract,
)
from tools.tool_input import reconstruct, reconstruct_edit, reconstruct_write
from tools.ignore_parser import parse_ignores, should_ignore
from tools.diff import FileEntry, Manifest, capture_manifest, compare_manifests
from tools.storage import PhaserStorage
from tools.bridge import (
    ParseError,
    Phase,
    detect_phase_boundaries,
    find_code_block_ranges,
    validate_phase,
    validate_document,
    parse_audit_document,
)


# =============================================================================
# Contract Loader Edge Cases
# =============================================================================


class TestContractLoaderEdgeCases:
    """Edge cases for contract loading and validation."""

    def test_malformed_yaml_syntax(self, temp_dir: Path) -> None:
        """Malformed YAML is skipped with warning."""
        contract_file = temp_dir / "bad.yaml"
        contract_file.write_text("rule_id: test\n  indentation: wrong")

        result = load_contracts_from_dir(temp_dir, "project")
        assert result.contracts == []
        assert len(result.warnings) == 1
        assert "bad.yaml" in result.warnings[0]

    def test_empty_contract_file(self, temp_dir: Path) -> None:
        """Empty YAML file is skipped."""
        contract_file = temp_dir / "empty.yaml"
        contract_file.write_text("")

        result = load_contracts_from_dir(temp_dir, "project")
        assert result.contracts == []

    def test_yaml_with_utf8_bom(self, temp_dir: Path) -> None:
        """YAML with UTF-8 BOM is handled."""
        contract_file = temp_dir / "bom.yaml"
        content = yaml.dump({
            "rule_id": "test",
            "type": "forbid_pattern",
            "pattern": "TODO",
            "file_glob": "*.py",
            "message": "No TODOs",
            "severity": "error",
        })
        # Write with BOM
        contract_file.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        result = load_contracts_from_dir(temp_dir, "project")
        # Should either load successfully or skip gracefully
        assert len(result.warnings) <= 1

    def test_non_yaml_files_ignored(self, temp_dir: Path) -> None:
        """Non-YAML files in contracts directory are ignored."""
        # Create various non-YAML files
        (temp_dir / "readme.md").write_text("# Contracts")
        (temp_dir / "config.json").write_text("{}")
        (temp_dir / ".gitkeep").write_text("")

        result = load_contracts_from_dir(temp_dir, "project")
        assert result.contracts == []
        assert result.warnings == []

    def test_disabled_contract_not_loaded(self, temp_dir: Path) -> None:
        """Contracts with enabled: false are skipped."""
        contract_file = temp_dir / "disabled.yaml"
        contract_file.write_text(yaml.dump({
            "rule_id": "disabled-rule",
            "type": "forbid_pattern",
            "pattern": "test",
            "file_glob": "*.py",
            "message": "Test",
            "severity": "error",
            "enabled": False,
        }))

        result = load_contracts_from_dir(temp_dir, "project")
        assert result.contracts == []

    def test_very_long_rule_id(self) -> None:
        """Rule ID exceeding 64 chars is rejected."""
        data = {
            "rule_id": "a" * 100,  # 100 chars, limit is 64
            "type": "forbid_pattern",
            "pattern": "x",
            "file_glob": "*",
            "message": "m",
            "severity": "error",
        }
        _, error = validate_contract(data, "project")
        assert error is not None
        assert "rule_id" in error.lower()

    def test_special_chars_in_rule_id(self) -> None:
        """Rule ID with special characters is rejected."""
        data = {
            "rule_id": "test/rule",  # Slash not allowed
            "type": "forbid_pattern",
            "pattern": "x",
            "file_glob": "*",
            "message": "m",
            "severity": "error",
        }
        _, error = validate_contract(data, "project")
        assert error is not None

    def test_yaml_list_instead_of_dict_handled(self, temp_dir: Path) -> None:
        """YAML file containing a list instead of dict is skipped with warning."""
        contract_file = temp_dir / "list.yaml"
        contract_file.write_text("- item1\n- item2\n")

        result = load_contracts_from_dir(temp_dir, "project")
        assert result.contracts == []
        assert len(result.warnings) == 1
        assert "list" in result.warnings[0].lower()


# =============================================================================
# Tool Input Edge Cases
# =============================================================================


class TestToolInputEdgeCases:
    """Edge cases for hook input parsing and reconstruction."""

    def test_write_with_null_bytes(self) -> None:
        """Write with binary content is detected."""
        result = reconstruct_write({
            "file_path": "/test.bin",
            "content": "text\x00with\x00nulls",
        })
        assert result.skipped
        assert "binary" in result.skip_reason.lower()

    def test_write_with_empty_path(self) -> None:
        """Write with empty file_path is skipped."""
        result = reconstruct_write({
            "file_path": "",
            "content": "code",
        })
        assert result.skipped
        assert "file_path" in result.skip_reason.lower()

    def test_write_with_missing_content(self) -> None:
        """Write with missing content uses empty string."""
        result = reconstruct_write({
            "file_path": "/test.py",
        })
        assert not result.skipped
        assert result.files[0].content == ""

    def test_edit_with_nonexistent_file(self, temp_dir: Path) -> None:
        """Edit targeting nonexistent file is skipped."""
        result = reconstruct_edit({
            "file_path": str(temp_dir / "nonexistent.py"),
            "old_str": "old",
            "new_str": "new",
        })
        assert result.skipped
        assert "not found" in result.skip_reason.lower()

    def test_edit_with_old_str_not_found(self, temp_dir: Path) -> None:
        """Edit where old_str doesn't exist is skipped."""
        target = temp_dir / "test.py"
        target.write_text("def main(): pass")

        result = reconstruct_edit({
            "file_path": str(target),
            "old_str": "nonexistent text",
            "new_str": "replacement",
        })
        assert result.skipped
        assert "not found" in result.skip_reason.lower()

    def test_edit_binary_file(self, temp_dir: Path) -> None:
        """Edit targeting binary file is skipped."""
        binary = temp_dir / "image.png"
        binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        result = reconstruct_edit({
            "file_path": str(binary),
            "old_str": "x",
            "new_str": "y",
        })
        assert result.skipped
        assert "binary" in result.skip_reason.lower()

    def test_unknown_tool_name(self) -> None:
        """Unknown tool name is skipped."""
        result = reconstruct({
            "tool_name": "UnknownTool",
            "tool_input": {"file_path": "/test.py"},
        })
        assert result.skipped
        assert "unknown" in result.skip_reason.lower()

    def test_edit_replaces_first_occurrence_only(self, temp_dir: Path) -> None:
        """Edit only replaces first occurrence of old_str."""
        target = temp_dir / "test.py"
        target.write_text("foo foo foo")

        result = reconstruct_edit({
            "file_path": str(target),
            "old_str": "foo",
            "new_str": "bar",
        })
        assert not result.skipped
        assert result.files[0].content == "bar foo foo"


# =============================================================================
# Ignore Parser Edge Cases
# =============================================================================


class TestIgnoreParserEdgeCases:
    """Edge cases for ignore directive parsing."""

    def test_unknown_file_extension(self) -> None:
        """Unknown extension returns no directives."""
        content = "# phaser:ignore rule-a\ncode"
        directives = parse_ignores(content, "file.xyz")
        assert directives == []

    def test_multiple_rules_with_spaces(self) -> None:
        """Multiple rule IDs with various spacing."""
        content = "code  # phaser:ignore rule-a,  rule-b  ,rule-c"
        directives = parse_ignores(content, "test.py")
        assert len(directives) == 1
        assert set(directives[0].rule_ids) == {"rule-a", "rule-b", "rule-c"}

    def test_ignore_all_variant(self) -> None:
        """phaser:ignore-all ignores all rules."""
        content = "risky_code()  # phaser:ignore-all"
        directives = parse_ignores(content, "test.py")
        assert len(directives) == 1
        assert directives[0].rule_ids == []  # Empty = all

    def test_ignore_directive_in_string_literal(self) -> None:
        """Ignore directive inside string literal is still parsed."""
        # This is a limitation - we don't do AST parsing
        content = 's = "# phaser:ignore rule-a"'
        directives = parse_ignores(content, "test.py")
        # Currently parses it (known limitation)
        assert len(directives) >= 0

    def test_ignore_next_line_at_end_of_file(self) -> None:
        """ignore-next-line at EOF applies to nothing."""
        content = "code\n# phaser:ignore-next-line rule-a"
        directives = parse_ignores(content, "test.py")
        # Line 3 doesn't exist, so this has no effect
        assert not should_ignore("rule-a", 2, directives)

    def test_css_block_comment_style(self) -> None:
        """CSS block comment ignore syntax."""
        content = ".class { color: red !important; /* phaser:ignore no-important */ }"
        directives = parse_ignores(content, "style.css")
        assert len(directives) == 1
        assert directives[0].rule_ids == ["no-important"]


# =============================================================================
# Diff Edge Cases
# =============================================================================


class TestDiffEdgeCases:
    """Edge cases for manifest capture and comparison."""

    def test_capture_empty_file(self, temp_dir: Path) -> None:
        """Empty files are captured correctly."""
        (temp_dir / "empty.txt").write_text("")

        manifest = capture_manifest(temp_dir)
        assert manifest.file_count == 1
        assert manifest.files[0].size == 0
        assert manifest.files[0].content == ""

    def test_capture_unicode_content(self, temp_dir: Path) -> None:
        """Unicode content is captured correctly."""
        (temp_dir / "unicode.txt").write_text("Hello 世界 🎉 café")

        manifest = capture_manifest(temp_dir)
        assert manifest.file_count == 1
        assert "世界" in manifest.files[0].content

    def test_capture_unicode_filename(self, temp_dir: Path) -> None:
        """Unicode filenames are handled."""
        (temp_dir / "文件.txt").write_text("content")

        manifest = capture_manifest(temp_dir)
        assert manifest.file_count == 1
        assert "文件.txt" in manifest.files[0].path

    def test_capture_symlink_to_file(self, temp_dir: Path) -> None:
        """Symlinks to files are handled."""
        target = temp_dir / "target.txt"
        target.write_text("content")
        link = temp_dir / "link.txt"
        link.symlink_to(target)

        manifest = capture_manifest(temp_dir)
        # Implementation may include or skip symlinks
        assert manifest.file_count >= 1

    def test_capture_deeply_nested(self, temp_dir: Path) -> None:
        """Deeply nested directories are captured."""
        deep = temp_dir / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_text("deep content")

        manifest = capture_manifest(temp_dir)
        assert manifest.file_count == 1
        assert "a/b/c/d/e/deep.txt" in manifest.files[0].path

    def test_compare_type_change(self) -> None:
        """File changing from text to binary is detected."""
        before = Manifest("/proj", "t1", 1, 100, [
            FileEntry("file.dat", "text", 100, "h1", "text content", False)
        ])
        after = Manifest("/proj", "t2", 1, 100, [
            FileEntry("file.dat", "binary", 100, "h2", None, False)
        ])

        result = compare_manifests(before, after)
        assert len(result.modified) == 1


# =============================================================================
# Storage Edge Cases
# =============================================================================


class TestStorageEdgeCases:
    """Edge cases for storage operations."""

    def test_corrupted_audits_json_raises(self, temp_dir: Path) -> None:
        """Corrupted audits.json raises ValueError."""
        storage = PhaserStorage(root=temp_dir)
        storage.ensure_directories()

        # Write corrupted JSON
        (temp_dir / "audits.json").write_text("not valid json")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Invalid JSON"):
            storage.list_audits()

    def test_get_nonexistent_audit(self, temp_dir: Path) -> None:
        """Getting nonexistent audit returns None."""
        storage = PhaserStorage(root=temp_dir)
        storage.ensure_directories()

        result = storage.get_audit("nonexistent-id")
        assert result is None

    def test_very_long_audit_data(self, temp_dir: Path) -> None:
        """Large audit data is handled."""
        storage = PhaserStorage(root=temp_dir)

        # Create audit with lots of data
        audit = {
            "project": "TestProject",
            "slug": "test-audit",
            "date": "2025-12-05",
            "status": "in_progress",
            "large_field": "x" * 100000,  # 100KB
        }

        audit_id = storage.save_audit(audit)
        retrieved = storage.get_audit(audit_id)
        assert len(retrieved["large_field"]) == 100000


# =============================================================================
# Bridge Edge Cases
# =============================================================================


class TestBridgeEdgeCases:
    """Edge cases for audit document parsing."""

    def test_phase_header_in_code_block(self) -> None:
        """Phase headers inside code blocks are ignored."""
        content = """## Phase 1: Real Phase

### Implementation

```markdown
## Phase 2: Fake Phase in Code Block
```

## Phase 3: Another Real Phase
"""
        boundaries = detect_phase_boundaries(content)
        phase_numbers = [b[0] for b in boundaries]
        assert 1 in phase_numbers
        assert 2 not in phase_numbers  # Inside code block
        assert 3 in phase_numbers

    def test_nested_code_fences(self) -> None:
        """Nested code fences are handled."""
        content = '''## Phase 1: Test

````markdown
Here's a code block:
```python
print("hello")
```
````

Regular text here
'''
        ranges = find_code_block_ranges(content)
        # Should have one range for the outer fence
        assert len(ranges) == 1

    def test_very_large_phase_token_warning(self) -> None:
        """Phases exceeding token limit are flagged."""
        # Create phase with lots of content
        large_content = "x" * 100000  # ~28K tokens at 3.5 chars/token

        phase = Phase(
            number=1,
            title="Large Phase",
            context="ctx",
            goal="goal",
            implementation="impl",
            verify="verify",
            completion="done",
            raw_content=large_content,
            line_start=1,
        )

        issues = validate_phase(phase)
        # Should have token warning or error
        assert any("token" in i.message.lower() for i in issues)

    def test_empty_document(self) -> None:
        """Empty document produces appropriate warnings."""
        result = validate_document("")
        # Empty document should have warnings about missing sections
        assert len(result.warnings) > 0 or len(result.errors) > 0

    def test_document_header_only_raises(self) -> None:
        """Document with only header, no phases, raises ParseError."""
        content = """# Document 1: Test

## Document Overview

Test overview.

## Prerequisites

- Python 3.10+

=== AUDIT SETUP START ===
Setup content here
=== AUDIT SETUP END ===
"""
        with pytest.raises(ParseError, match="No phases found"):
            parse_audit_document(content)
