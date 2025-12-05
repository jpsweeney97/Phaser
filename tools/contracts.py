"""
Phaser Contract Engine

Extracts enforceable rules from audit phases, persists them,
and checks code compliance against accumulated contracts.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import click
import yaml

if TYPE_CHECKING:
    from tools.storage import PhaserStorage


class RuleType(str, Enum):
    """Types of contract rules."""

    FORBID_PATTERN = "forbid_pattern"
    REQUIRE_PATTERN = "require_pattern"
    FILE_EXISTS = "file_exists"
    FILE_NOT_EXISTS = "file_not_exists"
    FILE_CONTAINS = "file_contains"
    FILE_NOT_CONTAINS = "file_not_contains"


class Severity(str, Enum):
    """Severity levels for contract violations."""

    ERROR = "error"
    WARNING = "warning"


@dataclass
class AuditSource:
    """Origin information for a contract."""

    id: str
    slug: str
    date: str
    phase: int

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "slug": self.slug,
            "date": self.date,
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> AuditSource:
        return cls(
            id=str(d["id"]),
            slug=str(d["slug"]),
            date=str(d["date"]),
            phase=int(d["phase"]),  # type: ignore[arg-type]
        )


@dataclass
class Rule:
    """A contract rule definition."""

    id: str
    type: RuleType
    severity: Severity
    pattern: str | None
    file_glob: str
    message: str
    rationale: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "pattern": self.pattern,
            "file_glob": self.file_glob,
            "message": self.message,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> Rule:
        return cls(
            id=str(d["id"]),
            type=RuleType(str(d["type"])),
            severity=Severity(str(d["severity"])),
            pattern=str(d["pattern"]) if d.get("pattern") else None,
            file_glob=str(d["file_glob"]),
            message=str(d["message"]),
            rationale=str(d.get("rationale", "")),
        )


@dataclass
class Contract:
    """A complete contract with source and rule."""

    version: int
    audit_source: AuditSource
    rule: Rule
    created_at: str
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "audit_source": self.audit_source.to_dict(),
            "rule": self.rule.to_dict(),
            "created_at": self.created_at,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> Contract:
        audit_source_data = d.get("audit_source", {})
        rule_data = d.get("rule", {})
        if not isinstance(audit_source_data, dict):
            audit_source_data = {}
        if not isinstance(rule_data, dict):
            rule_data = {}
        return cls(
            version=int(d.get("version", 1)),  # type: ignore[arg-type]
            audit_source=AuditSource.from_dict(audit_source_data),
            rule=Rule.from_dict(rule_data),
            created_at=str(d["created_at"]),
            enabled=bool(d.get("enabled", True)),
        )

    @property
    def contract_id(self) -> str:
        """Unique identifier for this contract (based on rule id)."""
        return self.rule.id


@dataclass
class Violation:
    """A single contract violation."""

    path: str
    line: int | None
    match: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "match": self.match,
            "message": self.message,
        }


@dataclass
class CheckResult:
    """Result of checking a single contract."""

    contract_id: str
    rule_id: str
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    checked_at: str = ""

    def __post_init__(self) -> None:
        if not self.checked_at:
            self.checked_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "rule_id": self.rule_id,
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "checked_at": self.checked_at,
        }


# -----------------------------------------------------------------------------
# Contract Operations
# -----------------------------------------------------------------------------


def create_contract(
    rule_id: str,
    rule_type: RuleType,
    pattern: str | None,
    file_glob: str,
    message: str,
    rationale: str,
    audit_source: AuditSource,
    severity: Severity = Severity.ERROR,
) -> Contract:
    """
    Create a new contract.

    Args:
        rule_id: Unique identifier for the rule
        rule_type: Type of rule
        pattern: Regex or literal pattern
        file_glob: Glob pattern for files to check
        message: Human-readable violation message
        rationale: Why this rule exists
        audit_source: Origin audit information
        severity: Error or warning

    Returns:
        New Contract instance
    """
    rule = Rule(
        id=rule_id,
        type=rule_type,
        severity=severity,
        pattern=pattern,
        file_glob=file_glob,
        message=message,
        rationale=rationale,
    )

    return Contract(
        version=1,
        audit_source=audit_source,
        rule=rule,
        created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        enabled=True,
    )


def save_contract(
    contract: Contract,
    storage: PhaserStorage,
) -> str:
    """
    Save contract to .phaser/contracts/ directory.

    Args:
        contract: Contract to save
        storage: PhaserStorage instance

    Returns:
        Contract ID (filename without extension)
    """
    storage.ensure_directories()
    contracts_dir = storage.get_path("contracts")
    contracts_dir.mkdir(exist_ok=True)

    contract_path = contracts_dir / f"{contract.rule.id}.yaml"
    with open(contract_path, "w", encoding="utf-8") as f:
        yaml.dump(contract.to_dict(), f, default_flow_style=False, allow_unicode=True)

    return contract.rule.id


def load_contract(
    contract_id: str,
    storage: PhaserStorage,
) -> Contract | None:
    """
    Load a single contract by ID.

    Args:
        contract_id: Contract identifier
        storage: PhaserStorage instance

    Returns:
        Contract if found, None otherwise
    """
    contract_path = storage.get_path(f"contracts/{contract_id}.yaml")
    if not contract_path.exists():
        return None

    with open(contract_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Contract.from_dict(data)


def load_contracts(
    storage: PhaserStorage,
    enabled_only: bool = True,
) -> list[Contract]:
    """
    Load all contracts from storage.

    Args:
        storage: PhaserStorage instance
        enabled_only: If True, only return enabled contracts

    Returns:
        List of Contract instances
    """
    contracts_dir = storage.get_path("contracts")
    if not contracts_dir.exists():
        return []

    contracts: list[Contract] = []
    for path in sorted(contracts_dir.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            contract = Contract.from_dict(data)
            if not enabled_only or contract.enabled:
                contracts.append(contract)
        except (yaml.YAMLError, KeyError, ValueError):
            # Skip malformed contracts
            continue

    return contracts


def enable_contract(contract_id: str, storage: PhaserStorage) -> bool:
    """
    Enable a contract.

    Args:
        contract_id: Contract identifier
        storage: PhaserStorage instance

    Returns:
        True if found and updated, False otherwise
    """
    contract = load_contract(contract_id, storage)
    if contract is None:
        return False

    contract.enabled = True
    save_contract(contract, storage)
    return True


def disable_contract(contract_id: str, storage: PhaserStorage) -> bool:
    """
    Disable a contract.

    Args:
        contract_id: Contract identifier
        storage: PhaserStorage instance

    Returns:
        True if found and updated, False otherwise
    """
    contract = load_contract(contract_id, storage)
    if contract is None:
        return False

    contract.enabled = False
    save_contract(contract, storage)
    return True


# -----------------------------------------------------------------------------
# Pattern Matching Helpers
# -----------------------------------------------------------------------------


def _glob_match(pattern: str, path: str) -> bool:
    """Check if path matches glob pattern."""
    # Handle ** for recursive matching
    if "**" in pattern:
        # Convert ** glob to regex
        regex_pattern = pattern.replace(".", r"\.")
        regex_pattern = regex_pattern.replace("**", ".*")
        regex_pattern = regex_pattern.replace("*", "[^/]*")
        regex_pattern = f"^{regex_pattern}$"
        return bool(re.match(regex_pattern, path))
    return fnmatch.fnmatch(path, pattern)


def _collect_matching_files(file_glob: str, root: Path) -> list[Path]:
    """Collect all files matching the glob pattern."""
    if "**" in file_glob:
        # Recursive glob
        return list(root.glob(file_glob))
    elif "*" in file_glob or "?" in file_glob:
        # Non-recursive glob
        return list(root.glob(file_glob))
    else:
        # Literal path
        path = root / file_glob
        return [path] if path.exists() else []


def _is_binary(content: bytes) -> bool:
    """Check if content appears to be binary."""
    return b"\x00" in content[:8192]


def find_pattern_violations(
    pattern: str,
    file_glob: str,
    root: Path,
    forbid: bool = True,
) -> list[Violation]:
    """
    Find files matching glob where pattern matches (or doesn't).

    Args:
        pattern: Regex pattern to search for
        file_glob: Glob pattern for files to check
        root: Root directory
        forbid: If True, matches are violations; if False, non-matches are violations

    Returns:
        List of Violation instances
    """
    violations: list[Violation] = []
    files = _collect_matching_files(file_glob, root)

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return [Violation(
            path="",
            line=None,
            match="",
            message=f"Invalid regex pattern: {e}",
        )]

    for filepath in files:
        if not filepath.is_file():
            continue

        # Skip large files (>1MB)
        try:
            if filepath.stat().st_size > 1_000_000:
                continue
        except OSError:
            continue

        try:
            content_bytes = filepath.read_bytes()
        except OSError:
            continue

        # Skip binary files
        if _is_binary(content_bytes):
            continue

        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue

        rel_path = str(filepath.relative_to(root))

        # Search for pattern
        for i, line in enumerate(content.splitlines(), start=1):
            match = regex.search(line)
            if match:
                if forbid:
                    # Pattern found = violation
                    violations.append(Violation(
                        path=rel_path,
                        line=i,
                        match=match.group(),
                        message=f"Forbidden pattern found: {match.group()}",
                    ))

    # For require_pattern, check if pattern was NOT found anywhere
    if not forbid:
        found_any = False
        for filepath in files:
            if not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                if regex.search(content):
                    found_any = True
                    break
            except (OSError, UnicodeDecodeError):
                continue

        if not found_any:
            violations.append(Violation(
                path=file_glob,
                line=None,
                match="",
                message=f"Required pattern not found: {pattern}",
            ))

    return violations


def check_file_exists(path: str, root: Path) -> bool:
    """Check if file exists at path relative to root."""
    return (root / path).exists()


def check_file_contains(
    path: str,
    text: str,
    root: Path,
) -> tuple[bool, int | None]:
    """
    Check if file contains text.

    Returns:
        (found, line_number) - line_number is first occurrence if found
    """
    filepath = root / path
    if not filepath.exists():
        return False, None

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, None

    for i, line in enumerate(content.splitlines(), start=1):
        if text in line:
            return True, i

    return False, None


# -----------------------------------------------------------------------------
# Checking Operations
# -----------------------------------------------------------------------------


def check_contract(
    contract: Contract,
    root: Path,
) -> CheckResult:
    """
    Check a single contract against codebase.

    Args:
        contract: Contract to check
        root: Root directory to check against

    Returns:
        CheckResult with pass/fail status and any violations
    """
    rule = contract.rule
    violations: list[Violation] = []

    if rule.type == RuleType.FORBID_PATTERN:
        if rule.pattern:
            violations = find_pattern_violations(
                rule.pattern, rule.file_glob, root, forbid=True
            )

    elif rule.type == RuleType.REQUIRE_PATTERN:
        if rule.pattern:
            violations = find_pattern_violations(
                rule.pattern, rule.file_glob, root, forbid=False
            )

    elif rule.type == RuleType.FILE_EXISTS:
        if not check_file_exists(rule.file_glob, root):
            violations.append(Violation(
                path=rule.file_glob,
                line=None,
                match="",
                message=rule.message,
            ))

    elif rule.type == RuleType.FILE_NOT_EXISTS:
        if check_file_exists(rule.file_glob, root):
            violations.append(Violation(
                path=rule.file_glob,
                line=None,
                match="",
                message=rule.message,
            ))

    elif rule.type == RuleType.FILE_CONTAINS:
        if rule.pattern:
            found, line = check_file_contains(rule.file_glob, rule.pattern, root)
            if not found:
                violations.append(Violation(
                    path=rule.file_glob,
                    line=None,
                    match="",
                    message=rule.message,
                ))

    elif rule.type == RuleType.FILE_NOT_CONTAINS:
        if rule.pattern:
            found, line = check_file_contains(rule.file_glob, rule.pattern, root)
            if found:
                violations.append(Violation(
                    path=rule.file_glob,
                    line=line,
                    match=rule.pattern,
                    message=rule.message,
                ))

    return CheckResult(
        contract_id=contract.contract_id,
        rule_id=rule.id,
        passed=len(violations) == 0,
        violations=violations,
    )


def check_all_contracts(
    storage: PhaserStorage,
    root: Path,
    fail_fast: bool = False,
) -> list[CheckResult]:
    """
    Check all enabled contracts against codebase.

    Args:
        storage: PhaserStorage instance
        root: Root directory to check against
        fail_fast: If True, stop at first failure

    Returns:
        List of CheckResult for each contract checked
    """
    contracts = load_contracts(storage, enabled_only=True)
    results: list[CheckResult] = []

    for contract in contracts:
        result = check_contract(contract, root)
        results.append(result)

        if fail_fast and not result.passed:
            break

    return results


def format_check_results(
    results: list[CheckResult],
    verbose: bool = False,
) -> str:
    """
    Format check results for display.

    Args:
        results: List of CheckResult to format
        verbose: If True, include violation details

    Returns:
        Formatted string for terminal output
    """
    if not results:
        return "No contracts to check."

    lines: list[str] = []
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"[{status}] {result.rule_id}")

        if verbose and not result.passed:
            for violation in result.violations:
                loc = f":{violation.line}" if violation.line else ""
                lines.append(f"  {violation.path}{loc}: {violation.message}")

    lines.append("")
    lines.append(f"Results: {passed} passed, {failed} failed")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# CLI Interface
# -----------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Phaser contract engine - create and check code contracts."""
    pass


@cli.command()
@click.option("--rule-id", required=True, help="Unique rule identifier")
@click.option(
    "--type", "rule_type",
    type=click.Choice([t.value for t in RuleType]),
    required=True,
    help="Rule type",
)
@click.option("--pattern", help="Regex or literal pattern")
@click.option("--glob", "file_glob", default="**/*", help="File glob pattern")
@click.option("--message", required=True, help="Violation message")
@click.option("--rationale", default="", help="Why this rule exists")
@click.option(
    "--severity",
    type=click.Choice([s.value for s in Severity]),
    default="error",
    help="Severity level",
)
def create(
    rule_id: str,
    rule_type: str,
    pattern: str | None,
    file_glob: str,
    message: str,
    rationale: str,
    severity: str,
) -> None:
    """Create a new contract."""
    from tools.storage import PhaserStorage

    # Create a placeholder audit source for manual contracts
    audit_source = AuditSource(
        id="manual",
        slug="manual",
        date=datetime.now().strftime("%Y-%m-%d"),
        phase=0,
    )

    contract = create_contract(
        rule_id=rule_id,
        rule_type=RuleType(rule_type),
        pattern=pattern,
        file_glob=file_glob,
        message=message,
        rationale=rationale,
        audit_source=audit_source,
        severity=Severity(severity),
    )

    storage = PhaserStorage()
    contract_id = save_contract(contract, storage)
    click.echo(f"Created contract: {contract_id}")


@cli.command()
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=".", help="Root directory")
@click.option("--verbose", "-v", is_flag=True, help="Show violation details")
@click.option("--fail-on-error", is_flag=True, help="Exit with error code on failures")
def check(root: Path, verbose: bool, fail_on_error: bool) -> None:
    """Check all contracts against codebase."""
    from tools.storage import PhaserStorage

    storage = PhaserStorage()
    results = check_all_contracts(storage, root)

    output = format_check_results(results, verbose=verbose)
    click.echo(output)

    if fail_on_error:
        failed = sum(1 for r in results if not r.passed)
        if failed > 0:
            raise SystemExit(1)


@cli.command("list")
@click.option("--enabled-only", is_flag=True, help="Only show enabled contracts")
def list_contracts(enabled_only: bool) -> None:
    """List all contracts."""
    from tools.storage import PhaserStorage

    storage = PhaserStorage()
    contracts = load_contracts(storage, enabled_only=enabled_only)

    if not contracts:
        click.echo("No contracts found.")
        return

    for contract in contracts:
        status = "enabled" if contract.enabled else "disabled"
        click.echo(f"{contract.rule.id} [{status}] - {contract.rule.message}")


@cli.command()
@click.argument("contract_id")
def enable(contract_id: str) -> None:
    """Enable a contract."""
    from tools.storage import PhaserStorage

    storage = PhaserStorage()
    if enable_contract(contract_id, storage):
        click.echo(f"Enabled: {contract_id}")
    else:
        click.echo(f"Contract not found: {contract_id}")
        raise SystemExit(1)


@cli.command()
@click.argument("contract_id")
def disable(contract_id: str) -> None:
    """Disable a contract."""
    from tools.storage import PhaserStorage

    storage = PhaserStorage()
    if disable_contract(contract_id, storage):
        click.echo(f"Disabled: {contract_id}")
    else:
        click.echo(f"Contract not found: {contract_id}")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
