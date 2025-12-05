"""Unified audit runner with simulation and branch mode support.

This module provides the AuditRunner class that executes audit phases
in different modes: normal, simulated, or branched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.events import EventEmitter
    from tools.storage import PhaserStorage

from tools.simulate import (
    SimulationContext,
    begin_simulation,
    commit_simulation,
    rollback_simulation,
    track_file_change,
)
from tools.branches import (
    BranchContext,
    begin_branch_mode,
    create_phase_branch,
    commit_phase,
    end_branch_mode,
)


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------


@dataclass
class PhaseResult:
    """Result of executing a single phase."""

    phase_num: int
    description: str
    success: bool
    duration: float
    error: str | None = None
    files_changed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize for reporting."""
        return {
            "phase_num": self.phase_num,
            "description": self.description,
            "success": self.success,
            "duration": self.duration,
            "error": self.error,
            "files_changed": self.files_changed,
        }


@dataclass
class AuditRunConfig:
    """Configuration for an audit run."""

    root: Path
    audit_id: str
    audit_slug: str = ""
    simulate: bool = False
    branch_mode: bool = False
    phases: list[int] | None = None  # None = all remaining
    fail_fast: bool = True
    verbose: bool = False

    def __post_init__(self) -> None:
        if not self.audit_slug:
            self.audit_slug = self.audit_id


# -----------------------------------------------------------------------------
# Audit Runner
# -----------------------------------------------------------------------------


class AuditRunner:
    """
    Unified audit runner supporting multiple execution modes.

    Modes:
    - Normal: Execute phases directly, changes are permanent
    - Simulated: Execute in sandbox, rollback after
    - Branched: Create git branch per phase (Phase 17)
    """

    def __init__(
        self,
        config: AuditRunConfig,
        storage: PhaserStorage | None = None,
        emitter: EventEmitter | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.emitter = emitter
        self.simulation_ctx: SimulationContext | None = None
        self.branch_ctx: BranchContext | None = None
        self._results: list[PhaseResult] = []

    def run(self) -> list[PhaseResult]:
        """
        Run audit phases according to configuration.

        Returns:
            List of PhaseResult for each executed phase
        """
        if self.config.simulate:
            return self._run_simulated()
        elif self.config.branch_mode:
            return self._run_branched()
        else:
            return self._run_normal()

    def _run_simulated(self) -> list[PhaseResult]:
        """Run in simulation mode with automatic rollback."""
        self.simulation_ctx = begin_simulation(
            self.config.root,
            self.config.audit_id,
            self.storage,
        )
        try:
            results = self._execute_phases()
            return results
        finally:
            # Always rollback after simulation
            if self.simulation_ctx:
                rollback_simulation(self.simulation_ctx)
                self.simulation_ctx = None

    def _run_normal(self) -> list[PhaseResult]:
        """Run in normal mode - changes are permanent."""
        return self._execute_phases()

    def _run_branched(self) -> list[PhaseResult]:
        """Run in branch-per-phase mode."""
        self.branch_ctx = begin_branch_mode(
            self.config.root,
            self.config.audit_id,
            self.config.audit_slug,
            storage=self.storage,
        )

        results: list[PhaseResult] = []
        phases_to_run = self._get_phases_to_run()

        for phase_num in phases_to_run:
            # Create branch for this phase
            phase_slug = self._get_phase_slug(phase_num)
            create_phase_branch(self.branch_ctx, phase_num, phase_slug)

            # Execute the phase
            result = self._execute_single_phase(phase_num)
            results.append(result)

            # Commit if successful
            if result.success:
                commit_phase(self.branch_ctx, phase_num)
            else:
                if self.config.fail_fast:
                    break

        self._results = results
        return results

    def _execute_phases(self) -> list[PhaseResult]:
        """Execute phases and return results."""
        results: list[PhaseResult] = []
        phases_to_run = self._get_phases_to_run()

        for phase_num in phases_to_run:
            result = self._execute_single_phase(phase_num)
            results.append(result)

            if not result.success and self.config.fail_fast:
                break

        self._results = results
        return results

    def _get_phases_to_run(self) -> list[int]:
        """Get list of phase numbers to execute."""
        if self.config.phases:
            return self.config.phases
        # In real usage, this would parse CONTEXT.md to find incomplete phases
        return []

    def _execute_single_phase(self, phase_num: int) -> PhaseResult:
        """
        Execute a single phase.

        This is a placeholder - in real usage, this would:
        1. Read phase file from .audit/phases/{NN}-*.md
        2. Execute instructions
        3. Run verification
        4. Track file changes if in simulation mode
        """
        import time

        start = time.time()

        # Placeholder implementation
        result = PhaseResult(
            phase_num=phase_num,
            description=f"Phase {phase_num}",
            success=True,
            duration=time.time() - start,
        )

        return result

    def _get_phase_slug(self, phase_num: int) -> str:
        """Get slug for a phase number."""
        # In real usage, this would parse the phase filename
        return f"phase-{phase_num:02d}"

    def track_file(self, path: Path, change_type: str) -> None:
        """
        Track a file change (for simulation mode).

        Args:
            path: Path to the changed file
            change_type: One of "created", "modified", "deleted"
        """
        if self.simulation_ctx:
            track_file_change(self.simulation_ctx, path, change_type)

    def get_simulation_summary(self) -> str | None:
        """Get summary of simulation changes."""
        if not self.simulation_ctx:
            return None

        parts = []
        if self.simulation_ctx.created_files:
            parts.append(f"+{len(self.simulation_ctx.created_files)} created")
        if self.simulation_ctx.modified_files:
            parts.append(f"~{len(self.simulation_ctx.modified_files)} modified")
        if self.simulation_ctx.deleted_files:
            parts.append(f"-{len(self.simulation_ctx.deleted_files)} deleted")

        return ", ".join(parts) if parts else "No changes"

    def commit_simulation_changes(self) -> bool:
        """
        Keep simulation changes instead of rolling back.

        Call this if all phases passed and user wants to apply changes.
        """
        if self.simulation_ctx:
            return commit_simulation(self.simulation_ctx)
        return False


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------


def run_audit(
    root: Path,
    audit_id: str,
    simulate: bool = False,
    branch_mode: bool = False,
    phases: list[int] | None = None,
    storage: PhaserStorage | None = None,
    emitter: EventEmitter | None = None,
) -> list[PhaseResult]:
    """
    Convenience function to run an audit.

    Args:
        root: Project root directory
        audit_id: Audit identifier
        simulate: Run in simulation mode
        branch_mode: Run in branch-per-phase mode
        phases: Specific phases to run (None = all)
        storage: Optional storage instance
        emitter: Optional event emitter

    Returns:
        List of PhaseResult
    """
    config = AuditRunConfig(
        root=root,
        audit_id=audit_id,
        simulate=simulate,
        branch_mode=branch_mode,
        phases=phases,
    )

    runner = AuditRunner(config, storage, emitter)
    return runner.run()


def simulate_phases(
    root: Path,
    audit_id: str,
    phases: list[int] | None = None,
    storage: PhaserStorage | None = None,
) -> tuple[list[PhaseResult], str]:
    """
    Simulate audit phases and return results with diff summary.

    Args:
        root: Project root directory
        audit_id: Audit identifier
        phases: Specific phases to run (None = all)
        storage: Optional storage instance

    Returns:
        Tuple of (results, diff_summary)
    """
    config = AuditRunConfig(
        root=root,
        audit_id=audit_id,
        simulate=True,
        phases=phases,
    )

    runner = AuditRunner(config, storage)
    results = runner.run()
    summary = runner.get_simulation_summary() or "No changes"

    return results, summary
