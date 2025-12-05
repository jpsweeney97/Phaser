"""Tests for tools/contracts.py — Contract creation and checking."""

from pathlib import Path

import pytest

from tools.contracts import (
    AuditSource,
    CheckResult,
    Contract,
    Rule,
    RuleType,
    Severity,
    Violation,
    check_all_contracts,
    check_contract,
    create_contract,
    disable_contract,
    enable_contract,
    format_check_results,
    load_contract,
    load_contracts,
    save_contract,
)


# -----------------------------------------------------------------------------
# Enum Tests
# -----------------------------------------------------------------------------


def test_rule_type_enum() -> None:
    """RuleType enum has all expected values."""
    assert RuleType.FORBID_PATTERN.value == "forbid_pattern"
    assert RuleType.REQUIRE_PATTERN.value == "require_pattern"
    assert RuleType.FILE_EXISTS.value == "file_exists"
    assert RuleType.FILE_NOT_EXISTS.value == "file_not_exists"
    assert RuleType.FILE_CONTAINS.value == "file_contains"
    assert RuleType.FILE_NOT_CONTAINS.value == "file_not_contains"


def test_severity_enum() -> None:
    """Severity enum has expected values."""
    assert Severity.ERROR.value == "error"
    assert Severity.WARNING.value == "warning"


# -----------------------------------------------------------------------------
# AuditSource Tests
# -----------------------------------------------------------------------------


def test_audit_source_creation() -> None:
    """AuditSource can be created."""
    source = AuditSource(
        id="abc-123",
        slug="test-audit",
        date="2025-12-05",
        phase=3,
    )
    assert source.id == "abc-123"
    assert source.slug == "test-audit"
    assert source.phase == 3


def test_audit_source_to_dict() -> None:
    """AuditSource serializes to dict."""
    source = AuditSource("id", "slug", "2025-01-01", 1)
    d = source.to_dict()
    assert d["id"] == "id"
    assert d["slug"] == "slug"
    assert d["phase"] == 1


def test_audit_source_from_dict() -> None:
    """AuditSource deserializes from dict."""
    d = {"id": "x", "slug": "y", "date": "2025-06-01", "phase": 5}
    source = AuditSource.from_dict(d)
    assert source.id == "x"
    assert source.phase == 5


# -----------------------------------------------------------------------------
# Contract Tests
# -----------------------------------------------------------------------------


def test_contract_creation() -> None:
    """Contract can be created via create_contract."""
    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="no-singleton",
        rule_type=RuleType.FORBID_PATTERN,
        pattern=r"\.shared\b",
        file_glob="**/*.swift",
        message="No singletons",
        rationale="Use DI instead",
        audit_source=source,
        severity=Severity.ERROR,
    )

    assert contract.version == 1
    assert contract.enabled is True
    assert contract.rule.id == "no-singleton"
    assert contract.rule.type == RuleType.FORBID_PATTERN
    assert contract.rule.severity == Severity.ERROR


def test_contract_to_dict() -> None:
    """Contract serializes to dict."""
    source = AuditSource("id", "slug", "2025-01-01", 1)
    contract = create_contract(
        rule_id="test",
        rule_type=RuleType.FILE_EXISTS,
        pattern=None,
        file_glob="LICENSE",
        message="License required",
        rationale="",
        audit_source=source,
    )

    d = contract.to_dict()
    assert d["version"] == 1
    assert d["enabled"] is True
    assert d["rule"]["id"] == "test"
    assert d["audit_source"]["slug"] == "slug"


def test_contract_from_dict() -> None:
    """Contract deserializes from dict."""
    d = {
        "version": 1,
        "audit_source": {"id": "a", "slug": "b", "date": "2025-01-01", "phase": 2},
        "rule": {
            "id": "test-rule",
            "type": "forbid_pattern",
            "severity": "warning",
            "pattern": "TODO",
            "file_glob": "**/*.py",
            "message": "No TODOs",
            "rationale": "",
        },
        "created_at": "2025-12-05T10:00:00Z",
        "enabled": False,
    }
    contract = Contract.from_dict(d)
    assert contract.rule.id == "test-rule"
    assert contract.rule.type == RuleType.FORBID_PATTERN
    assert contract.rule.severity == Severity.WARNING
    assert contract.enabled is False


def test_save_and_load_contract(storage) -> None:
    """Contract can be saved and loaded."""
    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="test-save",
        rule_type=RuleType.FILE_EXISTS,
        pattern=None,
        file_glob="README.md",
        message="Need README",
        rationale="",
        audit_source=source,
    )

    contract_id = save_contract(contract, storage)
    assert contract_id == "test-save"

    loaded = load_contract("test-save", storage)
    assert loaded is not None
    assert loaded.rule.id == "test-save"
    assert loaded.rule.file_glob == "README.md"


def test_load_contract_not_found(storage) -> None:
    """Loading nonexistent contract returns None."""
    result = load_contract("nonexistent", storage)
    assert result is None


def test_load_contracts_empty(storage) -> None:
    """Loading from empty storage returns empty list."""
    contracts = load_contracts(storage)
    assert contracts == []


def test_load_contracts_multiple(storage) -> None:
    """Load multiple contracts."""
    source = AuditSource("id", "slug", "2025-12-05", 1)

    for i in range(3):
        contract = create_contract(
            rule_id=f"rule-{i}",
            rule_type=RuleType.FILE_EXISTS,
            pattern=None,
            file_glob=f"file{i}.txt",
            message=f"Need file {i}",
            rationale="",
            audit_source=source,
        )
        save_contract(contract, storage)

    contracts = load_contracts(storage)
    assert len(contracts) == 3


def test_enable_disable_contract(storage) -> None:
    """Contract can be enabled and disabled."""
    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="toggle-test",
        rule_type=RuleType.FILE_EXISTS,
        pattern=None,
        file_glob="test.txt",
        message="test",
        rationale="",
        audit_source=source,
    )
    save_contract(contract, storage)

    # Disable
    result = disable_contract("toggle-test", storage)
    assert result is True

    loaded = load_contract("toggle-test", storage)
    assert loaded is not None
    assert loaded.enabled is False

    # Enable
    result = enable_contract("toggle-test", storage)
    assert result is True

    loaded = load_contract("toggle-test", storage)
    assert loaded is not None
    assert loaded.enabled is True


def test_enable_nonexistent(storage) -> None:
    """Enable nonexistent contract returns False."""
    result = enable_contract("nonexistent", storage)
    assert result is False


# -----------------------------------------------------------------------------
# Checking Tests - forbid_pattern
# -----------------------------------------------------------------------------


def test_forbid_pattern_violation(temp_dir: Path, storage) -> None:
    """forbid_pattern detects violations."""
    (temp_dir / "code.py").write_text("x = Singleton.shared\n")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="no-singleton",
        rule_type=RuleType.FORBID_PATTERN,
        pattern=r"\.shared\b",
        file_glob="**/*.py",
        message="No singletons",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].path == "code.py"


def test_forbid_pattern_pass(temp_dir: Path, storage) -> None:
    """forbid_pattern passes when pattern not found."""
    (temp_dir / "code.py").write_text("x = get_instance()\n")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="no-singleton",
        rule_type=RuleType.FORBID_PATTERN,
        pattern=r"\.shared\b",
        file_glob="**/*.py",
        message="No singletons",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is True
    assert len(result.violations) == 0


# -----------------------------------------------------------------------------
# Checking Tests - require_pattern
# -----------------------------------------------------------------------------


def test_require_pattern_violation(temp_dir: Path) -> None:
    """require_pattern fails when pattern not found."""
    (temp_dir / "model.py").write_text("class Model:\n    pass\n")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="require-observable",
        rule_type=RuleType.REQUIRE_PATTERN,
        pattern=r"@Observable",
        file_glob="**/*.py",
        message="Need @Observable",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is False


def test_require_pattern_pass(temp_dir: Path) -> None:
    """require_pattern passes when pattern found."""
    (temp_dir / "model.py").write_text("@Observable\nclass Model:\n    pass\n")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="require-observable",
        rule_type=RuleType.REQUIRE_PATTERN,
        pattern=r"@Observable",
        file_glob="**/*.py",
        message="Need @Observable",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is True


# -----------------------------------------------------------------------------
# Checking Tests - file_exists
# -----------------------------------------------------------------------------


def test_file_exists_pass(temp_dir: Path) -> None:
    """file_exists passes when file present."""
    (temp_dir / "LICENSE").write_text("MIT License")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="license-required",
        rule_type=RuleType.FILE_EXISTS,
        pattern=None,
        file_glob="LICENSE",
        message="Need LICENSE",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is True


def test_file_exists_violation(temp_dir: Path) -> None:
    """file_exists fails when file absent."""
    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="license-required",
        rule_type=RuleType.FILE_EXISTS,
        pattern=None,
        file_glob="LICENSE",
        message="Need LICENSE",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is False
    assert len(result.violations) == 1


# -----------------------------------------------------------------------------
# Checking Tests - file_not_exists
# -----------------------------------------------------------------------------


def test_file_not_exists_pass(temp_dir: Path) -> None:
    """file_not_exists passes when file absent."""
    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="no-env",
        rule_type=RuleType.FILE_NOT_EXISTS,
        pattern=None,
        file_glob=".env",
        message="No .env file",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is True


def test_file_not_exists_violation(temp_dir: Path) -> None:
    """file_not_exists fails when file present."""
    (temp_dir / ".env").write_text("SECRET=xxx")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="no-env",
        rule_type=RuleType.FILE_NOT_EXISTS,
        pattern=None,
        file_glob=".env",
        message="No .env file",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is False


# -----------------------------------------------------------------------------
# Checking Tests - file_contains
# -----------------------------------------------------------------------------


def test_file_contains_pass(temp_dir: Path) -> None:
    """file_contains passes when text found."""
    (temp_dir / "README.md").write_text("# Project\n\n## Installation\n\nRun npm install")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="readme-install",
        rule_type=RuleType.FILE_CONTAINS,
        pattern="## Installation",
        file_glob="README.md",
        message="Need install section",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is True


def test_file_contains_violation(temp_dir: Path) -> None:
    """file_contains fails when text not found."""
    (temp_dir / "README.md").write_text("# Project\n\nJust a project.")

    source = AuditSource("id", "slug", "2025-12-05", 1)
    contract = create_contract(
        rule_id="readme-install",
        rule_type=RuleType.FILE_CONTAINS,
        pattern="## Installation",
        file_glob="README.md",
        message="Need install section",
        rationale="",
        audit_source=source,
    )

    result = check_contract(contract, temp_dir)
    assert result.passed is False


# -----------------------------------------------------------------------------
# Batch Check Tests
# -----------------------------------------------------------------------------


def test_check_all_contracts_empty(storage, temp_dir: Path) -> None:
    """Check all with no contracts returns empty list."""
    results = check_all_contracts(storage, temp_dir)
    assert results == []


def test_check_all_contracts_all_pass(storage, temp_dir: Path) -> None:
    """Check all when all contracts pass."""
    (temp_dir / "LICENSE").write_text("MIT")
    (temp_dir / "README.md").write_text("# Hi")

    source = AuditSource("id", "slug", "2025-12-05", 1)

    c1 = create_contract("has-license", RuleType.FILE_EXISTS, None, "LICENSE", "need license", "", source)
    c2 = create_contract("has-readme", RuleType.FILE_EXISTS, None, "README.md", "need readme", "", source)

    save_contract(c1, storage)
    save_contract(c2, storage)

    results = check_all_contracts(storage, temp_dir)
    assert len(results) == 2
    assert all(r.passed for r in results)


def test_check_all_contracts_some_fail(storage, temp_dir: Path) -> None:
    """Check all when some contracts fail."""
    (temp_dir / "LICENSE").write_text("MIT")
    # No README

    source = AuditSource("id", "slug", "2025-12-05", 1)

    c1 = create_contract("has-license", RuleType.FILE_EXISTS, None, "LICENSE", "need license", "", source)
    c2 = create_contract("has-readme", RuleType.FILE_EXISTS, None, "README.md", "need readme", "", source)

    save_contract(c1, storage)
    save_contract(c2, storage)

    results = check_all_contracts(storage, temp_dir)
    assert len(results) == 2
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    assert len(passed) == 1
    assert len(failed) == 1


def test_check_all_contracts_fail_fast(storage, temp_dir: Path) -> None:
    """Check all with fail_fast stops at first failure."""
    source = AuditSource("id", "slug", "2025-12-05", 1)

    # Both will fail
    c1 = create_contract("a-file", RuleType.FILE_EXISTS, None, "a.txt", "need a", "", source)
    c2 = create_contract("b-file", RuleType.FILE_EXISTS, None, "b.txt", "need b", "", source)

    save_contract(c1, storage)
    save_contract(c2, storage)

    results = check_all_contracts(storage, temp_dir, fail_fast=True)
    assert len(results) == 1  # Stopped after first failure


# -----------------------------------------------------------------------------
# Output Tests
# -----------------------------------------------------------------------------


def test_format_results_all_pass() -> None:
    """Format results when all pass."""
    results = [
        CheckResult("c1", "rule1", True, []),
        CheckResult("c2", "rule2", True, []),
    ]
    output = format_check_results(results)
    assert "[PASS] rule1" in output
    assert "[PASS] rule2" in output
    assert "2 passed, 0 failed" in output


def test_format_results_with_violations() -> None:
    """Format results with failures."""
    results = [
        CheckResult("c1", "rule1", True, []),
        CheckResult("c2", "rule2", False, [
            Violation("file.py", 10, "bad", "Found bad pattern")
        ]),
    ]
    output = format_check_results(results, verbose=True)
    assert "[PASS] rule1" in output
    assert "[FAIL] rule2" in output
    assert "file.py:10" in output
    assert "1 passed, 1 failed" in output


def test_format_results_empty() -> None:
    """Format empty results."""
    output = format_check_results([])
    assert "No contracts" in output
