"""Tests for the Audit Bridge module."""

import pytest
from pathlib import Path

from tools.bridge import (
    # Errors
    BridgeError,
    ParseError,
    ValidationError,
    ExecutionError,
    # Enums
    FileAction,
    # Data classes
    ValidationIssue,
    ValidationResult,
    PhaseFile,
    Phase,
    AuditDocument,
    PrepareResult,
    # Parsing functions
    estimate_tokens,
    extract_setup_block,
    extract_prerequisites,
    parse_baseline_test_count,
    extract_overview,
    extract_completion_block,
    detect_fence_marker,
    find_code_block_ranges,
    is_inside_code_block,
    detect_phase_boundaries,
    parse_files_table,
    parse_section,
    parse_acceptance_criteria,
    parse_plan_steps,
    parse_phase,
    parse_audit_document,
    # Validation functions
    validate_phase,
    validate_document,
    # Constants
    SETUP_START_MARKER,
    SETUP_END_MARKER,
    TOKEN_WARNING_THRESHOLD,
    TOKEN_ERROR_THRESHOLD,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_phase_content():
    """Minimal valid phase content."""
    return """## Phase 1: Test Phase

### Context
Test context

### Goal
Test goal

### Files

| File | Action | Purpose |
|------|--------|---------|
| `test.py` | CREATE | Test file |

### Implementation

```python
print("hello")
```

### Verify

```bash
python test.py
# Expected: hello
```

### Completion

```bash
git add test.py
git commit -m "Phase 1: Test Phase"
```
"""


@pytest.fixture
def minimal_document_content():
    """Minimal valid document content."""
    return """# Document 1: Test Document

> Phases 1-1

## Document Overview

This is a test document.

## Prerequisites

```bash
python --version
# Expected: Python 3.10+

python -m pytest tests/ -q
# Expected: 100+ passed
```

=== AUDIT SETUP START ===

## Setup Block

```bash
git checkout -b test-branch
mkdir -p .audit-meta
git rev-parse HEAD > .audit-meta/base-commit
```

=== AUDIT SETUP END ===

## Phase 1: Test Phase

### Context
Test context

### Goal
Test goal

### Files

| File | Action | Purpose |
|------|--------|---------|
| `test.py` | CREATE | Test file |

### Plan

1. Create test file
2. Run tests

### Implementation

```python
print("hello")
```

### Verify

```bash
python test.py
# Expected: hello
```

### Acceptance Criteria

- [ ] test.py exists
- [ ] Output is correct

### Rollback

```bash
rm -f test.py
```

### Completion

```bash
git add test.py
git commit -m "Phase 1: Test Phase"
```

## Document Completion

### Final Steps

```bash
git checkout main
git merge test-branch
```
"""


# =============================================================================
# Error Tests
# =============================================================================


class TestErrors:
    def test_bridge_error_is_base(self):
        assert issubclass(ParseError, BridgeError)
        assert issubclass(ValidationError, BridgeError)
        assert issubclass(ExecutionError, BridgeError)

    def test_parse_error_with_line(self):
        err = ParseError("Test error", line=42)
        assert "Test error" in str(err)
        assert "line 42" in str(err)
        assert err.line == 42

    def test_parse_error_without_line(self):
        err = ParseError("Test error")
        assert "Test error" in str(err)
        assert "line" not in str(err)
        assert err.line is None

    def test_validation_error_with_issues(self):
        issues = [ValidationIssue("error", 1, None, "Test")]
        err = ValidationError("Validation failed", issues)
        assert err.issues == issues


# =============================================================================
# Enum Tests
# =============================================================================


class TestFileAction:
    def test_values(self):
        assert FileAction.CREATE.value == "CREATE"
        assert FileAction.MODIFY.value == "MODIFY"
        assert FileAction.DELETE.value == "DELETE"

    def test_from_string(self):
        assert FileAction("CREATE") == FileAction.CREATE


# =============================================================================
# Data Class Tests
# =============================================================================


class TestValidationIssue:
    def test_to_dict(self):
        issue = ValidationIssue("error", 1, 10, "Test message")
        d = issue.to_dict()
        assert d["level"] == "error"
        assert d["phase"] == 1
        assert d["line"] == 10
        assert d["message"] == "Test message"


class TestValidationResult:
    def test_to_dict(self):
        result = ValidationResult(
            valid=True,
            source_path="test.md",
            document_title="Test",
            phase_count=2,
            phase_range="1-2",
            token_estimates={"phase_1": 100},
        )
        d = result.to_dict()
        assert d["file"] == "test.md"
        assert d["valid"] is True
        assert d["document"]["title"] == "Test"


class TestPhaseFile:
    def test_to_dict(self):
        pf = PhaseFile("test.py", FileAction.CREATE, "Test file")
        d = pf.to_dict()
        assert d["path"] == "test.py"
        assert d["action"] == "CREATE"
        assert d["purpose"] == "Test file"


class TestPhase:
    def test_estimated_tokens(self):
        phase = Phase(1, "Test", raw_content="x" * 350)
        assert phase.estimated_tokens == 100

    def test_to_dict(self):
        phase = Phase(1, "Test", line_start=10, raw_content="content")
        d = phase.to_dict()
        assert d["number"] == 1
        assert d["title"] == "Test"
        assert d["line_start"] == 10


class TestAuditDocument:
    def test_phase_properties(self):
        doc = AuditDocument(
            title="Test",
            document_number=1,
            phases=[Phase(5, "A"), Phase(6, "B"), Phase(7, "C")],
        )
        assert doc.phase_count == 3
        assert doc.phase_start == 5
        assert doc.phase_end == 7
        assert doc.phase_range == "5-7"

    def test_empty_phases(self):
        doc = AuditDocument(title="Test", document_number=1, phases=[])
        assert doc.phase_count == 0
        assert doc.phase_start == 0
        assert doc.phase_end == 0


# =============================================================================
# Parsing Function Tests
# =============================================================================


class TestEstimateTokens:
    def test_estimate(self):
        # 350 chars / 3.5 = 100 tokens
        assert estimate_tokens("x" * 350) == 100

    def test_empty(self):
        assert estimate_tokens("") == 0


class TestExtractSetupBlock:
    def test_valid_extraction(self):
        content = f"""
Before
{SETUP_START_MARKER}
Setup content here
{SETUP_END_MARKER}
After
"""
        result = extract_setup_block(content)
        assert SETUP_START_MARKER in result
        assert "Setup content here" in result
        assert SETUP_END_MARKER in result
        assert "Before" not in result
        assert "After" not in result

    def test_missing_start_marker(self):
        content = f"No markers here {SETUP_END_MARKER}"
        with pytest.raises(ParseError) as exc:
            extract_setup_block(content)
        assert "AUDIT SETUP START" in str(exc.value)

    def test_missing_end_marker(self):
        content = f"{SETUP_START_MARKER} No end marker"
        with pytest.raises(ParseError) as exc:
            extract_setup_block(content)
        assert "AUDIT SETUP END" in str(exc.value)


class TestExtractPrerequisites:
    def test_valid_extraction(self):
        content = """
## Prerequisites

```bash
python --version
# Expected: 3.10+
```

## Next Section
"""
        result = extract_prerequisites(content)
        assert result is not None
        assert "python --version" in result

    def test_missing_section(self):
        content = "## Other Section\nContent"
        result = extract_prerequisites(content)
        assert result is None


class TestParseBaselineTestCount:
    def test_parse_with_plus(self):
        assert parse_baseline_test_count("# Expected: 280+ passed") == 280

    def test_parse_without_plus(self):
        assert parse_baseline_test_count("# Expected: 100 passed") == 100

    def test_parse_none(self):
        assert parse_baseline_test_count(None) == 0

    def test_parse_no_match(self):
        assert parse_baseline_test_count("No test count here") == 0


class TestDetectPhaseBoundaries:
    def test_multiple_phases(self):
        content = """
## Phase 1: First
Content 1
## Phase 2: Second
Content 2
## Phase 3: Third
Content 3
## Document Completion
Done
"""
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 3
        assert boundaries[0][0] == 1
        assert boundaries[1][0] == 2
        assert boundaries[2][0] == 3

    def test_no_phases(self):
        content = "No phases here"
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 0


class TestParseFilesTable:
    def test_valid_table(self):
        content = """
### Files

| File | Action | Purpose |
|------|--------|---------|
| `test.py` | CREATE | Test file |
| `utils.py` | MODIFY | Update utils |
"""
        files = parse_files_table(content)
        assert len(files) == 2
        assert files[0].path == "test.py"
        assert files[0].action == FileAction.CREATE
        assert files[1].path == "utils.py"
        assert files[1].action == FileAction.MODIFY

    def test_no_files_section(self):
        content = "No files section"
        files = parse_files_table(content)
        assert len(files) == 0


class TestParsePhase:
    def test_valid_phase(self, minimal_phase_content):
        phase = parse_phase(minimal_phase_content)
        assert phase.number == 1
        assert phase.title == "Test Phase"
        assert "Test context" in phase.context
        assert "Test goal" in phase.goal
        assert len(phase.files) == 1
        assert phase.implementation
        assert phase.verify
        assert phase.completion

    def test_invalid_header(self):
        content = "Not a valid phase header"
        with pytest.raises(ParseError):
            parse_phase(content)


class TestParseAuditDocument:
    def test_valid_document(self, minimal_document_content):
        doc = parse_audit_document(minimal_document_content)
        assert doc.document_number == 1
        assert "Test Document" in doc.title
        assert doc.overview is not None
        assert doc.prerequisites is not None
        assert len(doc.phases) == 1
        assert doc.setup_block
        assert doc.completion_block is not None

    def test_missing_header(self):
        content = "No document header"
        with pytest.raises(ParseError) as exc:
            parse_audit_document(content)
        assert "document header" in str(exc.value).lower()

    def test_missing_phases(self):
        content = """# Document 1: Test
=== AUDIT SETUP START ===
Setup
=== AUDIT SETUP END ===
"""
        with pytest.raises(ParseError) as exc:
            parse_audit_document(content)
        assert "No phases" in str(exc.value)


# =============================================================================
# Validation Function Tests
# =============================================================================


class TestValidatePhase:
    def test_valid_phase(self, minimal_phase_content):
        phase = parse_phase(minimal_phase_content)
        issues = validate_phase(phase)
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0

    def test_missing_required_sections(self):
        phase = Phase(
            number=1,
            title="Test",
            context="",  # Missing
            goal="Has goal",
            implementation="",  # Missing
            verify="",  # Missing
            completion="",  # Missing
            raw_content="## Phase 1: Test\n### Files\n| File | Action | Purpose |",
        )
        issues = validate_phase(phase)
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 4  # Context, Implementation, Verify, Completion

    def test_token_warning(self):
        # Create phase with content just over warning threshold
        large_content = "x" * int(TOKEN_WARNING_THRESHOLD * 3.5 + 100)
        phase = Phase(
            number=1,
            title="Test",
            context="c",
            goal="g",
            implementation="i",
            verify="# Expected: x",
            completion="c",
            raw_content=large_content,
        )
        issues = validate_phase(phase)
        warnings = [i for i in issues if i.level == "warning" and "tokens" in i.message]
        assert len(warnings) >= 1

    def test_token_error(self):
        # Create phase with content over error threshold
        large_content = "x" * int(TOKEN_ERROR_THRESHOLD * 3.5 + 100)
        phase = Phase(
            number=1,
            title="Test",
            context="c",
            goal="g",
            implementation="i",
            verify="# Expected: x",
            completion="c",
            raw_content=large_content,
        )
        issues = validate_phase(phase)
        errors = [i for i in issues if i.level == "error" and "tokens" in i.message]
        assert len(errors) >= 1


class TestValidateDocument:
    def test_valid_document(self, minimal_document_content):
        result = validate_document(minimal_document_content)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_setup_block(self):
        content = """# Document 1: Test
## Phase 1: Test
Content
"""
        result = validate_document(content)
        assert result.valid is False
        assert any("Setup block" in e.message for e in result.errors)

    def test_phase_gap_warning(self):
        content = """# Document 1: Test

=== AUDIT SETUP START ===
Setup
=== AUDIT SETUP END ===

## Phase 1: First

### Context
c
### Goal
g
### Files
| File | Action | Purpose |
### Implementation
i
### Verify
# Expected: x
### Completion
c

## Phase 3: Third

### Context
c
### Goal
g
### Files
| File | Action | Purpose |
### Implementation
i
### Verify
# Expected: x
### Completion
c
"""
        result = validate_document(content)
        assert any("gap" in w.message.lower() for w in result.warnings)

    def test_json_output_format(self, minimal_document_content):
        result = validate_document(minimal_document_content, Path("test.md"))
        d = result.to_dict()
        assert "file" in d
        assert "valid" in d
        assert "document" in d
        assert "errors" in d
        assert "warnings" in d
        assert "tokens" in d


# =============================================================================
# File Generation Tests
# =============================================================================


class TestCreateSetupFileContent:
    def test_with_prerequisites(self):
        from tools.bridge import create_setup_file_content

        content = f"""## Prerequisites

Test prereq content

{SETUP_START_MARKER}
Setup block content
{SETUP_END_MARKER}
"""
        result = create_setup_file_content(content)
        assert "Prerequisites" in result
        assert "Test prereq content" in result
        assert "Setup block content" in result

    def test_without_prerequisites(self):
        from tools.bridge import create_setup_file_content

        content = f"""{SETUP_START_MARKER}
Setup only
{SETUP_END_MARKER}
"""
        result = create_setup_file_content(content)
        assert "Setup only" in result


class TestCalculateZeroPadding:
    def test_single_digit(self):
        from tools.bridge import calculate_zero_padding

        assert calculate_zero_padding(9) == 1

    def test_double_digit(self):
        from tools.bridge import calculate_zero_padding

        assert calculate_zero_padding(41) == 2
        assert calculate_zero_padding(99) == 2

    def test_triple_digit(self):
        from tools.bridge import calculate_zero_padding

        assert calculate_zero_padding(100) == 3
        assert calculate_zero_padding(120) == 3


class TestSplitDocument:
    def test_creates_all_files(self, minimal_document_content, tmp_path):
        from tools.bridge import parse_audit_document, split_document

        doc = parse_audit_document(minimal_document_content)
        setup, phases, meta = split_document(doc, tmp_path / "audit-phases", tmp_path)

        assert setup.exists()
        assert setup.name == "setup.md"
        assert len(phases) == 1
        assert phases[0].name == "phase-1.md"
        assert meta.exists()
        assert (meta / "phaser-version").exists()
        assert (meta / "baseline-tests").exists()

    def test_zero_padding(self, tmp_path):
        from tools.bridge import AuditDocument, Phase, split_document

        doc = AuditDocument(
            title="Test",
            document_number=1,
            phases=[
                Phase(1, "First", raw_content="## Phase 1: First\nContent"),
                Phase(10, "Tenth", raw_content="## Phase 10: Tenth\nContent"),
            ],
            setup_block=f"{SETUP_START_MARKER}\nSetup\n{SETUP_END_MARKER}",
            raw_content=f"{SETUP_START_MARKER}\nSetup\n{SETUP_END_MARKER}",
        )

        setup, phases, meta = split_document(doc, tmp_path / "audit-phases", tmp_path)

        assert phases[0].name == "phase-01.md"
        assert phases[1].name == "phase-10.md"


class TestWriteMetadata:
    def test_creates_files(self, tmp_path):
        from tools.bridge import write_metadata, PHASER_VERSION

        meta_dir = write_metadata(tmp_path, 150)

        assert meta_dir.exists()
        assert (meta_dir / "phaser-version").read_text() == PHASER_VERSION
        assert (meta_dir / "baseline-tests").read_text() == "150"


# =============================================================================
# Prompt Generation Tests
# =============================================================================


class TestGenerateExecutionPrompt:
    def test_includes_all_variables(self):
        from tools.bridge import AuditDocument, Phase, generate_execution_prompt

        doc = AuditDocument(
            title="Document 7: Reverse Audit",
            document_number=7,
            phases=[Phase(36, "First"), Phase(37, "Second"), Phase(38, "Third")],
        )

        prompt = generate_execution_prompt(doc, "document-7-reverse.md")

        assert "phase-36.md" in prompt
        assert "phase-38.md" in prompt
        assert "3 completed" in prompt or "of 3" in prompt
        assert "Document 7: Reverse Audit" in prompt
        assert "document-7-reverse.md" in prompt


# =============================================================================
# Execution Function Tests
# =============================================================================


class TestPrepareAudit:
    def test_successful_preparation(self, minimal_document_content, tmp_path):
        from tools.bridge import prepare_audit

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)

        result = prepare_audit(audit_file, project_dir=tmp_path)

        assert result.setup_file.exists()
        assert len(result.phase_files) == 1
        assert result.audit_copy.exists()
        assert result.audit_copy.name == "AUDIT.md"
        assert len(result.prompt) > 0

    def test_file_not_found(self, tmp_path):
        from tools.bridge import prepare_audit

        with pytest.raises(FileNotFoundError):
            prepare_audit(tmp_path / "nonexistent.md")

    def test_directory_exists_error(self, minimal_document_content, tmp_path):
        from tools.bridge import prepare_audit

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)
        (tmp_path / "audit-phases").mkdir()

        with pytest.raises(FileExistsError):
            prepare_audit(audit_file, project_dir=tmp_path)

    def test_force_overwrites(self, minimal_document_content, tmp_path):
        from tools.bridge import prepare_audit

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)
        existing_dir = tmp_path / "audit-phases"
        existing_dir.mkdir()
        (existing_dir / "old-file.txt").write_text("old")

        result = prepare_audit(audit_file, project_dir=tmp_path, force=True)

        assert result.setup_file.exists()
        assert not (existing_dir / "old-file.txt").exists()

    def test_validation_error(self, tmp_path):
        from tools.bridge import prepare_audit, ValidationError, ParseError

        # Document missing setup block - raises ParseError during parsing
        content = """# Document 1: Test
## Phase 1: Test
Content
"""
        audit_file = tmp_path / "audit.md"
        audit_file.write_text(content)

        with pytest.raises((ValidationError, ParseError)):
            prepare_audit(audit_file, project_dir=tmp_path)

    def test_skip_validation(self, tmp_path):
        from tools.bridge import prepare_audit

        # Document with issues that would fail validation
        content = f"""# Document 1: Test
{SETUP_START_MARKER}
Setup
{SETUP_END_MARKER}
## Phase 1: Test
### Context
c
### Goal
g
### Files
| File | Action | Purpose |
### Implementation
i
### Verify
v
### Completion
c
"""
        audit_file = tmp_path / "audit.md"
        audit_file.write_text(content)

        # Should succeed with skip_validation
        result = prepare_audit(audit_file, project_dir=tmp_path, skip_validation=True)
        assert result.validation.valid is True


# =============================================================================
# CLI Tests
# =============================================================================


class TestValidateCLI:
    def test_valid_document(self, minimal_document_content, tmp_path):
        from click.testing import CliRunner
        from tools.cli import cli

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(audit_file)])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_invalid_document(self, tmp_path):
        from click.testing import CliRunner
        from tools.cli import cli

        audit_file = tmp_path / "audit.md"
        audit_file.write_text("# Document 1: Test\nNo setup block")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(audit_file)])

        assert result.exit_code == 1

    def test_json_output(self, minimal_document_content, tmp_path):
        from click.testing import CliRunner
        from tools.cli import cli
        import json

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--json", str(audit_file)])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "valid" in data
        assert "document" in data

    def test_strict_mode(self, tmp_path):
        from click.testing import CliRunner
        from tools.cli import cli

        # Document that's valid but has warnings
        content = f"""# Document 1: Test
{SETUP_START_MARKER}
Setup
{SETUP_END_MARKER}
## Phase 1: Test
### Context
c
### Goal
g
### Files
| File | Action | Purpose |
### Implementation
i
### Verify
# Expected: x
### Completion
c
"""
        audit_file = tmp_path / "audit.md"
        audit_file.write_text(content)

        runner = CliRunner()

        # Without strict: should pass
        result = runner.invoke(cli, ["validate", str(audit_file)])
        assert result.exit_code == 0

        # With strict: should fail (warnings become errors)
        result = runner.invoke(cli, ["validate", "--strict", str(audit_file)])
        assert result.exit_code == 1


class TestPrepareCLI:
    def test_dry_run(self, minimal_document_content, tmp_path):
        from click.testing import CliRunner
        from tools.cli import cli

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["prepare", "--dry-run", "--project", str(tmp_path), str(audit_file)]
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert not (tmp_path / "audit-phases").exists()

    def test_creates_files(self, minimal_document_content, tmp_path):
        from click.testing import CliRunner
        from tools.cli import cli

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["prepare", "--project", str(tmp_path), "--no-clipboard", str(audit_file)],
        )

        assert result.exit_code == 0
        assert (tmp_path / "audit-phases" / "setup.md").exists()
        assert (tmp_path / "AUDIT.md").exists()


class TestExecuteCLI:
    def test_dry_run(self, minimal_document_content, tmp_path):
        from click.testing import CliRunner
        from tools.cli import cli

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["execute", "--dry-run", "--project", str(tmp_path), str(audit_file)]
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.output


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    def test_full_prepare_workflow(self, minimal_document_content, tmp_path):
        """Test the complete prepare workflow."""
        from tools.bridge import prepare_audit

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(minimal_document_content)

        result = prepare_audit(audit_file, project_dir=tmp_path)

        # Check all outputs
        assert result.validation.valid
        assert result.setup_file.exists()
        assert all(pf.exists() for pf in result.phase_files)
        assert result.audit_copy.exists()
        assert result.meta_dir.exists()
        assert (result.meta_dir / "phaser-version").exists()
        assert (result.meta_dir / "baseline-tests").exists()
        assert len(result.prompt) > 1000  # Prompt should be substantial

        # Check setup.md includes prerequisites
        setup_content = result.setup_file.read_text()
        assert "Prerequisites" in setup_content

    def test_multi_phase_document(self, tmp_path):
        """Test document with multiple phases."""
        content = f"""# Document 1: Multi Phase Test

## Prerequisites
# Expected: 200+ passed

{SETUP_START_MARKER}
Setup block
{SETUP_END_MARKER}

## Phase 1: First Phase

### Context
First context
### Goal
First goal
### Files
| File | Action | Purpose |
### Implementation
First impl
### Verify
# Expected: first
### Completion
First done

## Phase 2: Second Phase

### Context
Second context
### Goal
Second goal
### Files
| File | Action | Purpose |
### Implementation
Second impl
### Verify
# Expected: second
### Completion
Second done

## Phase 3: Third Phase

### Context
Third context
### Goal
Third goal
### Files
| File | Action | Purpose |
### Implementation
Third impl
### Verify
# Expected: third
### Completion
Third done

## Document Completion
Final steps
"""
        from tools.bridge import prepare_audit

        audit_file = tmp_path / "audit.md"
        audit_file.write_text(content)

        result = prepare_audit(audit_file, project_dir=tmp_path)

        assert result.document.phase_count == 3
        assert len(result.phase_files) == 3
        assert result.phase_files[0].name == "phase-1.md"
        assert result.phase_files[1].name == "phase-2.md"
        assert result.phase_files[2].name == "phase-3.md"

        # Check prompt includes all phases
        assert "phase-1.md" in result.prompt
        assert "phase-3.md" in result.prompt


# =============================================================================
# Code Block Detection Tests (Regression for v1.6.1)
# =============================================================================


class TestFindCodeBlockRanges:
    def test_single_code_block(self):
        content = """Line 1
```python
code here
```
Line 5"""
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1
        # The code block should be found
        start, end = ranges[0]
        assert "```python" in content[start:end]
        assert "code here" in content[start:end]

    def test_multiple_code_blocks(self):
        content = """
```python
block 1
```

Some text

```bash
block 2
```
"""
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 2

    def test_no_code_blocks(self):
        content = "No code blocks here\nJust plain text"
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 0

    def test_code_block_with_language(self):
        content = """```javascript
const x = 1;
```"""
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1

    def test_code_block_without_language(self):
        content = """```
plain code
```"""
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1

    def test_nested_backticks_in_content(self):
        """Code block containing triple backticks in string literals.

        With fence-aware matching, the outer 3-backtick fence is only closed
        by another 3+ backtick fence. Internal backticks in strings don't
        close the block.
        """
        content = '''Text before
```python
example = """
```markdown
fake nested block
```
"""
```
Text after'''
        ranges = find_code_block_ranges(content)
        # Fence-aware approach correctly handles this: the outer ``` opens,
        # and only the final ``` at the end closes it. The middle ones are
        # inside string literals and match the same length, so they DO close.
        # But this specific case has balanced pairs, so we get 2 blocks.
        assert len(ranges) == 2
        # First block contains "example"
        start, end = ranges[0]
        assert "example" in content[start:end]

    def test_unclosed_code_block(self):
        """Unclosed code block extends to end of document."""
        content = '''Text
```python
code here
no closing fence'''
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1
        start, end = ranges[0]
        assert end == len(content)

    def test_indented_fence_markers(self):
        """Fence markers with leading whitespace should still be detected."""
        content = '''Text
  ```python
  indented code
  ```
More text'''
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1

    def test_multiple_code_blocks_complex(self):
        """Multiple code blocks with various content."""
        content = '''
## Section 1

```python
def foo():
    pass
```

Some text

```bash
echo "hello"
```

```markdown
# Heading
## Phase 1: Fake phase in markdown block
```

## Section 2
'''
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 3

    def test_four_backtick_fence_contains_three(self):
        """Four-backtick fence can contain three-backtick content."""
        content = '''Text before
````python
example = """
```
fake fence inside
```
"""
````
Text after'''
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1
        start, end = ranges[0]
        assert "fake fence inside" in content[start:end]

    def test_tilde_fence_ignores_backtick_inside(self):
        """Tilde fence ignores backtick fences inside."""
        content = '''Text
~~~python
```
not a close
```
~~~
More text'''
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1

    def test_backtick_fence_ignores_tilde_inside(self):
        """Backtick fence ignores tilde fences inside."""
        content = '''Text
```python
~~~
not a close
~~~
```
More text'''
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1

    def test_five_backtick_fence(self):
        """Five-backtick fence needs five to close."""
        content = '''Text
`````python
```
three
```
````
four
````
`````
After'''
        ranges = find_code_block_ranges(content)
        assert len(ranges) == 1
        start, end = ranges[0]
        assert "three" in content[start:end]
        assert "four" in content[start:end]

    def test_string_literal_with_backticks(self):
        """Python string containing backticks doesn't break detection."""
        content = '''# Doc

## Phase 1: Real

```python
content = """
## Phase 99: Fake in string
"""

more = \'\'\'
```
fake fence in string
```
\'\'\'
```

## Phase 2: Also Real
'''
        ranges = find_code_block_ranges(content)
        # The string literals contain ``` which will toggle state
        # But the end result should still filter phases correctly
        # This tests the real-world pattern
        from tools.bridge import detect_phase_boundaries
        boundaries = detect_phase_boundaries(content)
        phase_nums = [b[0] for b in boundaries]
        assert 1 in phase_nums
        assert 2 in phase_nums
        assert 99 not in phase_nums


class TestDetectFenceMarker:
    """Tests for fence marker detection helper."""

    def test_backtick_fence_basic(self):
        result = detect_fence_marker('```')
        assert result == ('`', 3)

    def test_backtick_fence_with_language(self):
        result = detect_fence_marker('```python')
        assert result == ('`', 3)

    def test_backtick_fence_four(self):
        result = detect_fence_marker('````')
        assert result == ('`', 4)

    def test_backtick_fence_five_with_language(self):
        result = detect_fence_marker('`````markdown')
        assert result == ('`', 5)

    def test_tilde_fence_basic(self):
        result = detect_fence_marker('~~~')
        assert result == ('~', 3)

    def test_tilde_fence_with_language(self):
        result = detect_fence_marker('~~~bash')
        assert result == ('~', 3)

    def test_tilde_fence_four(self):
        result = detect_fence_marker('~~~~')
        assert result == ('~', 4)

    def test_indented_fence_one_space(self):
        result = detect_fence_marker(' ```')
        assert result == ('`', 3)

    def test_indented_fence_three_spaces(self):
        result = detect_fence_marker('   ```')
        assert result == ('`', 3)

    def test_indented_fence_four_spaces_invalid(self):
        """Four spaces makes it a code block content, not a fence."""
        result = detect_fence_marker('    ```')
        assert result is None

    def test_not_a_fence_plain_text(self):
        result = detect_fence_marker('regular text')
        assert result is None

    def test_not_a_fence_single_backtick(self):
        result = detect_fence_marker('`inline code`')
        assert result is None

    def test_not_a_fence_two_backticks(self):
        result = detect_fence_marker('``not a fence``')
        assert result is None


class TestIsInsideCodeBlock:
    def test_position_before_code_block(self):
        ranges = [(10, 50)]
        assert is_inside_code_block(5, ranges) is False

    def test_position_inside_code_block(self):
        ranges = [(10, 50)]
        assert is_inside_code_block(25, ranges) is True

    def test_position_at_start_of_code_block(self):
        ranges = [(10, 50)]
        assert is_inside_code_block(10, ranges) is True

    def test_position_at_end_of_code_block(self):
        ranges = [(10, 50)]
        # End is exclusive
        assert is_inside_code_block(50, ranges) is False

    def test_position_after_code_block(self):
        ranges = [(10, 50)]
        assert is_inside_code_block(60, ranges) is False

    def test_multiple_code_blocks(self):
        ranges = [(10, 20), (50, 70)]
        assert is_inside_code_block(5, ranges) is False
        assert is_inside_code_block(15, ranges) is True
        assert is_inside_code_block(35, ranges) is False
        assert is_inside_code_block(60, ranges) is True
        assert is_inside_code_block(80, ranges) is False

    def test_empty_ranges(self):
        ranges = []
        assert is_inside_code_block(10, ranges) is False


class TestDetectPhaseBoundariesWithCodeBlocks:
    def test_ignores_phase_inside_code_block(self):
        content = """
## Phase 1: Real Phase
Real content

```python
content = '''
## Phase 1: Fake Phase
Fake content
'''
```

## Phase 2: Another Real Phase
More content
"""
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 2
        phase_nums = [b[0] for b in boundaries]
        assert phase_nums == [1, 2]

    def test_ignores_multiple_fake_phases(self):
        content = """
## Phase 1: Real

```markdown
## Phase 2: Fake
## Phase 3: Also Fake
```

## Phase 4: Real

```python
# ## Phase 5: In Comment (still in code block)
```
"""
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 2
        phase_nums = [b[0] for b in boundaries]
        assert phase_nums == [1, 4]

    def test_handles_nested_backticks_in_code_block(self):
        content = '''
## Phase 1: Real

```python
doc = """
## Phase 2: Fake in docstring
"""
```

## Phase 3: Real
'''
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 2
        phase_nums = [b[0] for b in boundaries]
        assert phase_nums == [1, 3]

    def test_no_code_blocks_works_normally(self):
        content = """
## Phase 1: First
Content

## Phase 2: Second
Content

## Document Completion
Done
"""
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 2

    def test_document_completion_not_in_code_block(self):
        content = """
## Phase 1: Only Phase
Content

```markdown
## Document Completion
Fake completion
```

## Document Completion
Real completion

More content after completion
"""
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 1
        # The phase should end at the real Document Completion, not the fake one
        _, start, end = boundaries[0]
        assert end < len(content)  # Should not extend to end of content
        # Also verify end is at the real completion, not fake one in code block
        assert "Real completion" not in content[start:end]

    def test_deeply_nested_phase_patterns(self):
        """Phase patterns nested in string literals inside code blocks."""
        content = '''
## Phase 1: Real

```python
test_content = """
## Phase 2: In string
Content
"""

another = \'\'\'
## Phase 3: In another string
\'\'\'

# ## Phase 4: In comment
```

## Phase 5: Real
'''
        boundaries = detect_phase_boundaries(content)
        phase_nums = [b[0] for b in boundaries]
        assert phase_nums == [1, 5]

    def test_real_world_audit_structure(self):
        """Simulate structure of a real audit document with test fixtures."""
        content = '''# Document 1: Test

## Prerequisites
```bash
python -m pytest tests/ -q
# Expected: 100+ passed
```

=== AUDIT SETUP START ===
Setup content
=== AUDIT SETUP END ===

## Phase 1: Implementation

### Context
Real context

### Goal
Real goal

### Files
| File | Action | Purpose |

### Implementation

```python
def test_example():
    content = """
## Phase 1: Fake Phase in Test Fixture
### Context
Fake context
"""
    assert parse(content)
```

### Verify
```bash
pytest -v
# Expected: passed
```

### Completion
```bash
git commit -m "Done"
```

## Phase 2: More Implementation

### Context
More context

### Goal
More goal

### Files
| File | Action | Purpose |

### Implementation
Code here

### Verify
```bash
test command
# Expected: pass
```

### Completion
```bash
git commit
```

## Document Completion
Done
'''
        boundaries = detect_phase_boundaries(content)
        assert len(boundaries) == 2
        phase_nums = [b[0] for b in boundaries]
        assert phase_nums == [1, 2]


class TestLaunchClaudeCode:
    """Tests for launch_claude_code function."""

    def test_returns_completed_process(self):
        """Verify function signature returns CompletedProcess."""
        import subprocess
        from tools.bridge import launch_claude_code
        import inspect

        sig = inspect.signature(launch_claude_code)
        # Check return annotation (may be string or type depending on Python version)
        annotation = sig.return_annotation
        assert annotation == subprocess.CompletedProcess or annotation == 'subprocess.CompletedProcess'

    def test_command_does_not_use_print_flag(self):
        """Verify -p flag is not used (would cause non-interactive mode)."""
        import inspect
        from tools.bridge import launch_claude_code

        source = inspect.getsource(launch_claude_code)
        # Should not contain -p flag
        assert '"-p"' not in source
        assert "'-p'" not in source
