"""End-to-end integration tests for complete audit workflows."""

from pathlib import Path

import pytest

from tools.branches import (
    MergeStrategy,
    begin_branch_mode,
    commit_phase,
    create_phase_branch,
    end_branch_mode,
    merge_all_branches,
)
from tools.contracts import AuditSource, RuleType, check_contract, create_contract
from tools.diff import capture_manifest, compare_manifests
from tools.events import EventEmitter, EventType
from tools.simulate import (
    begin_simulation,
    rollback_simulation,
    track_file_change,
)
from tools.storage import PhaserStorage


class TestStorageEventsIntegration:
    """Test storage and events working together."""

    def test_events_persisted_to_storage(
        self, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Events are saved to storage."""
        emitter.emit(
            EventType.AUDIT_STARTED, audit_id="test-1", project="Test", slug="test-audit"
        )
        emitter.emit(
            EventType.PHASE_STARTED, audit_id="test-1", phase=1, description="Test phase"
        )

        events = storage.get_events(audit_id="test-1")
        assert len(events) == 2
        assert events[0]["type"] == "audit_started"
        assert events[1]["type"] == "phase_started"

    def test_audit_lifecycle_events(
        self, storage: PhaserStorage, emitter: EventEmitter
    ) -> None:
        """Full audit lifecycle is tracked via events."""
        # Start audit
        emitter.emit(EventType.AUDIT_STARTED, audit_id="test-1", project="Test", slug="test")

        # Run phases
        for i in range(1, 4):
            emitter.emit(EventType.PHASE_STARTED, audit_id="test-1", phase=i)
            emitter.emit(EventType.PHASE_COMPLETED, audit_id="test-1", phase=i, duration=10.0)

        # Complete
        emitter.emit(EventType.AUDIT_COMPLETED, audit_id="test-1", duration=30.0)

        events = storage.get_events(audit_id="test-1")
        assert len(events) == 8  # 1 start + 3*(start+complete) + 1 complete


class TestDiffContractsIntegration:
    """Test diff and contracts working together."""

    def test_diff_captures_contract_violation_fix(
        self, git_repo_with_files: Path, storage: PhaserStorage
    ) -> None:
        """Diff captures changes that fix a contract violation."""
        # Create a "bad" file with singleton pattern
        bad_file = git_repo_with_files / "src" / "singleton.py"
        bad_file.write_text("class Service:\n    shared = Service()\n")

        # Capture before manifest
        before = capture_manifest(git_repo_with_files)

        # "Fix" the singleton
        bad_file.write_text("class Service:\n    def __init__(self): pass\n")

        # Capture after manifest
        after = capture_manifest(git_repo_with_files)

        # Diff shows the change
        diff = compare_manifests(before, after)
        assert len(diff.modified) == 1
        assert diff.modified[0].path == "src/singleton.py"

        # Contract now passes
        contract = create_contract(
            rule_id="no-singleton",
            rule_type=RuleType.FORBID_PATTERN,
            pattern=r"\.shared\s*=",
            file_glob="**/*.py",
            message="No singleton pattern",
            rationale="Use DI",
            audit_source=AuditSource(id="test", slug="test", date="2025-01-01", phase=1),
        )
        result = check_contract(contract, git_repo_with_files)
        assert result.passed

    def test_contract_violation_detected_in_diff(
        self, git_repo_with_files: Path, storage: PhaserStorage
    ) -> None:
        """Contract violation can be detected in changed files."""
        # File is clean initially
        main_file = git_repo_with_files / "src" / "main.py"
        original = main_file.read_text()

        # Capture before
        before = capture_manifest(git_repo_with_files)

        # Introduce a violation
        main_file.write_text(original + "\n# TODO: fix this later\n")

        # Capture after
        after = capture_manifest(git_repo_with_files)

        # Diff shows the change
        diff = compare_manifests(before, after)
        assert len(diff.modified) == 1

        # Contract catches the violation
        contract = create_contract(
            rule_id="no-todo",
            rule_type=RuleType.FORBID_PATTERN,
            pattern=r"TODO:",
            file_glob="**/*.py",
            message="No TODO comments",
            rationale="Track in issue tracker",
            audit_source=AuditSource(id="test", slug="test", date="2025-01-01", phase=1),
        )
        result = check_contract(contract, git_repo_with_files)
        assert not result.passed
        assert len(result.violations) == 1


class TestSimulationIntegration:
    """Test simulation with diff tracking."""

    def test_simulation_tracks_and_rolls_back(
        self, git_repo_with_files: Path, storage: PhaserStorage
    ) -> None:
        """Simulation tracks changes and rolls them back."""
        # Capture initial state
        initial = capture_manifest(git_repo_with_files)

        # Begin simulation
        ctx = begin_simulation(git_repo_with_files, "sim-test", storage)

        # Make changes
        new_file = git_repo_with_files / "new_file.py"
        new_file.write_text("# New file")
        track_file_change(ctx, Path("new_file.py"), "created")

        existing = git_repo_with_files / "src" / "main.py"
        original_content = existing.read_text()
        existing.write_text("# Modified")
        track_file_change(ctx, Path("src/main.py"), "modified")

        # Rollback
        rollback_simulation(ctx)

        # Verify restoration
        assert not new_file.exists()
        assert existing.read_text() == original_content

        # Capture final state - should match initial
        final = capture_manifest(git_repo_with_files)
        diff = compare_manifests(initial, final)
        assert len(diff.added) == 0
        assert len(diff.modified) == 0
        assert len(diff.deleted) == 0

    def test_simulation_diff_shows_changes_during(
        self, git_repo_with_files: Path, storage: PhaserStorage
    ) -> None:
        """Diff captures changes made during simulation."""
        # Capture before simulation
        before = capture_manifest(git_repo_with_files)

        # Begin simulation
        ctx = begin_simulation(git_repo_with_files, "sim-test", storage)

        # Make changes
        (git_repo_with_files / "added.py").write_text("# new")
        track_file_change(ctx, Path("added.py"), "created")

        # Capture during simulation
        during = capture_manifest(git_repo_with_files)

        # Diff shows changes
        diff = compare_manifests(before, during)
        assert len(diff.added) == 1
        assert diff.added[0].path == "added.py"

        # Rollback
        rollback_simulation(ctx)


class TestBranchingIntegration:
    """Test branching with events and storage."""

    def test_branch_workflow_with_events(
        self,
        git_repo_with_files: Path,
        storage: PhaserStorage,
        emitter: EventEmitter,
    ) -> None:
        """Branch workflow emits events for each phase."""
        # Begin branch mode
        ctx = begin_branch_mode(
            git_repo_with_files, "branch-test", "test-audit", storage=storage
        )

        try:
            # Phase 1
            branch1 = create_phase_branch(ctx, 1, "first-change")
            (git_repo_with_files / "phase1.txt").write_text("Phase 1")
            commit_phase(ctx, 1, "Phase 1: First change")
            emitter.emit(EventType.PHASE_COMPLETED, audit_id="branch-test", phase=1)

            # Phase 2
            branch2 = create_phase_branch(ctx, 2, "second-change")
            (git_repo_with_files / "phase2.txt").write_text("Phase 2")
            commit_phase(ctx, 2, "Phase 2: Second change")
            emitter.emit(EventType.PHASE_COMPLETED, audit_id="branch-test", phase=2)

            # Verify branches created
            assert branch1.branch_name == "audit/test-audit/phase-01-first-change"
            assert branch2.branch_name == "audit/test-audit/phase-02-second-change"

            # Merge
            merge_all_branches(ctx, strategy=MergeStrategy.SQUASH)

            # Verify files exist after merge
            assert (git_repo_with_files / "phase1.txt").exists()
            assert (git_repo_with_files / "phase2.txt").exists()

            # Verify events recorded
            events = storage.get_events(audit_id="branch-test")
            assert len(events) == 2
        finally:
            end_branch_mode(ctx)

    def test_branch_diff_per_phase(
        self, git_repo_with_files: Path, storage: PhaserStorage
    ) -> None:
        """Each phase branch has distinct diff."""
        ctx = begin_branch_mode(
            git_repo_with_files, "diff-test", "diff-audit", storage=storage
        )

        try:
            # Capture before any phases
            initial = capture_manifest(git_repo_with_files)

            # Phase 1
            create_phase_branch(ctx, 1, "phase-one")
            (git_repo_with_files / "file1.py").write_text("# phase 1")
            commit_phase(ctx, 1)

            # Diff shows phase 1 changes
            after_p1 = capture_manifest(git_repo_with_files)
            diff1 = compare_manifests(initial, after_p1)
            assert len(diff1.added) == 1
            assert diff1.added[0].path == "file1.py"

            # Phase 2
            create_phase_branch(ctx, 2, "phase-two")
            (git_repo_with_files / "file2.py").write_text("# phase 2")
            commit_phase(ctx, 2)

            # Diff from phase 1 shows only phase 2 changes
            after_p2 = capture_manifest(git_repo_with_files)
            diff2 = compare_manifests(after_p1, after_p2)
            assert len(diff2.added) == 1
            assert diff2.added[0].path == "file2.py"

            # Merge
            merge_all_branches(ctx, strategy=MergeStrategy.SQUASH)
        finally:
            end_branch_mode(ctx)


class TestFullAuditWorkflow:
    """Test complete audit lifecycle scenarios."""

    def test_audit_with_storage_events_diff(
        self,
        git_repo_with_files: Path,
        storage: PhaserStorage,
        emitter: EventEmitter,
    ) -> None:
        """Full audit records events and captures diffs."""
        # Start audit
        emitter.emit(
            EventType.AUDIT_STARTED,
            audit_id="full-audit",
            project="TestProject",
            slug="full-test",
        )

        # Capture initial state
        initial = capture_manifest(git_repo_with_files)

        # Execute "phase 1" - add a file
        emitter.emit(EventType.PHASE_STARTED, audit_id="full-audit", phase=1)
        (git_repo_with_files / "new_feature.py").write_text("def feature(): pass")
        after_p1 = capture_manifest(git_repo_with_files)
        emitter.emit(EventType.PHASE_COMPLETED, audit_id="full-audit", phase=1, duration=5.0)

        # Verify diff
        diff = compare_manifests(initial, after_p1)
        assert len(diff.added) == 1

        # Complete audit
        emitter.emit(EventType.AUDIT_COMPLETED, audit_id="full-audit", duration=10.0)

        # Verify events recorded
        events = storage.get_events(audit_id="full-audit")
        assert len(events) == 4  # started, phase_started, phase_completed, completed

    def test_simulated_audit_preserves_initial_state(
        self,
        git_repo_with_files: Path,
        storage: PhaserStorage,
    ) -> None:
        """Simulated audit doesn't modify the codebase."""
        # Capture before
        before = capture_manifest(git_repo_with_files)

        # Begin simulation
        ctx = begin_simulation(git_repo_with_files, "preserve-test", storage)

        # Make some changes
        (git_repo_with_files / "sim_file.py").write_text("# simulation")
        track_file_change(ctx, Path("sim_file.py"), "created")
        (git_repo_with_files / "src" / "main.py").write_text("# changed")
        track_file_change(ctx, Path("src/main.py"), "modified")

        # Rollback
        rollback_simulation(ctx)

        # Capture after
        after = capture_manifest(git_repo_with_files)

        # Should be identical
        diff = compare_manifests(before, after)
        assert len(diff.added) == 0
        assert len(diff.modified) == 0
        assert len(diff.deleted) == 0
