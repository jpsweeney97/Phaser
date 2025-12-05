"""Tests for tools/branches.py — Branch management."""

from pathlib import Path

import pytest

from tools.branches import (
    BranchContext,
    BranchInfo,
    BranchError,
    BranchExistsError,
    BranchModeAlreadyActiveError,
    MergeStrategy,
    begin_branch_mode,
    branch_exists,
    checkout_branch,
    cleanup_branches,
    commit_all,
    commit_phase,
    create_branch,
    create_phase_branch,
    delete_branch,
    end_branch_mode,
    get_branch_context,
    get_current_branch,
    has_uncommitted_changes,
    merge_all_branches,
)


# -----------------------------------------------------------------------------
# BranchInfo Tests
# -----------------------------------------------------------------------------


def test_branch_info_creation() -> None:
    """BranchInfo can be created."""
    info = BranchInfo(
        phase_num=1,
        phase_slug="validation",
        branch_name="audit/test/phase-01-validation",
        created_at="2025-12-05T10:00:00Z",
    )
    assert info.phase_num == 1
    assert info.phase_slug == "validation"
    assert info.commit_sha is None
    assert info.merged is False


def test_branch_info_to_dict() -> None:
    """BranchInfo serializes to dict."""
    info = BranchInfo(
        phase_num=2,
        phase_slug="headers",
        branch_name="audit/test/phase-02-headers",
        created_at="2025-12-05T10:00:00Z",
        commit_sha="abc123",
        merged=True,
    )
    d = info.to_dict()
    assert d["phase_num"] == 2
    assert d["commit_sha"] == "abc123"
    assert d["merged"] is True


def test_branch_info_from_dict() -> None:
    """BranchInfo deserializes from dict."""
    d = {
        "phase_num": 3,
        "phase_slug": "cleanup",
        "branch_name": "audit/test/phase-03-cleanup",
        "created_at": "2025-12-05T10:00:00Z",
        "commit_sha": None,
        "merged": False,
    }
    info = BranchInfo.from_dict(d)
    assert info.phase_num == 3
    assert info.phase_slug == "cleanup"


# -----------------------------------------------------------------------------
# BranchContext Tests
# -----------------------------------------------------------------------------


def test_branch_context_creation() -> None:
    """BranchContext can be created."""
    ctx = BranchContext(
        audit_id="test-audit",
        audit_slug="test-slug",
        root=Path("/tmp/test"),
        base_branch="main",
    )
    assert ctx.audit_id == "test-audit"
    assert ctx.base_branch == "main"
    assert ctx.current_phase is None
    assert ctx.branches == []
    assert ctx.active is True


def test_branch_context_to_dict() -> None:
    """BranchContext serializes to dict."""
    ctx = BranchContext(
        audit_id="test",
        audit_slug="test-slug",
        root=Path("/tmp"),
        base_branch="main",
        current_phase=2,
        branches=[
            BranchInfo(1, "a", "audit/test/phase-01-a", "2025-12-05T10:00:00Z"),
        ],
    )
    d = ctx.to_dict()
    assert d["audit_id"] == "test"
    assert d["current_phase"] == 2
    assert len(d["branches"]) == 1


def test_branch_context_from_dict() -> None:
    """BranchContext deserializes from dict."""
    d = {
        "audit_id": "test",
        "audit_slug": "test-slug",
        "root": "/tmp/project",
        "base_branch": "develop",
        "current_phase": None,
        "branches": [],
        "active": True,
    }
    ctx = BranchContext.from_dict(d)
    assert ctx.audit_id == "test"
    assert ctx.base_branch == "develop"


def test_branch_context_get_branch() -> None:
    """BranchContext.get_branch finds branch by phase number."""
    ctx = BranchContext(
        audit_id="test",
        audit_slug="test",
        root=Path("/tmp"),
        base_branch="main",
        branches=[
            BranchInfo(1, "a", "audit/test/phase-01-a", "t"),
            BranchInfo(2, "b", "audit/test/phase-02-b", "t"),
        ],
    )
    b = ctx.get_branch(2)
    assert b is not None
    assert b.phase_slug == "b"

    assert ctx.get_branch(99) is None


def test_merge_strategy_enum() -> None:
    """MergeStrategy enum values."""
    assert MergeStrategy.SQUASH.value == "squash"
    assert MergeStrategy.REBASE.value == "rebase"
    assert MergeStrategy.MERGE.value == "merge"


# -----------------------------------------------------------------------------
# Git Operation Tests
# -----------------------------------------------------------------------------


def test_branch_exists(git_repo: Path) -> None:
    """Check if branch exists."""
    current = get_current_branch(git_repo)
    assert branch_exists(git_repo, current) is True
    assert branch_exists(git_repo, "nonexistent-branch") is False


def test_create_branch(git_repo: Path) -> None:
    """Create a new branch."""
    result = create_branch(git_repo, "new-branch")
    assert result is True
    assert branch_exists(git_repo, "new-branch") is True


def test_checkout_branch(git_repo: Path) -> None:
    """Checkout existing branch."""
    create_branch(git_repo, "test-branch")
    result = checkout_branch(git_repo, "test-branch")
    assert result is True
    assert get_current_branch(git_repo) == "test-branch"


def test_commit_all(git_repo: Path) -> None:
    """Stage and commit all changes."""
    (git_repo / "new_file.txt").write_text("content")

    sha = commit_all(git_repo, "Add new file")
    assert sha is not None
    assert len(sha) > 0
    assert has_uncommitted_changes(git_repo) is False


def test_commit_all_nothing_to_commit(git_repo: Path) -> None:
    """Commit returns None when nothing to commit."""
    sha = commit_all(git_repo, "Empty commit")
    assert sha is None


def test_delete_branch(git_repo: Path) -> None:
    """Delete a branch."""
    create_branch(git_repo, "to-delete")
    assert branch_exists(git_repo, "to-delete") is True

    result = delete_branch(git_repo, "to-delete", force=True)
    assert result is True
    assert branch_exists(git_repo, "to-delete") is False


# -----------------------------------------------------------------------------
# Branch Mode Tests
# -----------------------------------------------------------------------------


def test_begin_branch_mode(git_repo: Path) -> None:
    """Begin branch mode."""
    ctx = begin_branch_mode(git_repo, "test-audit", "test-slug")

    assert ctx.audit_id == "test-audit"
    assert ctx.audit_slug == "test-slug"
    assert ctx.root == git_repo.resolve()
    assert ctx.active is True

    # Cleanup
    end_branch_mode(ctx)


def test_begin_branch_mode_custom_base(git_repo: Path) -> None:
    """Begin branch mode with custom base branch."""
    create_branch(git_repo, "develop")

    ctx = begin_branch_mode(git_repo, "test-audit", "test-slug", base_branch="develop")

    assert ctx.base_branch == "develop"

    end_branch_mode(ctx)


def test_begin_branch_mode_already_active(git_repo: Path) -> None:
    """Begin branch mode fails if already active."""
    ctx = begin_branch_mode(git_repo, "first", "first")

    with pytest.raises(BranchModeAlreadyActiveError):
        begin_branch_mode(git_repo, "second", "second")

    end_branch_mode(ctx)


def test_begin_branch_mode_uncommitted_changes(git_repo: Path) -> None:
    """Begin branch mode fails with uncommitted changes."""
    (git_repo / "README.md").write_text("modified")

    with pytest.raises(BranchError):
        begin_branch_mode(git_repo, "test", "test")


def test_create_phase_branch_naming(git_repo: Path) -> None:
    """Create phase branch with correct naming."""
    ctx = begin_branch_mode(git_repo, "test-audit", "security-hardening")

    info = create_phase_branch(ctx, 1, "input-validation")

    assert info.branch_name == "audit/security-hardening/phase-01-input-validation"
    assert info.phase_num == 1
    assert info.phase_slug == "input-validation"
    assert branch_exists(git_repo, info.branch_name) is True

    end_branch_mode(ctx)


def test_create_phase_branch_chains(git_repo: Path) -> None:
    """Phase branches chain correctly."""
    ctx = begin_branch_mode(git_repo, "test", "test")

    # Create first branch
    info1 = create_phase_branch(ctx, 1, "first")
    (git_repo / "file1.txt").write_text("content1")
    commit_all(git_repo, "Phase 1")

    # Create second branch (should be based on first)
    info2 = create_phase_branch(ctx, 2, "second")

    # file1.txt should exist in second branch
    assert (git_repo / "file1.txt").exists()

    assert len(ctx.branches) == 2

    end_branch_mode(ctx)


def test_create_phase_branch_exists_error(git_repo: Path) -> None:
    """Create phase branch fails if branch exists."""
    ctx = begin_branch_mode(git_repo, "test", "test")

    create_phase_branch(ctx, 1, "first")

    # Try to create same branch again
    with pytest.raises(BranchExistsError):
        # Need to reset context to try creating same branch
        ctx.branches = []
        create_phase_branch(ctx, 1, "first")

    end_branch_mode(ctx)


def test_commit_phase(git_repo: Path) -> None:
    """Commit changes for a phase."""
    ctx = begin_branch_mode(git_repo, "test", "test")
    create_phase_branch(ctx, 1, "first")

    # Make a change
    (git_repo / "new_file.txt").write_text("content")

    sha = commit_phase(ctx, 1)
    assert sha is not None

    branch = ctx.get_branch(1)
    assert branch is not None
    assert branch.commit_sha == sha

    end_branch_mode(ctx)


def test_merge_all_branches_squash(git_repo: Path) -> None:
    """Merge all branches with squash strategy."""
    base = get_current_branch(git_repo)
    ctx = begin_branch_mode(git_repo, "test", "test", base_branch=base)

    # Create phase branch with changes
    create_phase_branch(ctx, 1, "first")
    (git_repo / "phase1.txt").write_text("phase 1 content")
    commit_phase(ctx, 1)

    # Merge back to base
    result = merge_all_branches(ctx, target=base, strategy=MergeStrategy.SQUASH)
    assert result is True

    # Check branches marked as merged
    assert ctx.branches[0].merged is True

    # Check we're on base branch with the changes
    assert get_current_branch(git_repo) == base
    assert (git_repo / "phase1.txt").exists()

    end_branch_mode(ctx)


def test_cleanup_branches(git_repo: Path) -> None:
    """Cleanup deletes merged branches."""
    base = get_current_branch(git_repo)
    ctx = begin_branch_mode(git_repo, "test", "test", base_branch=base)

    # Create and merge a branch
    info = create_phase_branch(ctx, 1, "first")
    (git_repo / "file.txt").write_text("content")
    commit_phase(ctx, 1)

    merge_all_branches(ctx, target=base, strategy=MergeStrategy.SQUASH)

    assert branch_exists(git_repo, info.branch_name) is True

    # Cleanup
    deleted = cleanup_branches(ctx, merged_only=True)
    assert deleted == 1
    assert branch_exists(git_repo, info.branch_name) is False

    end_branch_mode(ctx)


def test_get_branch_context(git_repo: Path) -> None:
    """Get branch context from storage."""
    # No context initially
    assert get_branch_context(git_repo) is None

    # Start branch mode
    ctx = begin_branch_mode(git_repo, "test", "test")

    # Should find it
    found = get_branch_context(git_repo)
    assert found is not None
    assert found.audit_id == "test"

    # End and check gone
    end_branch_mode(ctx)
    assert get_branch_context(git_repo) is None


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


def test_full_branch_workflow(git_repo: Path) -> None:
    """Full branch workflow: create, commit, merge, cleanup."""
    base = get_current_branch(git_repo)
    ctx = begin_branch_mode(git_repo, "integration", "integration-test", base_branch=base)

    # Phase 1
    create_phase_branch(ctx, 1, "first-change")
    (git_repo / "file1.py").write_text("print('phase 1')")
    sha1 = commit_phase(ctx, 1)
    assert sha1 is not None

    # Phase 2
    create_phase_branch(ctx, 2, "second-change")
    (git_repo / "file2.py").write_text("print('phase 2')")
    sha2 = commit_phase(ctx, 2)
    assert sha2 is not None

    # Verify both files exist on phase 2 branch
    assert (git_repo / "file1.py").exists()
    assert (git_repo / "file2.py").exists()

    # Merge
    result = merge_all_branches(ctx, target=base, strategy=MergeStrategy.SQUASH)
    assert result is True

    # Verify on base with all changes
    assert get_current_branch(git_repo) == base
    assert (git_repo / "file1.py").exists()
    assert (git_repo / "file2.py").exists()

    # Cleanup
    deleted = cleanup_branches(ctx)
    assert deleted == 2

    end_branch_mode(ctx)


def test_branch_mode_with_multiple_phases(git_repo: Path) -> None:
    """Branch mode handles multiple phases correctly."""
    base = get_current_branch(git_repo)
    ctx = begin_branch_mode(git_repo, "multi", "multi-phase", base_branch=base)

    # Create 3 phases
    for i in range(1, 4):
        create_phase_branch(ctx, i, f"phase-{i}")
        (git_repo / f"phase{i}.txt").write_text(f"Phase {i}")
        commit_phase(ctx, i)

    assert len(ctx.branches) == 3

    # All phases should be on latest branch
    assert get_current_branch(git_repo) == "audit/multi-phase/phase-03-phase-3"
    assert (git_repo / "phase1.txt").exists()
    assert (git_repo / "phase2.txt").exists()
    assert (git_repo / "phase3.txt").exists()

    # Merge and cleanup
    merge_all_branches(ctx, target=base, strategy=MergeStrategy.SQUASH)
    cleanup_branches(ctx)
    end_branch_mode(ctx)


def test_branch_mode_handles_no_changes(git_repo: Path) -> None:
    """Branch mode handles phases with no changes."""
    base = get_current_branch(git_repo)
    ctx = begin_branch_mode(git_repo, "test", "test", base_branch=base)

    create_phase_branch(ctx, 1, "empty")

    # Don't make any changes
    sha = commit_phase(ctx, 1)
    assert sha is None  # Nothing to commit

    branch = ctx.get_branch(1)
    assert branch is not None
    assert branch.commit_sha is None

    end_branch_mode(ctx)
