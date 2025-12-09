"""Tests for the Phaser post-audit serializer."""

import base64
from pathlib import Path

import pytest

from tools.serialize import (
    DEFAULT_EXCLUDES,
    ALLOWED_HIDDEN_DIRS,
    ALLOWED_HIDDEN_FILES,
    MAX_FILE_SIZE,
    collect_files,
    is_ignored,
    matches_gitignore,
    parse_gitignore,
    read_file_node,
    serialize_workspace,
    should_include_directory,
    should_include_file,
    to_yaml,
    yaml_escape,
)


class TestDefaultExcludes:
    """Tests for default exclude patterns."""

    def test_contains_standard_excludes(self) -> None:
        """Verify common directories are excluded."""
        assert ".git" in DEFAULT_EXCLUDES
        assert "__pycache__" in DEFAULT_EXCLUDES
        assert "node_modules" in DEFAULT_EXCLUDES
        assert ".venv" in DEFAULT_EXCLUDES

    def test_allowed_hidden_dirs(self) -> None:
        """Verify useful hidden dirs are allowed."""
        assert ".github" in ALLOWED_HIDDEN_DIRS
        assert ".circleci" in ALLOWED_HIDDEN_DIRS

    def test_allowed_hidden_files(self) -> None:
        """Verify useful hidden files are allowed."""
        assert ".gitignore" in ALLOWED_HIDDEN_FILES
        assert ".editorconfig" in ALLOWED_HIDDEN_FILES


class TestGitignoreParsing:
    """Tests for gitignore parsing."""

    def test_parses_gitignore(self, temp_dir: Path) -> None:
        """Verify .gitignore patterns are extracted."""
        (temp_dir / ".gitignore").write_text("*.pyc\nbuild/\n__pycache__/\n")

        patterns = parse_gitignore(temp_dir)

        assert "*.pyc" in patterns
        assert "build/" in patterns
        assert "__pycache__/" in patterns

    def test_handles_missing_gitignore(self, temp_dir: Path) -> None:
        """Verify empty patterns when no .gitignore exists."""
        patterns = parse_gitignore(temp_dir)

        assert patterns == []

    def test_skips_comments_and_blanks(self, temp_dir: Path) -> None:
        """Verify comments and blank lines are ignored."""
        (temp_dir / ".gitignore").write_text(
            "# This is a comment\n\n*.log\n  \n# Another comment\ndist/\n"
        )

        patterns = parse_gitignore(temp_dir)

        assert len(patterns) == 2
        assert "*.log" in patterns
        assert "dist/" in patterns
        assert "# This is a comment" not in patterns


class TestPatternMatching:
    """Tests for gitignore pattern matching."""

    def test_matches_simple_pattern(self) -> None:
        """Verify simple filename patterns match."""
        assert matches_gitignore("test.pyc", "*.pyc") is True
        assert matches_gitignore("src/test.pyc", "*.pyc") is True

    def test_matches_directory_pattern(self) -> None:
        """Verify patterns ending with / match directories."""
        assert matches_gitignore("build/output.txt", "build/") is True
        assert matches_gitignore("src/build/output.txt", "build/") is True

    def test_matches_rooted_pattern(self) -> None:
        """Verify patterns starting with / anchor to root."""
        assert matches_gitignore("build", "/build") is True
        assert matches_gitignore("src/build", "/build") is False

    def test_negation_not_supported(self) -> None:
        """Verify ! patterns are skipped (documented limitation)."""
        # Negation patterns should not match (return False)
        assert matches_gitignore("important.log", "!important.log") is False

    def test_is_ignored_with_multiple_patterns(self) -> None:
        """Verify is_ignored checks all patterns."""
        patterns = ["*.pyc", "build/", "*.log"]

        assert is_ignored("test.pyc", patterns) is True
        assert is_ignored("app.log", patterns) is True
        assert is_ignored("src/main.py", patterns) is False


class TestDirectoryFiltering:
    """Tests for directory inclusion logic."""

    def test_excludes_default_directories(self) -> None:
        """Verify default excludes are filtered."""
        assert should_include_directory(".git", ".git", []) is False
        assert should_include_directory("node_modules", "node_modules", []) is False
        assert should_include_directory("__pycache__", "__pycache__", []) is False

    def test_excludes_hidden_directories(self) -> None:
        """Verify hidden directories are excluded by default."""
        assert should_include_directory(".secret", ".secret", []) is False
        assert should_include_directory(".cache", ".cache", []) is False

    def test_allows_whitelisted_hidden_dirs(self) -> None:
        """Verify allowed hidden directories pass."""
        assert should_include_directory(".github", ".github", []) is True
        assert should_include_directory(".circleci", ".circleci", []) is True

    def test_respects_gitignore_patterns(self) -> None:
        """Verify gitignore patterns exclude directories."""
        patterns = ["vendor/", "tmp/"]

        assert should_include_directory("vendor", "vendor", patterns) is False
        assert should_include_directory("tmp", "tmp", patterns) is False
        assert should_include_directory("src", "src", patterns) is True


class TestFileFiltering:
    """Tests for file inclusion logic."""

    def test_excludes_hidden_files(self) -> None:
        """Verify hidden files are excluded by default."""
        assert should_include_file(".secret", ".secret", []) is False
        assert should_include_file(".env.local", ".env.local", []) is False

    def test_allows_whitelisted_hidden_files(self) -> None:
        """Verify allowed hidden files pass."""
        assert should_include_file(".gitignore", ".gitignore", []) is True
        assert should_include_file(".editorconfig", ".editorconfig", []) is True

    def test_respects_gitignore_patterns(self) -> None:
        """Verify gitignore patterns exclude files."""
        patterns = ["*.log", "*.tmp"]

        assert should_include_file("app.log", "app.log", patterns) is False
        assert should_include_file("cache.tmp", "cache.tmp", patterns) is False
        assert should_include_file("main.py", "main.py", patterns) is True


class TestFileCollection:
    """Tests for file collection."""

    def test_collects_text_files(self, temp_dir: Path) -> None:
        """Verify text files are collected."""
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "main.py").write_text("print('hello')")
        (temp_dir / "README.md").write_text("# Project")

        files = collect_files(temp_dir, [])

        paths = [str(f.relative_to(temp_dir)) for f in files]
        assert "src/main.py" in paths
        assert "README.md" in paths

    def test_skips_default_excludes(self, temp_dir: Path) -> None:
        """Verify .git, node_modules, etc. are excluded."""
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "main.py").write_text("code")
        (temp_dir / ".git").mkdir()
        (temp_dir / ".git" / "config").write_text("git config")
        (temp_dir / "node_modules").mkdir()
        (temp_dir / "node_modules" / "pkg").mkdir()
        (temp_dir / "node_modules" / "pkg" / "index.js").write_text("module")

        files = collect_files(temp_dir, [])

        paths = [str(f.relative_to(temp_dir)) for f in files]
        assert "src/main.py" in paths
        assert not any(".git" in p for p in paths)
        assert not any("node_modules" in p for p in paths)

    def test_respects_gitignore(self, temp_dir: Path) -> None:
        """Verify .gitignore patterns are honored."""
        (temp_dir / "main.py").write_text("code")
        (temp_dir / "debug.log").write_text("logs")
        patterns = ["*.log"]

        files = collect_files(temp_dir, patterns)

        paths = [str(f.relative_to(temp_dir)) for f in files]
        assert "main.py" in paths
        assert "debug.log" not in paths


class TestBinaryDetection:
    """Tests for binary file detection."""

    def test_detects_text_files(self, temp_dir: Path) -> None:
        """Verify text files are identified correctly."""
        (temp_dir / "test.txt").write_text("Hello, world!")

        node = read_file_node(temp_dir / "test.txt", temp_dir)

        assert node is not None
        assert node["type"] == "text"
        assert node["content"] == "Hello, world!"

    def test_detects_binary_files(self, temp_dir: Path) -> None:
        """Verify binary files are identified by null bytes."""
        (temp_dir / "test.bin").write_bytes(b"\x00\x01\x02\xff")

        node = read_file_node(temp_dir / "test.bin", temp_dir)

        assert node is not None
        assert node["type"] == "binary"

    def test_encodes_binary_as_base64(self, temp_dir: Path) -> None:
        """Verify binary content is base64 encoded."""
        binary_content = b"\x00\x01\x02\xff"
        (temp_dir / "test.bin").write_bytes(binary_content)

        node = read_file_node(temp_dir / "test.bin", temp_dir)

        assert node is not None
        decoded = base64.b64decode(node["content"])
        assert decoded == binary_content


class TestFileSizeLimits:
    """Tests for file size limiting."""

    def test_skips_large_files(self, temp_dir: Path) -> None:
        """Verify files over MAX_FILE_SIZE are skipped."""
        # Create a file just over the limit
        large_content = "x" * (MAX_FILE_SIZE + 1)
        (temp_dir / "large.txt").write_text(large_content)

        node = read_file_node(temp_dir / "large.txt", temp_dir)

        assert node is None

    def test_includes_files_under_limit(self, temp_dir: Path) -> None:
        """Verify files under MAX_FILE_SIZE are included."""
        (temp_dir / "small.txt").write_text("small content")

        node = read_file_node(temp_dir / "small.txt", temp_dir)

        assert node is not None


class TestYamlOutput:
    """Tests for YAML generation."""

    def test_escapes_special_characters(self) -> None:
        """Verify YAML escaping for special chars."""
        assert yaml_escape("normal") == "normal"
        assert yaml_escape("has:colon") == "'has:colon'"
        assert yaml_escape("has space ") == "'has space '"
        assert yaml_escape("-starts-dash") == "'-starts-dash'"

    def test_escapes_reserved_words(self) -> None:
        """Verify YAML reserved words are quoted."""
        assert yaml_escape("true") == "'true'"
        assert yaml_escape("false") == "'false'"
        assert yaml_escape("null") == "'null'"
        assert yaml_escape("yes") == "'yes'"
        assert yaml_escape("no") == "'no'"

    def test_escapes_numeric_strings(self) -> None:
        """Verify numeric-looking strings are quoted."""
        assert yaml_escape("123") == "'123'"
        assert yaml_escape("3.14") == "'3.14'"

    def test_escapes_single_quotes_when_needed(self) -> None:
        """Verify single quotes are escaped when string needs quoting."""
        # String with colon needs quoting, so internal quotes get escaped
        assert yaml_escape("it's:here") == "'it''s:here'"
        # Plain string with apostrophe doesn't need quoting in YAML
        assert yaml_escape("it's") == "it's"

    def test_empty_string(self) -> None:
        """Verify empty string handling."""
        assert yaml_escape("") == "''"

    def test_multiline_content_uses_literal_block(self, temp_dir: Path) -> None:
        """Verify long content uses | block scalar."""
        (temp_dir / "multi.txt").write_text("line1\nline2\nline3")

        manifest = serialize_workspace(temp_dir)
        yaml_output = to_yaml(manifest)

        assert "content: |" in yaml_output

    def test_output_is_valid_yaml(self, temp_dir: Path) -> None:
        """Verify output can be parsed as YAML."""
        import yaml as pyyaml

        (temp_dir / "test.py").write_text("print('hello')")

        manifest = serialize_workspace(temp_dir)
        yaml_output = to_yaml(manifest)

        # Should not raise
        parsed = pyyaml.safe_load(yaml_output)

        assert parsed["file_count"] == 1
        assert len(parsed["files"]) == 1


class TestSerializeWorkspace:
    """Tests for workspace serialization."""

    def test_serializes_simple_project(self, temp_dir: Path) -> None:
        """Verify basic project serialization."""
        (temp_dir / "main.py").write_text("print('hello')")
        (temp_dir / "README.md").write_text("# Project")

        manifest = serialize_workspace(temp_dir)

        assert manifest["file_count"] == 2
        assert manifest["root"] == str(temp_dir.resolve())
        assert "timestamp" in manifest
        assert len(manifest["files"]) == 2

    def test_includes_file_metadata(self, temp_dir: Path) -> None:
        """Verify file nodes contain required fields."""
        (temp_dir / "test.py").write_text("code")

        manifest = serialize_workspace(temp_dir)

        assert len(manifest["files"]) == 1
        node = manifest["files"][0]
        assert "path" in node
        assert "type" in node
        assert "size" in node
        assert "sha256" in node
        assert "content" in node
        assert "is_executable" in node

    def test_computes_correct_hash(self, temp_dir: Path) -> None:
        """Verify SHA256 hash is computed correctly."""
        import hashlib

        content = "test content"
        (temp_dir / "test.txt").write_text(content)

        manifest = serialize_workspace(temp_dir)

        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        assert manifest["files"][0]["sha256"] == expected_hash

    def test_detects_executable_files(self, temp_dir: Path) -> None:
        """Verify executable flag is detected."""
        script = temp_dir / "script.sh"
        script.write_text("#!/bin/bash\necho hello")
        script.chmod(0o755)

        manifest = serialize_workspace(temp_dir)

        node = manifest["files"][0]
        assert node["is_executable"] is True

    def test_raises_for_non_directory(self, temp_dir: Path) -> None:
        """Verify error for non-directory input."""
        (temp_dir / "file.txt").write_text("content")

        with pytest.raises(ValueError, match="Not a directory"):
            serialize_workspace(temp_dir / "file.txt")

    def test_total_size_calculation(self, temp_dir: Path) -> None:
        """Verify total_size_bytes is sum of file sizes."""
        (temp_dir / "a.txt").write_text("12345")  # 5 bytes
        (temp_dir / "b.txt").write_text("123")  # 3 bytes

        manifest = serialize_workspace(temp_dir)

        assert manifest["total_size_bytes"] == 8
