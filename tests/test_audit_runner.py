"""Tests for the Phaser audit runner."""

from pathlib import Path

import pytest

from tools.audit_runner import (
    AuditRunConfig,
    AuditRunner,
    PhaseResult,
    run_audit,
    simulate_phases,
)
from tools.storage import PhaserStorage


class TestPhaseResult:
    """Tests for PhaseResult dataclass."""

    def test_creation_with_defaults(self) -> None:
        """Verify PhaseResult can be created with minimal args."""
        result = PhaseResult(
            phase_num=1,
            description="Test phase",
            success=True,
            duration=1.5,
        )

        assert result.phase_num == 1
        assert result.description == "Test phase"
        assert result.success is True
        assert result.duration == 1.5
        assert result.error is None
        assert result.files_changed == []

    def test_creation_with_error(self) -> None:
        """Verify PhaseResult captures error information."""
        result = PhaseResult(
            phase_num=2,
            description="Failed phase",
            success=False,
            duration=0.5,
            error="Verification failed",
            files_changed=["src/main.py"],
        )

        assert result.success is False
        assert result.error == "Verification failed"
        assert result.files_changed == ["src/main.py"]

    def test_to_dict_serialization(self) -> None:
        """Verify to_dict produces expected structure."""
        result = PhaseResult(
            phase_num=1,
            description="Test",
            success=True,
            duration=1.0,
        )

        d = result.to_dict()

        assert d["phase_num"] == 1
        assert d["description"] == "Test"
        assert d["success"] is True
        assert d["duration"] == 1.0
        assert d["error"] is None
        assert d["files_changed"] == []


class TestAuditRunConfig:
    """Tests for AuditRunConfig dataclass."""

    def test_creation_with_required_args(self, temp_dir: Path) -> None:
        """Verify config can be created with minimal args."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="test-audit",
        )

        assert config.root == temp_dir
        assert config.audit_id == "test-audit"
        assert config.simulate is False
        assert config.branch_mode is False
        assert config.phases is None
        assert config.fail_fast is True

    def test_audit_slug_defaults_to_audit_id(self, temp_dir: Path) -> None:
        """Verify audit_slug defaults to audit_id when not provided."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="my-audit-123",
        )

        assert config.audit_slug == "my-audit-123"

    def test_audit_slug_preserved_when_provided(self, temp_dir: Path) -> None:
        """Verify explicit audit_slug is preserved."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="my-audit-123",
            audit_slug="custom-slug",
        )

        assert config.audit_slug == "custom-slug"

    def test_simulation_mode_config(self, temp_dir: Path) -> None:
        """Verify simulation mode configuration."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="sim-audit",
            simulate=True,
        )

        assert config.simulate is True
        assert config.branch_mode is False

    def test_branch_mode_config(self, temp_dir: Path) -> None:
        """Verify branch mode configuration."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="branch-audit",
            branch_mode=True,
        )

        assert config.branch_mode is True
        assert config.simulate is False

    def test_specific_phases_config(self, temp_dir: Path) -> None:
        """Verify specific phases can be configured."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="test-audit",
            phases=[1, 2, 3],
        )

        assert config.phases == [1, 2, 3]


class TestAuditRunnerModeSelection:
    """Tests for AuditRunner mode selection."""

    def test_selects_normal_mode_by_default(
        self, temp_dir: Path, storage: PhaserStorage
    ) -> None:
        """Verify normal mode is selected by default."""
        config = AuditRunConfig(root=temp_dir, audit_id="test")
        runner = AuditRunner(config, storage)

        # run() should not raise and return empty list (no phases)
        results = runner.run()

        assert results == []
        assert runner.simulation_ctx is None
        assert runner.branch_ctx is None

    def test_selects_simulation_mode_when_configured(
        self, git_repo: Path, storage: PhaserStorage
    ) -> None:
        """Verify simulation mode is selected when simulate=True."""
        config = AuditRunConfig(root=git_repo, audit_id="test", simulate=True)
        runner = AuditRunner(config, storage)

        results = runner.run()

        assert results == []
        # simulation_ctx should be None after run (cleaned up)
        assert runner.simulation_ctx is None


class TestAuditRunnerNormalMode:
    """Tests for normal mode execution."""

    def test_executes_specified_phases(
        self, temp_dir: Path, storage: PhaserStorage
    ) -> None:
        """Verify specified phases are executed."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="test",
            phases=[1, 2, 3],
        )
        runner = AuditRunner(config, storage)

        results = runner.run()

        assert len(results) == 3
        assert results[0].phase_num == 1
        assert results[1].phase_num == 2
        assert results[2].phase_num == 3

    def test_all_phases_succeed_by_default(
        self, temp_dir: Path, storage: PhaserStorage
    ) -> None:
        """Verify phases succeed with placeholder implementation."""
        config = AuditRunConfig(
            root=temp_dir,
            audit_id="test",
            phases=[1],
        )
        runner = AuditRunner(config, storage)

        results = runner.run()

        assert len(results) == 1
        assert results[0].success is True

    def test_returns_empty_when_no_phases(
        self, temp_dir: Path, storage: PhaserStorage
    ) -> None:
        """Verify empty results when no phases specified."""
        config = AuditRunConfig(root=temp_dir, audit_id="test")
        runner = AuditRunner(config, storage)

        results = runner.run()

        assert results == []


class TestAuditRunnerSimulationMode:
    """Tests for simulation mode execution."""

    def test_simulation_executes_phases(
        self, git_repo: Path, storage: PhaserStorage
    ) -> None:
        """Verify phases execute in simulation mode."""
        config = AuditRunConfig(
            root=git_repo,
            audit_id="test",
            simulate=True,
            phases=[1, 2],
        )
        runner = AuditRunner(config, storage)

        results = runner.run()

        assert len(results) == 2

    def test_simulation_context_cleaned_up(
        self, git_repo: Path, storage: PhaserStorage
    ) -> None:
        """Verify simulation context is cleaned up after run."""
        config = AuditRunConfig(
            root=git_repo,
            audit_id="test",
            simulate=True,
            phases=[1],
        )
        runner = AuditRunner(config, storage)

        runner.run()

        # Context should be None after cleanup
        assert runner.simulation_ctx is None

    def test_get_simulation_summary_returns_none_without_simulation(
        self, temp_dir: Path, storage: PhaserStorage
    ) -> None:
        """Verify summary returns None when not in simulation mode."""
        config = AuditRunConfig(root=temp_dir, audit_id="test")
        runner = AuditRunner(config, storage)

        summary = runner.get_simulation_summary()

        assert summary is None


class TestAuditRunnerFileTracking:
    """Tests for file change tracking."""

    def test_track_file_without_simulation_is_noop(
        self, temp_dir: Path, storage: PhaserStorage
    ) -> None:
        """Verify track_file does nothing outside simulation."""
        config = AuditRunConfig(root=temp_dir, audit_id="test")
        runner = AuditRunner(config, storage)

        # Should not raise
        runner.track_file(temp_dir / "test.py", "created")

        assert runner.simulation_ctx is None


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_run_audit_basic(self, temp_dir: Path) -> None:
        """Verify run_audit works with minimal args."""
        results = run_audit(temp_dir, "test-audit")

        assert results == []

    def test_run_audit_with_phases(self, temp_dir: Path) -> None:
        """Verify run_audit executes specified phases."""
        results = run_audit(temp_dir, "test-audit", phases=[1, 2])

        assert len(results) == 2

    def test_run_audit_simulation_mode(
        self, git_repo: Path, storage: PhaserStorage
    ) -> None:
        """Verify run_audit supports simulation mode."""
        results = run_audit(
            git_repo,
            "test-audit",
            simulate=True,
            phases=[1],
            storage=storage,
        )

        assert len(results) == 1

    def test_simulate_phases_returns_tuple(
        self, git_repo: Path, storage: PhaserStorage
    ) -> None:
        """Verify simulate_phases returns (results, summary)."""
        results, summary = simulate_phases(
            git_repo,
            "test-audit",
            phases=[1],
            storage=storage,
        )

        assert len(results) == 1
        assert isinstance(summary, str)

    def test_simulate_phases_default_summary(
        self, git_repo: Path, storage: PhaserStorage
    ) -> None:
        """Verify default summary when no changes tracked."""
        results, summary = simulate_phases(
            git_repo,
            "test-audit",
            phases=[1],
            storage=storage,
        )

        # Summary should indicate no changes (context cleaned up)
        assert summary == "No changes"
