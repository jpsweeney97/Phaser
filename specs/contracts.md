# Contract Specification

> Phaser v1.2 — Audit Contracts Feature

---

## Overview

Audit Contracts enable extracting enforceable rules from completed audit phases. When an audit fixes an issue (e.g., removes singleton patterns), a contract can be created that prevents regression. Contracts are machine-checkable rules that persist beyond the audit.

---

## Purpose

1. **Extract quality rules** from audit phases
2. **Persist rules** for future enforcement
3. **Check current code** against accumulated rules
4. **Integrate with CI** for regression prevention

---

## Contract Schema

```yaml
version: 1

audit_source:
  id: "abc-123-def-456"
  slug: "security-hardening"
  date: "2025-12-05"
  phase: 3

rule:
  id: "no-singleton-pattern"
  type: "forbid_pattern"
  severity: "error"
  pattern: "\\.shared\\b"
  file_glob: "**/*.swift"
  message: "Singleton pattern (.shared) is not allowed"
  rationale: "Use dependency injection instead (see phase 3)"

created_at: "2025-12-05T10:30:00Z"
enabled: true
```

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | int | Yes | Schema version (currently 1) |
| audit_source | object | Yes | Origin audit information |
| rule | object | Yes | The enforceable rule definition |
| created_at | string | Yes | ISO 8601 timestamp |
| enabled | bool | Yes | Whether contract is active |

### AuditSource Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | UUID of source audit |
| slug | string | Yes | Audit identifier slug |
| date | string | Yes | Audit date (YYYY-MM-DD) |
| phase | int | Yes | Phase number that created this contract |

### Rule Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique rule identifier (kebab-case) |
| type | string | Yes | Rule type (see Rule Types below) |
| severity | string | Yes | "error" or "warning" |
| pattern | string | Conditional | Regex pattern (required for pattern rules) |
| file_glob | string | Yes | Glob pattern for files to check |
| message | string | Yes | Human-readable violation message |
| rationale | string | No | Why this rule exists |

---

## Rule Types

| Type | Purpose | Passes When |
|------|---------|-------------|
| `forbid_pattern` | Content must NOT match regex | Pattern not found in any matching file |
| `require_pattern` | Content MUST match regex | Pattern found in at least one matching file |
| `file_exists` | File must exist | Specified file is present |
| `file_not_exists` | File must NOT exist | Specified file is absent |
| `file_contains` | File must contain text | Literal text found in file |
| `file_not_contains` | File must NOT contain text | Literal text not found in file |

### forbid_pattern

Ensures a regex pattern does NOT appear in files matching the glob.

```yaml
rule:
  id: "no-force-unwrap"
  type: "forbid_pattern"
  severity: "error"
  pattern: "\\!\\s*$"
  file_glob: "**/*.swift"
  message: "Force unwrap (!) is not allowed"
```

### require_pattern

Ensures a regex pattern DOES appear in at least one file matching the glob.

```yaml
rule:
  id: "require-observable"
  type: "require_pattern"
  severity: "warning"
  pattern: "@Observable"
  file_glob: "**/ViewModels/*.swift"
  message: "ViewModels should use @Observable macro"
```

### file_exists

Ensures a specific file exists.

```yaml
rule:
  id: "license-required"
  type: "file_exists"
  severity: "error"
  file_glob: "LICENSE"
  message: "LICENSE file must exist in repository root"
```

### file_not_exists

Ensures a specific file does NOT exist.

```yaml
rule:
  id: "no-env-file"
  type: "file_not_exists"
  severity: "error"
  file_glob: ".env"
  message: ".env file should not be committed"
```

### file_contains

Ensures a file contains specific literal text.

```yaml
rule:
  id: "readme-has-installation"
  type: "file_contains"
  severity: "warning"
  pattern: "## Installation"
  file_glob: "README.md"
  message: "README.md should have an Installation section"
```

### file_not_contains

Ensures a file does NOT contain specific literal text.

```yaml
rule:
  id: "no-hardcoded-secrets"
  type: "file_not_contains"
  severity: "error"
  pattern: "sk-"
  file_glob: "**/*.py"
  message: "Potential API key found in source file"
```

---

## Data Classes

### AuditSource

```python
@dataclass
class AuditSource:
    id: str
    slug: str
    date: str
    phase: int

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "AuditSource": ...
```

### Rule

```python
@dataclass
class Rule:
    id: str
    type: RuleType
    severity: Severity
    pattern: str | None
    file_glob: str
    message: str
    rationale: str

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Rule": ...
```

### Contract

```python
@dataclass
class Contract:
    version: int
    audit_source: AuditSource
    rule: Rule
    created_at: str
    enabled: bool

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Contract": ...
```

### Violation

```python
@dataclass
class Violation:
    path: str
    line: int | None
    match: str
    message: str

    def to_dict(self) -> dict: ...
```

### CheckResult

```python
@dataclass
class CheckResult:
    contract_id: str
    rule_id: str
    passed: bool
    violations: list[Violation]
    checked_at: str

    def to_dict(self) -> dict: ...
```

---

## Contract Operations

### create_contract

```python
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
    Create a new contract from parameters.

    Args:
        rule_id: Unique identifier for the rule
        rule_type: Type of rule (forbid_pattern, etc.)
        pattern: Regex or literal pattern (required for pattern rules)
        file_glob: Glob pattern for files to check
        message: Human-readable violation message
        rationale: Why this rule exists
        audit_source: Origin audit information
        severity: Error or warning (default: error)

    Returns:
        New Contract instance with generated timestamp
    """
```

### save_contract

```python
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
```

### load_contracts

```python
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
```

### enable_contract / disable_contract

```python
def enable_contract(contract_id: str, storage: PhaserStorage) -> bool:
    """Enable a contract. Returns True if found and updated."""

def disable_contract(contract_id: str, storage: PhaserStorage) -> bool:
    """Disable a contract. Returns True if found and updated."""
```

---

## Checking Operations

### check_contract

```python
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
```

### check_all_contracts

```python
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
```

### format_check_results

```python
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
```

---

## Pattern Matching Helpers

### find_pattern_violations

```python
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
```

### check_file_exists

```python
def check_file_exists(path: str, root: Path) -> bool:
    """Check if file exists at path relative to root."""
```

### check_file_contains

```python
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
```

---

## Integration Points

### Manual Extraction

Create contracts manually via CLI:

```bash
python -m tools.contracts create \
  --rule-id no-singleton \
  --type forbid_pattern \
  --pattern "\.shared\b" \
  --glob "**/*.swift" \
  --message "No singleton pattern"
```

### Automatic Suggestion

After phase completion, suggest relevant contracts based on phase content:

| Phase Action | Suggested Contract |
|--------------|-------------------|
| "Remove X" | `forbid_pattern` for X |
| "Add Y" | `require_pattern` for Y |
| "Create Z file" | `file_exists` for Z |
| "Delete W file" | `file_not_exists` for W |

### CI Integration

Run contract checks in CI pipeline:

```bash
# Check all contracts, fail on error
python -m tools.contracts check --fail-on-error

# Check with verbose output
python -m tools.contracts check --verbose

# Check specific directory
python -m tools.contracts check --root ./src
```

Exit codes:
- 0: All contracts pass
- 1: At least one error-severity contract failed
- 2: Only warning-severity contracts failed (with --fail-on-warning)

### Storage Location

Contracts are stored in `.phaser/contracts/` as YAML files:

```
.phaser/
└── contracts/
    ├── no-singleton-pattern.yaml
    ├── require-observable.yaml
    └── license-required.yaml
```

---

## Extraction Heuristics

When analyzing phase content for automatic contract suggestion:

| Pattern in Phase | Suggested Rule Type | Example |
|------------------|-------------------|---------|
| "Remove X", "Delete X", "Eliminate X" | `forbid_pattern` | "Remove .shared" → forbid `\.shared` |
| "Add Y", "Include Y", "Require Y" | `require_pattern` | "Add @Observable" → require `@Observable` |
| "Create Z file", "Add Z file" | `file_exists` | "Create LICENSE" → require LICENSE exists |
| "Delete Z file", "Remove Z file" | `file_not_exists` | "Delete .env" → require .env absent |
| "Must have X", "Should contain X" | `file_contains` | "Must have ## Usage" → require text |
| "Must not have X", "Remove X from" | `file_not_contains` | "Remove API key" → forbid text |

---

## CLI Interface

```bash
# Create a new contract
python -m tools.contracts create \
  --rule-id <id> \
  --type <type> \
  --pattern <regex> \
  --glob <glob> \
  --message <msg> \
  [--rationale <why>] \
  [--severity error|warning]

# Check all contracts
python -m tools.contracts check \
  [--root <path>] \
  [--verbose] \
  [--fail-on-error] \
  [--fail-on-warning]

# List all contracts
python -m tools.contracts list \
  [--enabled-only] \
  [--format json|table]

# Enable/disable contracts
python -m tools.contracts enable <contract-id>
python -m tools.contracts disable <contract-id>

# Show contract details
python -m tools.contracts show <contract-id>
```

---

## Edge Cases

### Large Files

- Skip files larger than 1MB for pattern matching
- Report as "skipped" rather than violation

### Binary Files

- Skip binary files for pattern matching
- Only apply `file_exists` / `file_not_exists` rules

### Encoding

- Assume UTF-8 encoding
- Files that fail to decode are skipped with warning

### Symlinks

- Follow symlinks for content checks
- Report real path in violations

### Empty Matches

- Empty pattern matches everything (validation error)
- Empty glob matches nothing (no files checked)

---

## Example Usage

### Creating a Contract from Audit

After completing Phase 3 which removed singleton patterns:

```python
from tools.contracts import create_contract, save_contract, RuleType, Severity, AuditSource
from tools.storage import PhaserStorage

storage = PhaserStorage()

source = AuditSource(
    id="abc-123",
    slug="architecture-refactor",
    date="2025-12-05",
    phase=3,
)

contract = create_contract(
    rule_id="no-singleton-pattern",
    rule_type=RuleType.FORBID_PATTERN,
    pattern=r"\.shared\b",
    file_glob="**/*.swift",
    message="Singleton pattern (.shared) is not allowed",
    rationale="Use dependency injection instead (see phase 3)",
    audit_source=source,
    severity=Severity.ERROR,
)

save_contract(contract, storage)
```

### Checking Contracts

```python
from tools.contracts import check_all_contracts, format_check_results
from tools.storage import PhaserStorage
from pathlib import Path

storage = PhaserStorage()
results = check_all_contracts(storage, Path.cwd())

print(format_check_results(results, verbose=True))

# Check for failures
errors = [r for r in results if not r.passed]
if errors:
    print(f"{len(errors)} contract(s) violated")
```

---

*Phaser v1.2 — Contract Specification*
