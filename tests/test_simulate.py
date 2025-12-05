"""Tests for tools/simulate.py — Simulation engine."""

from pathlib import Path

import pytest

from tools.simulate import (
    SimulationContext,
    SimulationResult,
    SimulationAlreadyActiveError,
    NotAGitRepoError,
    begin_simulation,
    commit_simulation,
    get_active_simulation,
    get_current_branch,
    git_checkout_file,
    git_stash_pop,
    git_stash_push,
    has_uncommitted_changes,
    rollback_simulation,
    simulation_context,
    track_file_change,
)


# -----------------------------------------------------------------------------
# SimulationContext Tests
# -----------------------------------------------------------------------------


def test_simulation_context_creation() -> None:
    """SimulationContext can be created."""
    ctx = SimulationContext(
        audit_id="test-audit",
        root=Path("/tmp/test"),
        original_branch="main",
        stash_ref=None,
    )
    assert ctx.audit_id == "test-audit"
    assert ctx.original_branch == "main"
    assert ctx.active is True
    assert ctx.created_files == []
    assert ctx.modified_files == []


def test_simulation_context_to_dict() -> None:
    """SimulationContext serializes to dict."""
    ctx = SimulationContext(
        audit_id="test",
        root=Path("/tmp"),
        original_branch="main",
        stash_ref="stash@{0}",
        created_files=[Path("new.py")],
        modified_files=[Path("old.py")],
        started_at="2025-12-05T10:00:00Z",
    )
    d = ctx.to_dict()
    assert d["audit_id"] == "test"
    assert d["stash_ref"] == "stash@{0}"
    assert d["created_files"] == ["new.py"]
    assert d["modified_files"] == ["old.py"]


def test_simulation_context_from_dict() -> None:
    """SimulationContext deserializes from dict."""
    d = {
        "audit_id": "test",
        "root": "/tmp/project",
        "original_branch": "develop",
        "stash_ref": None,
        "created_files": ["a.py", "b.py"],
        "modified_files": [],
        "deleted_files": [],
        "started_at": "2025-12-05T10:00:00Z",
        "active": True,
    }
    ctx = SimulationContext.from_dict(d)
    assert ctx.audit_id == "test"
    assert ctx.original_branch == "develop"
    assert len(ctx.created_files) == 2


# -----------------------------------------------------------------------------
# SimulationResult Tests
# -----------------------------------------------------------------------------


def test_simulation_result_summary_success() -> None:
    """SimulationResult summary for success."""
    result = SimulationResult(
        success=True,
        phases_run=5,
        phases_passed=5,
        phases_failed=0,
        first_failure=None,
        failure_reason=None,
        duration=10.5,
        diff_summary="+3 created, ~2 modified",
        files_created=3,
        files_modified=2,
        files_deleted=0,
    )
    summary = result.summary()
    assert "SUCCESS" in summary
    assert "5/5 passed" in summary
    assert "create 3" in summary
    assert "modify 2" in summary


def test_simulation_result_summary_failure() -> None:
    """SimulationResult summary for failure."""
    result = SimulationResult(
        success=False,
        phases_run=5,
        phases_passed=3,
        phases_failed=2,
        first_failure=4,
        failure_reason="Test failed",
        duration=8.0,
        diff_summary="",
        files_created=1,
        files_modified=1,
        files_deleted=0,
    )
    summary = result.summary()
    assert "FAILED" in summary
    assert "3/5 passed" in summary
    assert "Phase 4" in summary
    assert "Test failed" in summary


def test_simulation_result_to_dict() -> None:
    """SimulationResult serializes to dict."""
    result = SimulationResult(
        success=True,
        phases_run=3,
        phases_passed=3,
        phases_failed=0,
        first_failure=None,
        failure_reason=None,
        duration=5.0,
        diff_summary="test",
    )
    d = result.to_dict()
    assert d["success"] is True
    assert d["phases_run"] == 3


# -----------------------------------------------------------------------------
# Git Helper Tests
# -----------------------------------------------------------------------------


def test_get_current_branch(git_repo: Path) -> None:
    """Get current branch name."""
    branch = get_current_branch(git_repo)
    # Git init creates either "main" or "master" depending on config
    assert branch in ("main", "master")


def test_has_uncommitted_changes_clean(git_repo: Path) -> None:
    """Clean repo has no uncommitted changes."""
    assert has_uncommitted_changes(git_repo) is False


def test_has_uncommitted_changes_dirty(git_repo: Path) -> None:
    """Dirty repo has uncommitted changes."""
    (git_repo / "new_file.txt").write_text("new content")
    assert has_uncommitted_changes(git_repo) is True


def test_git_stash_push_pop(git_repo: Path) -> None:
    """Stash push and pop work correctly."""
    # Create uncommitted change
    (git_repo / "README.md").write_text("modified content")
    assert has_uncommitted_changes(git_repo) is True

    # Stash it
    stash_ref = git_stash_push(git_repo, "test stash")
    assert stash_ref is not None
    assert has_uncommitted_changes(git_repo) is False

    # Pop it
    result = git_stash_pop(git_repo, stash_ref)
    assert result is True
    assert has_uncommitted_changes(git_repo) is True


def test_git_stash_push_nothing_to_stash(git_repo: Path) -> None:
    """Stash push returns None when nothing to stash."""
    assert has_uncommitted_changes(git_repo) is False
    stash_ref = git_stash_push(git_repo, "empty stash")
    assert stash_ref is None


def test_git_checkout_file(git_repo_with_files: Path) -> None:
    """Checkout restores file from HEAD."""
    file_path = git_repo_with_files / "src" / "main.py"
    original = file_path.read_text()

    # Modify file
    file_path.write_text("modified content")
    assert file_path.read_text() != original

    # Checkout to restore
    result = git_checkout_file(git_repo_with_files, Path("src/main.py"))
    assert result is True
    assert file_path.read_text() == original


# -----------------------------------------------------------------------------
# Simulation Tests
# -----------------------------------------------------------------------------


def test_begin_simulation_clean_repo(git_repo: Path) -> None:
    """Begin simulation on clean repo."""
    ctx = begin_simulation(git_repo, "test-audit")

    assert ctx.audit_id == "test-audit"
    assert ctx.root == git_repo.resolve()
    assert ctx.stash_ref is None  # Nothing to stash
    assert ctx.active is True

    # Cleanup
    rollback_simulation(ctx)


def test_begin_simulation_dirty_repo_stashes(git_repo: Path) -> None:
    """Begin simulation on dirty repo stashes changes."""
    # Create uncommitted change
    (git_repo / "README.md").write_text("modified")
    assert has_uncommitted_changes(git_repo) is True

    ctx = begin_simulation(git_repo, "test-audit")

    assert ctx.stash_ref is not None
    assert has_uncommitted_changes(git_repo) is False

    # Cleanup - should restore stash
    rollback_simulation(ctx)
    assert has_uncommitted_changes(git_repo) is True


def test_begin_simulation_not_git_repo(temp_dir: Path) -> None:
    """Begin simulation fails on non-git directory."""
    with pytest.raises(NotAGitRepoError):
        begin_simulation(temp_dir, "test-audit")


def test_begin_simulation_already_active(git_repo: Path) -> None:
    """Begin simulation fails if already active."""
    ctx = begin_simulation(git_repo, "first-audit")

    with pytest.raises(SimulationAlreadyActiveError):
        begin_simulation(git_repo, "second-audit")

    # Cleanup
    rollback_simulation(ctx)


def test_track_file_created(git_repo: Path) -> None:
    """Track created file."""
    ctx = begin_simulation(git_repo, "test-audit")

    track_file_change(ctx, Path("new_file.py"), "created")

    assert len(ctx.created_files) == 1
    assert ctx.created_files[0] == Path("new_file.py")

    rollback_simulation(ctx)


def test_track_file_modified(git_repo: Path) -> None:
    """Track modified file."""
    ctx = begin_simulation(git_repo, "test-audit")

    track_file_change(ctx, Path("README.md"), "modified")

    assert len(ctx.modified_files) == 1
    assert ctx.modified_files[0] == Path("README.md")

    rollback_simulation(ctx)


def test_rollback_restores_modified_file(git_repo_with_files: Path) -> None:
    """Rollback restores modified files."""
    original = (git_repo_with_files / "src" / "main.py").read_text()

    ctx = begin_simulation(git_repo_with_files, "test-audit")

    # Modify file and track
    (git_repo_with_files / "src" / "main.py").write_text("modified content")
    track_file_change(ctx, Path("src/main.py"), "modified")

    # Rollback
    result = rollback_simulation(ctx)
    assert result is True

    # File should be restored
    assert (git_repo_with_files / "src" / "main.py").read_text() == original


def test_rollback_deletes_created_file(git_repo: Path) -> None:
    """Rollback deletes created files."""
    ctx = begin_simulation(git_repo, "test-audit")

    # Create file and track
    new_file = git_repo / "new_file.py"
    new_file.write_text("new content")
    track_file_change(ctx, Path("new_file.py"), "created")

    assert new_file.exists()

    # Rollback
    result = rollback_simulation(ctx)
    assert result is True

    # File should be deleted
    assert not new_file.exists()


def test_rollback_restores_stash(git_repo: Path) -> None:
    """Rollback restores stashed changes."""
    # Create uncommitted change
    (git_repo / "README.md").write_text("uncommitted change")

    ctx = begin_simulation(git_repo, "test-audit")
    assert ctx.stash_ref is not None

    # Clean after stash
    assert (git_repo / "README.md").read_text() == "# Test Repo"

    # Rollback
    rollback_simulation(ctx)

    # Uncommitted change should be restored
    assert (git_repo / "README.md").read_text() == "uncommitted change"


def test_commit_simulation_keeps_changes(git_repo: Path) -> None:
    """Commit simulation keeps changes."""
    ctx = begin_simulation(git_repo, "test-audit")

    # Create file
    new_file = git_repo / "kept_file.py"
    new_file.write_text("kept content")
    track_file_change(ctx, Path("kept_file.py"), "created")

    # Commit (don't rollback)
    result = commit_simulation(ctx)
    assert result is True

    # File should still exist
    assert new_file.exists()
    assert new_file.read_text() == "kept content"


def test_simulation_context_manager(git_repo: Path) -> None:
    """Context manager auto-rollback works."""
    new_file = git_repo / "temp_file.py"

    with simulation_context(git_repo, "test-audit") as ctx:
        new_file.write_text("temporary")
        track_file_change(ctx, Path("temp_file.py"), "created")
        assert new_file.exists()

    # After context, file should be deleted
    assert not new_file.exists()


def test_get_active_simulation(git_repo: Path) -> None:
    """Get active simulation context."""
    # No active simulation
    assert get_active_simulation(git_repo) is None

    # Start simulation
    ctx = begin_simulation(git_repo, "test-audit")

    # Should find it
    active = get_active_simulation(git_repo)
    assert active is not None
    assert active.audit_id == "test-audit"

    # Cleanup
    rollback_simulation(ctx)

    # Should be gone
    assert get_active_simulation(git_repo) is None


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


def test_simulate_creates_and_rolls_back_file(git_repo: Path) -> None:
    """Full simulation with file creation and rollback."""
    with simulation_context(git_repo, "integration-test") as ctx:
        # Create multiple files
        (git_repo / "file1.py").write_text("content1")
        (git_repo / "file2.py").write_text("content2")
        track_file_change(ctx, Path("file1.py"), "created")
        track_file_change(ctx, Path("file2.py"), "created")

        assert (git_repo / "file1.py").exists()
        assert (git_repo / "file2.py").exists()

    # Both files should be gone
    assert not (git_repo / "file1.py").exists()
    assert not (git_repo / "file2.py").exists()


def test_simulate_modifies_and_rolls_back_file(git_repo_with_files: Path) -> None:
    """Full simulation with file modification and rollback."""
    original = (git_repo_with_files / "src" / "main.py").read_text()

    with simulation_context(git_repo_with_files, "integration-test") as ctx:
        (git_repo_with_files / "src" / "main.py").write_text("modified")
        track_file_change(ctx, Path("src/main.py"), "modified")

        assert (git_repo_with_files / "src" / "main.py").read_text() == "modified"

    # File should be restored
    assert (git_repo_with_files / "src" / "main.py").read_text() == original


def test_simulate_multiple_changes_rollback(git_repo_with_files: Path) -> None:
    """Full simulation with multiple change types."""
    original_main = (git_repo_with_files / "src" / "main.py").read_text()

    with simulation_context(git_repo_with_files, "integration-test") as ctx:
        # Create new file
        (git_repo_with_files / "new.py").write_text("new")
        track_file_change(ctx, Path("new.py"), "created")

        # Modify existing file
        (git_repo_with_files / "src" / "main.py").write_text("modified")
        track_file_change(ctx, Path("src/main.py"), "modified")

        assert (git_repo_with_files / "new.py").exists()
        assert (git_repo_with_files / "src" / "main.py").read_text() == "modified"

    # All changes should be rolled back
    assert not (git_repo_with_files / "new.py").exists()
    assert (git_repo_with_files / "src" / "main.py").read_text() == original_main
