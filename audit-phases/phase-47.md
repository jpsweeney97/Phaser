## Phase 47: Tests and Documentation

### Context

All functionality is implemented. We need comprehensive tests and updated documentation.

### Goal

Create test suite for negotiate module and update CHANGELOG.md.

### Files

**Create: `tests/test_negotiate.py`**

```python
"""Tests for Phase Negotiation system."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from tools.negotiate import (
    OpType,
    FileChange,
    Phase,
    NegotiationOp,
    NegotiationState,
    NegotiationError,
    now_iso,
    parse_phase_header,
    parse_audit_file,
    compute_file_hash,
    init_negotiation,
    save_negotiation_state,
    load_negotiation_state,
    validate_phase_exists,
    validate_position,
    validate_split,
    validate_merge,
    check_consecutive,
    op_split,
    op_merge,
    op_reorder,
    op_skip,
    op_unskip,
    op_modify,
    op_reset,
    format_phase_list,
    format_phase_detail,
    format_diff,
    generate_negotiated_audit,
    MODIFIABLE_FIELDS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_audit_content():
    """Sample audit markdown content."""
    return """# Sample Audit

## Phase 1: Setup Project

### Context
Initial project setup.

### Goal
Create project structure.

### Files

**Create: `src/main.py`**

**Create: `requirements.txt`**

### Plan
- Create directories
- Add files

### Acceptance Criteria
- [ ] Project structure exists
- [ ] Files created

---

## Phase 2: Add Features

### Context
Adding core features.

### Goal
Implement main functionality.

### Files

**Modify: `src/main.py`**

**Create: `src/utils.py`**

**Create: `tests/test_main.py`**

### Plan
- Implement features
- Add tests

### Acceptance Criteria
- [ ] Features work
- [ ] Tests pass

---

## Phase 3: Documentation

### Context
Final documentation.

### Goal
Write docs.

### Files

**Create: `README.md`**

### Plan
- Write README

### Acceptance Criteria
- [ ] README complete
"""


@pytest.fixture
def sample_audit_file(sample_audit_content, tmp_path):
    """Create a temporary audit file."""
    audit_path = tmp_path / "audit.md"
    audit_path.write_text(sample_audit_content)
    return str(audit_path)


@pytest.fixture
def sample_state(sample_audit_file):
    """Create a sample negotiation state."""
    return init_negotiation(sample_audit_file)


# ============================================================================
# Test OpType Enum
# ============================================================================

class TestOpType:
    def test_values(self):
        assert OpType.SPLIT.value == "split"
        assert OpType.MERGE.value == "merge"
        assert OpType.REORDER.value == "reorder"
        assert OpType.SKIP.value == "skip"
        assert OpType.UNSKIP.value == "unskip"
        assert OpType.MODIFY.value == "modify"
        assert OpType.RESET.value == "reset"

    def test_from_string(self):
        assert OpType("split") == OpType.SPLIT
        assert OpType("merge") == OpType.MERGE


# ============================================================================
# Test FileChange
# ============================================================================

class TestFileChange:
    def test_to_dict(self):
        fc = FileChange("src/main.py", "create", "Main file")
        d = fc.to_dict()
        assert d["path"] == "src/main.py"
        assert d["action"] == "create"
        assert d["description"] == "Main file"

    def test_from_dict(self):
        d = {"path": "test.py", "action": "modify", "description": ""}
        fc = FileChange.from_dict(d)
        assert fc.path == "test.py"
        assert fc.action == "modify"


# ============================================================================
# Test Phase
# ============================================================================

class TestPhase:
    def test_is_derived_false_by_default(self):
        p = Phase("p1", 1, "Test")
        assert p.is_derived is False

    def test_is_derived_true_if_split(self):
        p = Phase("p1a", 1, "Test", split_from="p1")
        assert p.is_derived is True

    def test_is_derived_true_if_merged(self):
        p = Phase("p1", 1, "Test", merged_from=["p2", "p3"])
        assert p.is_derived is True

    def test_file_count(self):
        p = Phase("p1", 1, "Test", files=[
            FileChange("a.py", "create"),
            FileChange("b.py", "modify"),
        ])
        assert p.file_count == 2

    def test_to_dict_from_dict_roundtrip(self):
        p = Phase(
            id="p1",
            number=1,
            title="Test Phase",
            context="Context here",
            goal="Goal here",
            files=[FileChange("test.py", "create")],
            plan=["Step 1", "Step 2"],
            acceptance_criteria=["Criterion 1"],
        )
        d = p.to_dict()
        p2 = Phase.from_dict(d)
        assert p2.id == p.id
        assert p2.title == p.title
        assert len(p2.files) == 1
        assert p2.plan == p.plan


# ============================================================================
# Test NegotiationOp
# ============================================================================

class TestNegotiationOp:
    def test_to_dict(self):
        op = NegotiationOp(
            op_type=OpType.SKIP,
            timestamp="2025-01-01T00:00:00Z",
            target_ids=["phase-1"],
            description="Skipped phase 1"
        )
        d = op.to_dict()
        assert d["op_type"] == "skip"
        assert d["target_ids"] == ["phase-1"]

    def test_from_dict(self):
        d = {
            "op_type": "merge",
            "timestamp": "2025-01-01T00:00:00Z",
            "target_ids": ["phase-1", "phase-2"],
            "params": {"merged_id": "phase-1"},
            "description": "Merged"
        }
        op = NegotiationOp.from_dict(d)
        assert op.op_type == OpType.MERGE
        assert len(op.target_ids) == 2


# ============================================================================
# Test NegotiationState
# ============================================================================

class TestNegotiationState:
    def test_phase_count(self, sample_state):
        assert sample_state.phase_count == 3

    def test_active_count(self, sample_state):
        assert sample_state.active_count == 3
        sample_state.skipped_ids.add("phase-1")
        assert sample_state.active_count == 2

    def test_has_changes_false_initially(self, sample_state):
        assert sample_state.has_changes is False

    def test_has_changes_true_after_skip(self, sample_state):
        sample_state.skipped_ids.add("phase-1")
        assert sample_state.has_changes is True

    def test_get_phase(self, sample_state):
        p = sample_state.get_phase("phase-2")
        assert p is not None
        assert p.title == "Add Features"

    def test_get_phase_by_number(self, sample_state):
        p = sample_state.get_phase_by_number(3)
        assert p is not None
        assert p.title == "Documentation"


# ============================================================================
# Test Parsing
# ============================================================================

class TestParsing:
    def test_parse_phase_header_valid(self):
        result = parse_phase_header("## Phase 42: Implement Feature")
        assert result == (42, "Implement Feature")

    def test_parse_phase_header_triple_hash(self):
        result = parse_phase_header("### Phase 1: Setup")
        assert result == (1, "Setup")

    def test_parse_phase_header_invalid(self):
        assert parse_phase_header("# Not a phase") is None
        assert parse_phase_header("Regular text") is None

    def test_parse_audit_file(self, sample_audit_file):
        phases = parse_audit_file(sample_audit_file)
        assert len(phases) == 3
        assert phases[0].title == "Setup Project"
        assert phases[1].title == "Add Features"
        assert phases[2].title == "Documentation"

    def test_parse_audit_file_extracts_files(self, sample_audit_file):
        phases = parse_audit_file(sample_audit_file)
        # Phase 1 has 2 files, Phase 2 has 3 files, Phase 3 has 1 file
        assert len(phases[0].files) == 2
        assert len(phases[1].files) == 3
        assert len(phases[2].files) == 1
        assert any(f.path == "src/main.py" for f in phases[0].files)

    def test_parse_audit_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_audit_file("/nonexistent/path.md")


# ============================================================================
# Test Validation
# ============================================================================

class TestValidation:
    def test_validate_phase_exists_found(self, sample_state):
        p = validate_phase_exists(sample_state, "phase-1")
        assert p.number == 1

    def test_validate_phase_exists_not_found(self, sample_state):
        with pytest.raises(NegotiationError):
            validate_phase_exists(sample_state, "phase-99")

    def test_validate_position_valid(self, sample_state):
        validate_position(sample_state, 1)
        validate_position(sample_state, 3)

    def test_validate_position_invalid(self, sample_state):
        with pytest.raises(NegotiationError):
            validate_position(sample_state, 0)
        with pytest.raises(NegotiationError):
            validate_position(sample_state, 10)

    def test_validate_split_valid(self, sample_state):
        phase = sample_state.get_phase("phase-2")
        validate_split(phase)  # Has 3 files

    def test_validate_split_invalid(self, sample_state):
        phase = sample_state.get_phase("phase-3")  # Has 1 file
        with pytest.raises(NegotiationError):
            validate_split(phase)

    def test_validate_merge_valid(self, sample_state):
        phases = validate_merge(sample_state, ["phase-1", "phase-2"])
        assert len(phases) == 2

    def test_validate_merge_too_few(self, sample_state):
        with pytest.raises(NegotiationError):
            validate_merge(sample_state, ["phase-1"])

    def test_check_consecutive_true(self, sample_state):
        phases = [sample_state.get_phase("phase-1"), sample_state.get_phase("phase-2")]
        assert check_consecutive(phases) is True

    def test_check_consecutive_false(self, sample_state):
        phases = [sample_state.get_phase("phase-1"), sample_state.get_phase("phase-3")]
        assert check_consecutive(phases) is False


# ============================================================================
# Test Operations
# ============================================================================

class TestOperations:
    def test_op_skip(self, sample_state):
        op_skip(sample_state, "phase-1")
        assert "phase-1" in sample_state.skipped_ids
        assert sample_state.operation_count == 1

    def test_op_skip_already_skipped(self, sample_state):
        op_skip(sample_state, "phase-1")
        with pytest.raises(NegotiationError):
            op_skip(sample_state, "phase-1")

    def test_op_unskip(self, sample_state):
        op_skip(sample_state, "phase-1")
        op_unskip(sample_state, "phase-1")
        assert "phase-1" not in sample_state.skipped_ids

    def test_op_unskip_not_skipped(self, sample_state):
        with pytest.raises(NegotiationError):
            op_unskip(sample_state, "phase-1")

    def test_op_reorder(self, sample_state):
        op_reorder(sample_state, "phase-1", 3)
        # Phase 1 should now be at position 3
        assert sample_state.current_phases[2].title == "Setup Project"

    def test_op_modify_title(self, sample_state):
        op_modify(sample_state, "phase-1", "title", "New Title")
        p = sample_state.get_phase("phase-1")
        assert p.title == "New Title"

    def test_op_modify_invalid_field(self, sample_state):
        with pytest.raises(NegotiationError):
            op_modify(sample_state, "phase-1", "invalid_field", "value")

    def test_op_merge(self, sample_state):
        merged = op_merge(sample_state, ["phase-1", "phase-2"], force=True)
        assert sample_state.phase_count == 2  # 3 - 2 + 1
        assert len(merged.merged_from) == 2

    def test_op_split(self, sample_state):
        # Phase 2 has 3 files
        new_phases = op_split(sample_state, "phase-2", split_at=[1, 2])
        assert len(new_phases) == 3
        assert sample_state.phase_count == 5  # 3 - 1 + 3
        # Verify split tracking
        assert all(p.split_from == "phase-2" for p in new_phases)

    def test_op_split_preserves_derived_ids(self, sample_state):
        """Verify that split phase IDs are not overwritten by renumbering."""
        new_phases = op_split(sample_state, "phase-2", split_at=[1, 2])
        # IDs should have suffixes like phase-2a, phase-2b, phase-2c
        ids = [p.id for p in new_phases]
        assert "phase-2a" in ids
        assert "phase-2b" in ids
        assert "phase-2c" in ids

    def test_op_reset_all(self, sample_state):
        op_skip(sample_state, "phase-1")
        op_modify(sample_state, "phase-2", "title", "Changed")
        assert sample_state.operation_count == 2
        op_reset(sample_state, "all")
        assert len(sample_state.skipped_ids) == 0
        assert sample_state.operation_count == 0  # History cleared
        p2 = sample_state.get_phase("phase-2")
        assert p2.title == "Add Features"

    def test_op_reset_single_phase(self, sample_state):
        op_modify(sample_state, "phase-1", "title", "Changed")
        op_reset(sample_state, "phase-1")
        p1 = sample_state.get_phase("phase-1")
        assert p1.title == "Setup Project"
        # Single phase reset should record operation
        assert sample_state.operation_count == 2


# ============================================================================
# Test Formatting
# ============================================================================

class TestFormatting:
    def test_format_phase_list(self, sample_state):
        output = format_phase_list(sample_state)
        assert "3 active" in output
        assert "Setup Project" in output
        assert "Add Features" in output

    def test_format_phase_list_with_skip(self, sample_state):
        sample_state.skipped_ids.add("phase-1")
        output = format_phase_list(sample_state)
        assert "[SKIP]" in output

    def test_format_phase_detail(self, sample_state):
        phase = sample_state.get_phase("phase-1")
        output = format_phase_detail(phase, False)
        assert "Phase 1" in output
        assert "Setup Project" in output

    def test_format_diff(self, sample_state):
        sample_state.skipped_ids.add("phase-1")
        output = format_diff(sample_state)
        assert "Skipped" in output
        assert "phase-1" in output

    def test_generate_negotiated_audit(self, sample_state):
        output = generate_negotiated_audit(sample_state)
        assert "# Negotiated Audit" in output
        assert "## Phase 1" in output
        assert "## Phase 2" in output

    def test_generate_negotiated_audit_excludes_skipped(self, sample_state):
        op_skip(sample_state, "phase-1")
        output = generate_negotiated_audit(sample_state, include_skipped=False)
        assert "Setup Project" not in output  # Phase 1 excluded


# ============================================================================
# Test Persistence
# ============================================================================

class TestPersistence:
    def test_save_and_load_state(self, sample_state, tmp_path):
        # Make some changes
        op_skip(sample_state, "phase-1")

        # Save
        state_path = str(tmp_path / "state.yaml")
        save_negotiation_state(sample_state, state_path)

        # Load
        loaded = load_negotiation_state(state_path)
        assert loaded.phase_count == sample_state.phase_count
        assert "phase-1" in loaded.skipped_ids
        assert loaded.operation_count == 1

    def test_save_to_filename_only(self, sample_state, tmp_path):
        """Test saving when path has no directory component."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            save_negotiation_state(sample_state, "state.yaml")
            assert os.path.exists("state.yaml")
        finally:
            os.chdir(original_cwd)

    def test_compute_file_hash(self, sample_audit_file):
        hash1 = compute_file_hash(sample_audit_file)
        hash2 = compute_file_hash(sample_audit_file)
        assert hash1 == hash2
        assert len(hash1) == 16


# ============================================================================
# Test CLI (basic)
# ============================================================================

class TestCLI:
    def test_cli_help(self):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'negotiate' in result.output.lower() or 'phase' in result.output.lower()

    def test_preview_command(self, sample_audit_file):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['preview', sample_audit_file])
        assert result.exit_code == 0
        assert "3 phases" in result.output

    def test_status_no_session(self, sample_audit_file):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['status', sample_audit_file])
        assert result.exit_code == 0
        assert "No negotiation session" in result.output

    def test_skip_command(self, sample_audit_file, tmp_path):
        from click.testing import CliRunner
        from tools.negotiate import cli

        runner = CliRunner()
        output_path = str(tmp_path / "output.md")
        result = runner.invoke(cli, ['skip', sample_audit_file, '--phases', '1,3', '--output', output_path])
        assert result.exit_code == 0
        assert "Skipped phase 1" in result.output
        assert "Skipped phase 3" in result.output
        assert os.path.exists(output_path)
```

**Modify: `CHANGELOG.md`**

Add to the existing [1.5.0] section:

```markdown
## [1.5.0] - 2025-12-05

### Added

- **Reverse Audit** (`phaser reverse`)

  - `phaser reverse generate <commit-range>` — Generate audit document from git diff
  - `phaser reverse preview <commit-range>` — Preview inferred phases
  - `phaser reverse commits <commit-range>` — List commits with details
  - `phaser reverse diff <commit-range>` — Show full diff
  - Multiple grouping strategies: commits, directories, filetypes, semantic
  - Output formats: markdown, yaml, json
  - Automatic phase title and category inference
  - Support for conventional commit parsing

- **Phase Negotiation** (`phaser negotiate`)
  - `phaser negotiate <audit-file>` — Interactive phase customization
  - `phaser negotiate preview <audit-file>` — Preview phases in audit
  - `phaser negotiate skip <audit-file> --phases N,M` — Quick skip phases
  - `phaser negotiate apply <audit-file> --ops <file.yaml>` — Batch apply operations
  - `phaser negotiate export <audit-file>` — Export negotiated audit
  - `phaser negotiate status <audit-file>` — Show session status
  - Operations: split, merge, reorder, skip, modify, reset
  - Session persistence with resume capability
  - Non-consecutive merge warning
  - Tracks operation history for review
  - Produces clean negotiated audit documents
```

### Plan

1. Create comprehensive test file covering all modules
2. Update CHANGELOG.md with Phase Negotiation feature
3. Verify test count meets target

### Verification

```bash
python -m pytest tests/test_negotiate.py -v
python -m pytest tests/ -q | tail -5  # Check total count
grep -A 20 "Phase Negotiation" CHANGELOG.md
```

### Acceptance Criteria

- [ ] tests/test_negotiate.py created with ~35 tests
- [ ] All tests pass
- [ ] CHANGELOG.md updated with Phase Negotiation feature
- [ ] Test coverage includes: OpType, FileChange, Phase, NegotiationOp, NegotiationState
- [ ] Test coverage includes: parsing, validation, all operations
- [ ] Test coverage includes: formatting, persistence, CLI commands
- [ ] Total test count 345+ (310 + 35)

### Rollback

```bash
rm tests/test_negotiate.py
git checkout HEAD -- CHANGELOG.md
```

### Completion

Phase 47 complete when all tests pass and documentation is updated.

---

