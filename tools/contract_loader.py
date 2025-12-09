"""Load and validate contracts from YAML files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

import yaml


VALID_TYPES = frozenset(
    [
        "forbid_pattern",
        "require_pattern",
        "file_exists",
        "file_not_exists",
        "file_contains",
        "file_not_contains",
    ]
)

VALID_SEVERITIES = frozenset(["error", "warning"])


@dataclass
class Contract:
    """A single contract rule."""

    rule_id: str
    type: str
    pattern: Optional[str]
    file_glob: str
    message: str
    severity: str
    rationale: str = ""
    enabled: bool = True
    source: str = "user"  # "user" or "project"
    _compiled_pattern: Optional[re.Pattern] = field(default=None, repr=False)

    def matches_file(self, file_path: str) -> bool:
        """Check if this contract applies to the given file."""
        return fnmatch(file_path, self.file_glob)

    @property
    def compiled_pattern(self) -> Optional[re.Pattern]:
        """Get compiled regex pattern (cached)."""
        if self._compiled_pattern is None and self.pattern:
            self._compiled_pattern = re.compile(self.pattern)
        return self._compiled_pattern


@dataclass
class LoadResult:
    """Result of loading contracts."""

    contracts: list[Contract]
    warnings: list[str]


def validate_contract(
    data: dict, source: str
) -> tuple[Optional[Contract], Optional[str]]:
    """Validate and create a Contract from YAML data."""
    rule_id = data.get("rule_id", "")

    # Validate rule_id
    if not rule_id:
        return None, "Missing rule_id"
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,63}$", rule_id):
        return None, f"Invalid rule_id: {rule_id}"

    # Validate type
    contract_type = data.get("type", "")
    if contract_type not in VALID_TYPES:
        return None, f"Invalid type '{contract_type}' for {rule_id}"

    # Validate pattern for pattern-based types
    pattern = data.get("pattern")
    if contract_type in (
        "forbid_pattern",
        "require_pattern",
        "file_contains",
        "file_not_contains",
    ):
        if not pattern:
            return None, f"Missing pattern for {rule_id}"
        try:
            re.compile(pattern)
        except re.error as e:
            return None, f"Invalid regex for {rule_id}: {e}"

    # Validate file_glob
    file_glob = data.get("file_glob", "")
    if not file_glob:
        return None, f"Missing file_glob for {rule_id}"

    # Validate severity
    severity = data.get("severity", "")
    if severity not in VALID_SEVERITIES:
        return None, f"Invalid severity '{severity}' for {rule_id}"

    # Validate message
    message = data.get("message", "")
    if not message:
        return None, f"Missing message for {rule_id}"

    return (
        Contract(
            rule_id=rule_id,
            type=contract_type,
            pattern=pattern,
            file_glob=file_glob,
            message=message,
            severity=severity,
            rationale=data.get("rationale", ""),
            enabled=data.get("enabled", True),
            source=source,
        ),
        None,
    )


def load_contracts_from_dir(contracts_dir: Path, source: str) -> LoadResult:
    """Load all contracts from a directory."""
    contracts: list[Contract] = []
    warnings: list[str] = []

    if not contracts_dir.exists():
        return LoadResult(contracts, warnings)

    for yaml_file in contracts_dir.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            if not isinstance(data, dict):
                warnings.append(f"{yaml_file.name}: Expected YAML dict, got {type(data).__name__}")
                continue
            contract, error = validate_contract(data, source)
            if error:
                warnings.append(f"{yaml_file.name}: {error}")
            elif contract and contract.enabled:
                contracts.append(contract)
        except yaml.YAMLError as e:
            warnings.append(f"{yaml_file.name}: YAML parse error: {e}")
        except OSError as e:
            warnings.append(f"{yaml_file.name}: Read error: {e}")

    return LoadResult(contracts, warnings)


def load_contracts(project_root: Optional[Path] = None) -> LoadResult:
    """Load contracts from project and user directories."""
    all_contracts: list[Contract] = []
    all_warnings: list[str] = []
    seen_ids: set[str] = set()

    # Project contracts (higher precedence)
    if project_root:
        project_dir = project_root / ".claude" / "contracts"
        result = load_contracts_from_dir(project_dir, "project")
        for contract in result.contracts:
            all_contracts.append(contract)
            seen_ids.add(contract.rule_id)
        all_warnings.extend(result.warnings)

    # User contracts (lower precedence)
    user_dir = Path.home() / ".phaser" / "contracts"
    result = load_contracts_from_dir(user_dir, "user")
    for contract in result.contracts:
        if contract.rule_id not in seen_ids:
            all_contracts.append(contract)
            seen_ids.add(contract.rule_id)
        # Skip duplicates silently (project takes precedence)
    all_warnings.extend(result.warnings)

    return LoadResult(all_contracts, all_warnings)
