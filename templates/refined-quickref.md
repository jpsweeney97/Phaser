# Refined Templates — Quick Reference

## When to Use

| Template | Use Case |
|----------|----------|
| `CONTEXT_refined.md` | Production audits requiring predictable Claude Code behavior |
| `phase_template_refined.md` | Phases needing explicit verification and rollback |

---

## CONTEXT_refined.md Structure

```
<context>                    Role + objective + constraints
Metadata                     Project info, test command, timestamps
Phase Status                 Checklist with <task_orchestration>
<input_contract>             Command triggers + error handling
<reasoning_protocol>         6-step decision tree for every command
Automation Rules             Chain definitions with error propagation
<edge_cases>                 7 enumerated boundary conditions
<evaluation_suite>           6 test scenarios for validation
<examples>                   Happy path, edge, error, counter-example
```

### Key Additions Over Original

- **Explicit contracts** instead of prose descriptions
- **Reasoning protocol** Claude Code follows visibly
- **Edge cases enumerated** with specific responses
- **Evaluation suite** for testing compliance

---

## Phase Template Structure

```
Metadata Block               Risk, idempotent, estimated time, dependencies
<context>                    Role + objective + rationale
<output_schema>              Success state + constraints
<input_contract>             File manifest + preconditions
<reasoning_protocol>         Ordered steps with checkpoints
<evaluation_suite>           Typed test cases (existence, content, build)
<success_criteria>           Observable criteria linked to test cases
<rollback_procedure>         Ordered steps with verification
<contract>                   Optional: extractable rule for enforcement
```

### Key Additions Over Original

- **Metadata block** with risk level and time estimate
- **Preconditions** checked before execution
- **Checkpoints** after each plan step
- **Test case types** (existence, content_present, content_absent, build, test)
- **Criteria-to-test linking** via `verify="test_case:N"`
- **Rollback verification** to confirm clean state

---

## Testability Conversions

| Vague | Observable | Command |
|-------|------------|---------|
| "Code is clean" | Functions ≤50 lines | `awk` line count check |
| "Well documented" | Public funcs have docstrings | `grep -A1` pattern |
| "No duplication" | No identical 5+ line blocks | `jscpd` tool |
| "Tests added" | Corresponding test file exists | `test -f {path}_test.{ext}` |
| "Backward compatible" | Existing tests pass | `swift test` / `pytest` |

---

## Verification Patterns

```bash
# Existence
test -f path          # File exists
test -s path          # File exists and non-empty
test ! -f path        # File does NOT exist
test -d path          # Directory exists

# Content
grep -q "pattern" f   # Pattern present
! grep -q "pattern" f # Pattern absent
head -1 f | grep -q   # First line matches

# Counts
[ $(wc -l < f) -le N ]      # Line count ≤ N
[ $(grep -c "p" f) -eq N ]  # Exactly N matches

# Validity
python -m json.tool f       # JSON valid
python -c "import yaml..."  # YAML valid
```

---

## Idempotency Patterns

| Avoid | Use Instead |
|-------|-------------|
| `echo >> file` | `grep -q \|\| echo >>` |
| `mkdir dir` | `mkdir -p dir` |
| `sed -i 's/a/b/'` | Check with grep first |
| `git commit` | `git diff --quiet \|\|` |

---

## Edge Cases Handled

### CONTEXT Level
- no_audit_directory
- invalid_phase_number
- all_phases_complete
- archive_permission_denied
- cleanup_failed
- test_command_not_found
- phase_file_empty

### Phase Level
- phase_interrupted_mid_execution
- verification_partial_failure
- rollback_fails
- file_already_exists
- build_fails_unrelated
- test_flaky

---

## Applied Modules

| Module | CONTEXT | Phase |
|--------|:-------:|:-----:|
| orchestration | ✓ | |
| chaining | ✓ | |
| reasoning | ✓ | ✓ |
| testability | | ✓ |
| evaluation | ✓ | ✓ |
| edge_cases | ✓ | ✓ |
| examples | ✓ | ✓ |
| guardrails | ✓ | |
| refactoring | | ✓ |
| git | | ✓ |
