# Spec: Template Validation Tool

**Version:** 1.0  
**Status:** Draft  
**Date:** 2025-01-XX

---

## Summary

A CLI tool (`phaser validate`) that parses evaluation suites from refined templates and executes test cases to verify compliance. Enables automated validation of phase verifications and behavioral contract testing.

---

## Motivation

The refined templates (`CONTEXT_refined.md`, `phase_template_refined.md`) include `<evaluation_suite>` blocks with executable test cases. Without tooling to run these, they're just documentation. This tool makes them actionable:

1. **Phase verification**: Run all `## Verify` commands before marking phases complete
2. **CI integration**: Fail builds if verification tests don't pass
3. **Template validation**: Ensure templates are syntactically correct
4. **Behavioral testing**: Document and track expected Claude Code behaviors

---

## Design

### Commands

```
phaser validate suite <file>            # Run evaluation suite from any file
phaser validate phase <phase_file>      # Run phase verification commands
phaser validate context <context_file>  # List/inspect behavioral scenarios
phaser validate all <audit_dir>         # Run all validations for audit
```

### Test Case Types

| Type | Purpose | Example Command |
|------|---------|-----------------|
| `existence` | File exists | `test -f file.py` |
| `not_exists` | File deleted | `test ! -f legacy.py` |
| `content_present` | Pattern in file | `grep -q "class Foo" file.py` |
| `content_absent` | Pattern removed | `! grep -q "TODO" file.py` |
| `line_count` | Size constraint | `[ $(wc -l < file) -lt 200 ]` |
| `build` | Build succeeds | `swift build` |
| `test` | Tests pass | `pytest` |
| `no_references` | No remaining refs | `! rg -q "OldClass"` |
| `custom` | Any command | `python validate.py` |

### Data Model

```python
@dataclass
class TestCase:
    id: str
    test_type: TestType
    command: str
    description: str
    timeout: int = 30
    expected_exit_code: int = 0

@dataclass
class TestExecution:
    test_case: TestCase
    result: TestResult  # PASS, FAIL, SKIP, ERROR
    exit_code: Optional[int]
    stdout: str
    stderr: str
    duration_ms: int
    error_message: str

@dataclass
class ValidationReport:
    suite: EvaluationSuite
    executions: list[TestExecution]
    # Properties: passed, failed, skipped, errors, success, duration_ms
```

### Parsing

The tool parses two formats:

**1. XML-style evaluation suites:**

```xml
<evaluation_suite>
    <test_case id="1" type="existence">
        <command>test -f src/service.py</command>
        <description>Service file exists</description>
    </test_case>
</evaluation_suite>
```

**2. Verify sections (fallback):**

```markdown
## Verify

test -f src/service.py
grep -q "class Service" src/service.py
python -m py_compile src/service.py
```

### Execution

1. Parse test cases from file
2. Execute each command in subprocess
3. Capture exit code, stdout, stderr, duration
4. Determine PASS/FAIL based on exit code
5. Generate report

Options:
- `--fail-fast`: Stop on first failure
- `--working-dir`: Set working directory for commands
- `--timeout`: Override default 30s timeout
- `--verbose`: Show progress per test

### Output Formats

**Table (default):**
```
ID       Type             Result   Time     Description
----------------------------------------------------------------------
1        existence        PASS     12ms     Service file exists
2        content_present  FAIL     8ms      Contains class definition
         └─ Expected exit code 0, got 1
```

**JSON:**
```json
{
  "success": false,
  "summary": {"total": 2, "passed": 1, "failed": 1},
  "test_cases": [...]
}
```

**Markdown:** Full report with failure details section.

---

## Integration

### With Existing CLI

Add to `cli.py`:

```python
from tools.validate import cli as validate_cli
cli.add_command(validate_cli, name="validate")
```

### With CI

```yaml
# .github/workflows/audit.yml
- name: Validate phase verifications
  run: phaser validate all .audit/ --format json
```

### With Phase Execution

Claude Code can invoke validation before marking phases complete:

```python
# In phase execution logic
result = subprocess.run(["phaser", "validate", "phase", phase_file])
if result.returncode != 0:
    # Phase verification failed
```

---

## Files

| File | Purpose |
|------|---------|
| `tools/validate.py` | Main module |
| `tests/test_validate.py` | Tests |
| `specs/validate.md` | This spec |

---

## Usage Examples

### Validate a Phase File

```bash
$ phaser validate phase .audit/phases/02-extract-validation.md -v

Running 5 verification(s) for 02-extract-validation.md

  Running: config_exists - Config file exists... ✓
  Running: service_created - Service file exists... ✓
  Running: content_valid - Contains expected class... ✓
  Running: build_passes - Build succeeds... ✓
  Running: tests_pass - All tests pass... ✓

======================================================================
Status: PASSED
Results: 5 passed, 0 failed, 0 skipped, 0 errors
Duration: 2341ms
```

### List CONTEXT Scenarios

```bash
$ phaser validate context .audit/CONTEXT.md --list

Scenarios in CONTEXT.md:

  happy_path           happy_path   User executes 3-phase audit with no failures
  skip_middle          edge         User skips phase 2 of 3
  all_skipped          edge         User skips all phases
  retry_success        edge         Phase fails verification, fix succeeds on retry
  max_retries          adversarial  Phase fails all 3 retry attempts
  stale_audit          edge         Audit inactive for 10 days
```

### Validate All (CI Mode)

```bash
$ phaser validate all .audit/ --format json

{
  "success": true,
  "summary": {"total": 23, "passed": 23, "failed": 0},
  "files_validated": 4
}
```

---

## Future Work

1. **Watch mode**: Re-run validations on file changes
2. **Coverage tracking**: Which acceptance criteria have linked tests
3. **Behavioral simulation**: Simulate user commands and check Claude Code responses
4. **Flaky test detection**: Retry tests that fail inconsistently
5. **Parallel execution**: Run independent tests concurrently

---

## References

- `templates/CONTEXT_refined.md` — Uses `<evaluation_suite>` for behavioral specs
- `templates/phase_template_refined.md` — Uses `<evaluation_suite>` for verifications
- `/mnt/skills/user/prompt-refining/references/modules-quality.md` — Evaluation module
