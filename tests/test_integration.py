"""Integration tests for diff and contracts working together."""

from pathlib import Path

import pytest

from tools.contracts import (
    AuditSource,
    RuleType,
    Severity,
    check_contract,
    create_contract,
    save_contract,
)
from tools.diff import (
    capture_manifest,
    compare_manifests,
    load_manifests_for_audit,
    save_manifest_to_storage,
)
from tools.events import EventEmitter, EventType
from tools.storage import PhaserStorage


# -----------------------------------------------------------------------------
# Full Audit Lifecycle Tests
# -----------------------------------------------------------------------------


def test_full_audit_lifecycle_with_diff(temp_dir: Path) -> None:
    """Test complete audit lifecycle with manifest capture."""
    audit_id = "test-audit-001"

    # Use separate directories for project and storage
    project_dir = temp_dir / "project"
    storage_dir = temp_dir / "storage"
    project_dir.mkdir()
    storage_dir.mkdir()

    storage = PhaserStorage(root=storage_dir)

    # Create initial project state
    (project_dir / "src").mkdir()
    (project_dir / "src" / "main.py").write_text("print('hello')")
    (project_dir / "README.md").write_text("# Test Project")

    # Capture pre-audit manifest
    pre_manifest = capture_manifest(project_dir)
    save_manifest_to_storage(storage, pre_manifest, audit_id, "pre")

    assert pre_manifest.file_count == 2

    # Simulate audit changes
    (project_dir / "src" / "main.py").write_text("print('hello world')")  # Modified
    (project_dir / "src" / "utils.py").write_text("def helper(): pass")  # Added
    (project_dir / "README.md").unlink()  # Deleted

    # Capture post-audit manifest
    post_manifest = capture_manifest(project_dir)
    save_manifest_to_storage(storage, post_manifest, audit_id, "post")

    # Load and compare
    pre, post = load_manifests_for_audit(storage, audit_id)
    assert pre is not None
    assert post is not None

    diff = compare_manifests(pre, post)

    assert len(diff.added) == 1
    assert diff.added[0].path == "src/utils.py"

    assert len(diff.modified) == 1
    assert diff.modified[0].path == "src/main.py"

    assert len(diff.deleted) == 1
    assert diff.deleted[0].path == "README.md"


def test_contract_created_from_audit(temp_dir: Path, storage: PhaserStorage) -> None:
    """Test creating a contract based on audit findings."""
    # Simulate audit that removed singleton pattern
    audit_source = AuditSource(
        id="audit-123",
        slug="remove-singletons",
        date="2025-12-05",
        phase=3,
    )

    # Create contract to prevent regression
    contract = create_contract(
        rule_id="no-singleton",
        rule_type=RuleType.FORBID_PATTERN,
        pattern=r"\.shared\b",
        file_glob="**/*.swift",
        message="Singleton pattern not allowed after audit phase 3",
        rationale="Use dependency injection instead",
        audit_source=audit_source,
        severity=Severity.ERROR,
    )

    contract_id = save_contract(contract, storage)
    assert contract_id == "no-singleton"

    # Verify contract checks work
    (temp_dir / "App.swift").write_text("let app = AppDelegate.shared")

    result = check_contract(contract, temp_dir)
    assert result.passed is False
    assert len(result.violations) == 1
    assert "App.swift" in result.violations[0].path


def test_contract_check_after_regression(temp_dir: Path, storage: PhaserStorage) -> None:
    """Test that contracts detect regressions after audit."""
    # Set up contract from previous audit
    source = AuditSource("old-audit", "security-fix", "2025-11-01", 2)
    contract = create_contract(
        rule_id="no-hardcoded-secret",
        rule_type=RuleType.FORBID_PATTERN,
        pattern=r"password\s*=\s*['\"][^'\"]+['\"]",
        file_glob="**/*.py",
        message="Hardcoded passwords not allowed",
        rationale="Security audit phase 2",
        audit_source=source,
    )
    save_contract(contract, storage)

    # Code is clean
    (temp_dir / "config.py").write_text("password = os.environ['PASSWORD']")
    result = check_contract(contract, temp_dir)
    assert result.passed is True

    # Developer introduces regression
    (temp_dir / "test_helper.py").write_text("password = 'test123'")
    result = check_contract(contract, temp_dir)
    assert result.passed is False
    assert "test_helper.py" in result.violations[0].path


def test_events_emitted_during_diff(
    temp_dir: Path,
    storage: PhaserStorage,
    emitter: EventEmitter,
) -> None:
    """Test that events are emitted during diff operations."""
    from tools.audit_hooks import on_audit_complete, on_audit_setup

    audit_id = "event-test-audit"
    collected_events: list[tuple[EventType, dict]] = []

    def collector(event) -> None:
        collected_events.append((event.type, event.data))

    emitter.subscribe(collector)

    # Create initial state
    (temp_dir / "file.txt").write_text("original")

    # Setup captures pre-manifest
    on_audit_setup(temp_dir, audit_id, storage, emitter)

    # Modify file
    (temp_dir / "file.txt").write_text("modified")
    (temp_dir / "new.txt").write_text("new file")

    # Complete captures post-manifest and emits events
    diff = on_audit_complete(temp_dir, audit_id, storage, emitter)

    assert diff is not None

    # Check that file events were emitted
    event_types = [e[0] for e in collected_events]
    assert EventType.FILE_CREATED in event_types
    assert EventType.FILE_MODIFIED in event_types


# -----------------------------------------------------------------------------
# Combined Diff + Contract Workflow
# -----------------------------------------------------------------------------


def test_audit_diff_informs_contract(temp_dir: Path, storage: PhaserStorage) -> None:
    """Test workflow where diff results inform contract creation."""
    audit_id = "diff-to-contract"

    # Initial state with bad pattern
    (temp_dir / "code.py").write_text("logger.debug('debug info')")

    pre = capture_manifest(temp_dir)
    save_manifest_to_storage(storage, pre, audit_id, "pre")

    # Audit removes debug logging
    (temp_dir / "code.py").write_text("logger.info('info message')")

    post = capture_manifest(temp_dir)
    save_manifest_to_storage(storage, post, audit_id, "post")

    # Compare shows modification
    diff = compare_manifests(pre, post)
    assert len(diff.modified) == 1

    # Create contract to prevent debug logging from returning
    source = AuditSource(audit_id, "remove-debug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="no-debug-log",
        rule_type=RuleType.FORBID_PATTERN,
        pattern=r"logger\.debug\(",
        file_glob="**/*.py",
        message="Debug logging not allowed in production",
        rationale="Removed in audit phase 1",
        audit_source=source,
    )

    # Verify current code passes
    result = check_contract(contract, temp_dir)
    assert result.passed is True


def test_multiple_contracts_from_single_audit(temp_dir: Path) -> None:
    """Test creating multiple contracts from one audit."""
    # Use separate directories for project and storage
    project_dir = temp_dir / "project"
    storage_dir = temp_dir / "storage"
    project_dir.mkdir()
    storage_dir.mkdir()

    storage = PhaserStorage(root=storage_dir)
    source = AuditSource("multi-contract", "code-quality", "2025-12-05", 1)

    contracts = [
        create_contract(
            "no-print",
            RuleType.FORBID_PATTERN,
            r"\bprint\(",
            "**/*.py",
            "Use logger instead of print",
            "",
            source,
        ),
        create_contract(
            "has-docstring",
            RuleType.FILE_CONTAINS,
            '"""',
            "module.py",
            "Files should have docstrings",
            "",
            source,
        ),
        create_contract(
            "has-tests",
            RuleType.FILE_EXISTS,
            None,
            "tests/__init__.py",
            "Tests directory required",
            "",
            source,
        ),
    ]

    for c in contracts:
        save_contract(c, storage)

    # Set up compliant code
    (project_dir / "module.py").write_text('"""Module docstring."""\nimport logging\nlog = logging.getLogger()\n')
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "__init__.py").write_text("")

    # All contracts should pass
    from tools.contracts import check_all_contracts

    results = check_all_contracts(storage, project_dir)
    assert len(results) == 3
    assert all(r.passed for r in results)


# -----------------------------------------------------------------------------
# Edge Cases
# -----------------------------------------------------------------------------


def test_diff_and_contract_with_binary_files(temp_dir: Path) -> None:
    """Binary files are handled correctly by both diff and contracts."""
    audit_id = "binary-test"

    # Use separate directories for project and storage
    project_dir = temp_dir / "project"
    storage_dir = temp_dir / "storage"
    project_dir.mkdir()
    storage_dir.mkdir()

    storage = PhaserStorage(root=storage_dir)

    # Create binary file
    (project_dir / "data.bin").write_bytes(b"\x00\x01\x02\x03")

    pre = capture_manifest(project_dir)
    save_manifest_to_storage(storage, pre, audit_id, "pre")

    # Modify binary
    (project_dir / "data.bin").write_bytes(b"\x00\x01\x02\x03\x04\x05")

    post = capture_manifest(project_dir)
    save_manifest_to_storage(storage, post, audit_id, "post")

    diff = compare_manifests(pre, post)
    assert len(diff.modified) == 1
    assert diff.modified[0].diff_lines == ["(binary file changed)"]

    # Contract pattern matching skips binary files
    source = AuditSource("test", "test", "2025-12-05", 1)
    contract = create_contract(
        "no-pattern",
        RuleType.FORBID_PATTERN,
        ".",
        "**/*.bin",  # Only check .bin files
        "test",
        "",
        source,
    )

    # Binary file should not trigger pattern match (binary files are skipped)
    result = check_contract(contract, project_dir)
    assert result.passed is True


def test_empty_directory_diff_and_contracts(temp_dir: Path, storage: PhaserStorage) -> None:
    """Handle empty directories gracefully."""
    audit_id = "empty-test"

    pre = capture_manifest(temp_dir)
    post = capture_manifest(temp_dir)

    assert pre.file_count == 0
    assert post.file_count == 0

    diff = compare_manifests(pre, post)
    assert diff.summary() == "No changes"

    # Contract on empty dir
    source = AuditSource("test", "test", "2025-12-05", 1)
    contract = create_contract(
        "readme-exists",
        RuleType.FILE_EXISTS,
        None,
        "README.md",
        "Need README",
        "",
        source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is False
