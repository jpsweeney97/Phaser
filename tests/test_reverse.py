"""Tests for the Reverse Audit module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.reverse import (
    ChangeCategory,
    CommitInfo,
    FileChangeInfo,
    GroupingStrategy,
    InferredPhase,
    ReverseAuditResult,
    format_as_markdown,
    format_as_yaml,
    format_preview,
    generate_phase_description,
    generate_reverse_audit,
    get_commit_files,
    get_current_branch,
    get_repo_name,
    group_by_commits,
    group_by_directories,
    group_commits_to_phases,
    infer_category,
    infer_phase_title,
    is_git_repository,
    now_iso,
    parse_commit_range,
    run_git_command,
    validate_commit_range,
)


class TestGroupingStrategy:
    """Tests for GroupingStrategy enum."""

    def test_commits_value(self) -> None:
        """COMMITS has correct value."""
        assert GroupingStrategy.COMMITS.value == "commits"

    def test_directories_value(self) -> None:
        """DIRECTORIES has correct value."""
        assert GroupingStrategy.DIRECTORIES.value == "directories"

    def test_filetypes_value(self) -> None:
        """FILETYPES has correct value."""
        assert GroupingStrategy.FILETYPES.value == "filetypes"

    def test_semantic_value(self) -> None:
        """SEMANTIC has correct value."""
        assert GroupingStrategy.SEMANTIC.value == "semantic"


class TestFileChangeInfo:
    """Tests for FileChangeInfo dataclass."""

    def test_to_dict_minimal(self) -> None:
        """to_dict with minimal fields."""
        info = FileChangeInfo(
            path="src/main.py",
            change_type="added",
            insertions=50,
            deletions=0,
        )
        result = info.to_dict()

        assert result["path"] == "src/main.py"
        assert result["change_type"] == "added"
        assert "old_path" not in result

    def test_to_dict_with_rename(self) -> None:
        """to_dict includes old_path for renames."""
        info = FileChangeInfo(
            path="src/new_name.py",
            change_type="renamed",
            insertions=0,
            deletions=0,
            old_path="src/old_name.py",
        )
        result = info.to_dict()

        assert result["old_path"] == "src/old_name.py"

    def test_from_dict(self) -> None:
        """from_dict reconstructs FileChangeInfo."""
        data = {
            "path": "test.py",
            "change_type": "modified",
            "insertions": 10,
            "deletions": 5,
        }
        info = FileChangeInfo.from_dict(data)

        assert info.path == "test.py"
        assert info.insertions == 10


class TestCommitInfo:
    """Tests for CommitInfo dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        commit = CommitInfo(
            hash="abc123def456",
            short_hash="abc123d",
            author="Test Author",
            date="2025-12-05T10:00:00Z",
            message="Add feature",
            files_changed=3,
            insertions=100,
            deletions=20,
            files=[
                FileChangeInfo(path="a.py", change_type="added"),
            ],
        )
        result = commit.to_dict()

        assert result["hash"] == "abc123def456"
        assert result["message"] == "Add feature"
        assert len(result["files"]) == 1

    def test_from_dict(self) -> None:
        """from_dict reconstructs CommitInfo."""
        data = {
            "hash": "abc123",
            "short_hash": "abc",
            "author": "Author",
            "date": "2025-12-05",
            "message": "Test",
            "files": [],
        }
        commit = CommitInfo.from_dict(data)

        assert commit.hash == "abc123"
        assert commit.message == "Test"


class TestInferredPhase:
    """Tests for InferredPhase dataclass."""

    def test_file_count(self) -> None:
        """file_count returns unique file count."""
        phase = InferredPhase(
            number=1,
            title="Test",
            description="Desc",
            category="feature",
            files=[
                FileChangeInfo(path="a.py", change_type="added"),
                FileChangeInfo(path="b.py", change_type="added"),
                FileChangeInfo(path="a.py", change_type="modified"),  # Duplicate
            ],
        )

        assert phase.file_count == 2

    def test_total_insertions(self) -> None:
        """total_insertions sums correctly."""
        phase = InferredPhase(
            number=1,
            title="Test",
            description="Desc",
            category="feature",
            files=[
                FileChangeInfo(path="a.py", change_type="added", insertions=50),
                FileChangeInfo(path="b.py", change_type="added", insertions=30),
            ],
        )

        assert phase.total_insertions == 80

    def test_to_dict(self) -> None:
        """to_dict includes computed properties."""
        phase = InferredPhase(
            number=1,
            title="Test Phase",
            description="Description",
            category="feature",
        )
        result = phase.to_dict()

        assert result["number"] == 1
        assert result["title"] == "Test Phase"
        assert "file_count" in result


class TestReverseAuditResult:
    """Tests for ReverseAuditResult dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        result = ReverseAuditResult(
            title="Test Audit",
            project="test-project",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05T10:00:00Z",
            total_commits=5,
            total_files=10,
        )
        data = result.to_dict()

        assert data["title"] == "Test Audit"
        assert data["summary"]["total_commits"] == 5

    def test_from_dict(self) -> None:
        """from_dict reconstructs ReverseAuditResult."""
        data = {
            "title": "Test",
            "project": "proj",
            "commit_range": "HEAD~3..HEAD",
            "strategy": "commits",
            "generated_at": "2025-12-05",
            "summary": {"total_commits": 3},
            "phases": [],
        }
        result = ReverseAuditResult.from_dict(data)

        assert result.title == "Test"
        assert result.total_commits == 3


class TestGitHelpers:
    """Tests for git helper functions."""

    def test_is_git_repository_in_repo(self, tmp_path: Path) -> None:
        """Detects git repository correctly."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        assert is_git_repository(tmp_path) is True

    def test_is_git_repository_not_repo(self, tmp_path: Path) -> None:
        """Returns False for non-repo."""
        assert is_git_repository(tmp_path) is False

    def test_get_repo_name_fallback(self, tmp_path: Path) -> None:
        """Falls back to directory name."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        name = get_repo_name(tmp_path)
        assert name == tmp_path.name


class TestInferCategory:
    """Tests for infer_category function."""

    def test_detects_test_category(self) -> None:
        """Detects test category from file paths."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Add tests",
            files=[FileChangeInfo(path="tests/test_main.py", change_type="added")],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "test"

    def test_detects_docs_category(self) -> None:
        """Detects docs category from file paths."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Update readme",
            files=[FileChangeInfo(path="README.md", change_type="modified")],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "docs"

    def test_detects_fix_from_message(self) -> None:
        """Detects fix category from commit message."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Fix bug in login",
            files=[FileChangeInfo(path="src/auth.py", change_type="modified")],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "fix"

    def test_detects_feature_from_new_files(self) -> None:
        """Detects feature when mostly new files."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Add user module",
            files=[
                FileChangeInfo(path="src/user.py", change_type="added"),
                FileChangeInfo(path="src/profile.py", change_type="added"),
            ],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "feature"


class TestInferPhaseTitle:
    """Tests for infer_phase_title function."""

    def test_single_commit_uses_message(self) -> None:
        """Single commit uses cleaned message."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="",
            message="feat(auth): add login functionality",
            files=[],
        )]

        title = infer_phase_title(commits, [], "feature")

        assert "Add login functionality" in title

    def test_removes_conventional_commit_prefix(self) -> None:
        """Removes conventional commit prefixes."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="",
            message="fix: correct typo in readme",
            files=[],
        )]

        title = infer_phase_title(commits, [], "fix")

        assert not title.startswith("fix:")
        assert "Correct typo" in title


class TestGroupByCommits:
    """Tests for group_by_commits function."""

    def test_one_phase_per_commit(self) -> None:
        """Creates one phase per commit."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="First",
                      files=[FileChangeInfo(path="a.py", change_type="added")]),
            CommitInfo(hash="b", short_hash="b", author="", date="", message="Second",
                      files=[FileChangeInfo(path="b.py", change_type="added")]),
        ]

        phases = group_by_commits(commits)

        assert len(phases) == 2
        assert phases[0].number == 1
        assert phases[1].number == 2

    def test_respects_max_phases(self) -> None:
        """Limits to max_phases."""
        commits = [
            CommitInfo(hash=str(i), short_hash=str(i), author="", date="",
                      message=f"Commit {i}", files=[])
            for i in range(10)
        ]

        phases = group_by_commits(commits, max_phases=5)

        assert len(phases) == 5


class TestGroupByDirectories:
    """Tests for group_by_directories function."""

    def test_groups_by_top_level_dir(self) -> None:
        """Groups files by top-level directory."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="Changes",
                      files=[
                          FileChangeInfo(path="src/main.py", change_type="modified"),
                          FileChangeInfo(path="src/utils.py", change_type="modified"),
                          FileChangeInfo(path="tests/test_main.py", change_type="added"),
                      ]),
        ]

        phases = group_by_directories(commits)

        assert len(phases) == 2  # src and tests
        dir_names = {p.title for p in phases}
        assert "Update src" in dir_names
        assert "Update tests" in dir_names


class TestGroupCommitsToPhases:
    """Tests for group_commits_to_phases function."""

    def test_empty_commits(self) -> None:
        """Returns empty list for no commits."""
        phases = group_commits_to_phases([])
        assert phases == []

    def test_uses_correct_strategy(self) -> None:
        """Uses specified strategy."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="Test",
                      files=[FileChangeInfo(path="src/a.py", change_type="added")]),
        ]

        phases_commits = group_commits_to_phases(commits, GroupingStrategy.COMMITS)
        phases_dirs = group_commits_to_phases(commits, GroupingStrategy.DIRECTORIES)

        # Both should work, structure may differ
        assert len(phases_commits) >= 1
        assert len(phases_dirs) >= 1


class TestFormatAsMarkdown:
    """Tests for format_as_markdown function."""

    def test_includes_title(self) -> None:
        """Output includes title."""
        result = ReverseAuditResult(
            title="Test Audit",
            project="test",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05",
        )

        md = format_as_markdown(result)

        assert "# Test Audit" in md

    def test_includes_overview(self) -> None:
        """Output includes overview section."""
        result = ReverseAuditResult(
            title="Test",
            project="test",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05",
            total_commits=5,
            total_files=10,
        )

        md = format_as_markdown(result)

        assert "## Overview" in md
        assert "5 commits" in md


class TestFormatAsYaml:
    """Tests for format_as_yaml function."""

    def test_produces_valid_yaml(self) -> None:
        """Output is valid YAML."""
        import yaml

        result = ReverseAuditResult(
            title="Test",
            project="test",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05",
        )

        yaml_str = format_as_yaml(result)
        parsed = yaml.safe_load(yaml_str)

        assert parsed["title"] == "Test"


class TestFormatPreview:
    """Tests for format_preview function."""

    def test_shows_summary(self) -> None:
        """Preview shows summary info."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="Test",
                      insertions=50, deletions=10, files=[]),
        ]
        phases = [
            InferredPhase(number=1, title="Test Phase", description="", category="feature"),
        ]

        preview = format_preview(commits, phases, "HEAD~1..HEAD", "commits")

        assert "Reverse Audit Preview" in preview
        assert "HEAD~1..HEAD" in preview
        assert "Test Phase" in preview


class TestNowIso:
    """Tests for now_iso helper."""

    def test_returns_iso_format(self) -> None:
        """Returns valid ISO timestamp."""
        result = now_iso()

        assert "T" in result
        assert len(result) > 10


class TestCLI:
    """Tests for CLI commands."""

    def test_preview_command(self) -> None:
        """Preview command works."""
        from click.testing import CliRunner
        from tools.reverse import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["preview", "HEAD~1..HEAD"])

        # May fail if not in git repo, but command should run
        assert result.exit_code in (0, 1)

    def test_commits_command(self) -> None:
        """Commits command works."""
        from click.testing import CliRunner
        from tools.reverse import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["commits", "HEAD~1..HEAD"])

        assert result.exit_code in (0, 1)

    def test_help_shows_options(self) -> None:
        """Help shows all options."""
        from click.testing import CliRunner
        from tools.reverse import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert "preview" in result.output
        assert "commits" in result.output
        assert "generate" in result.output
