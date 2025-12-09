# Phase File Template (Refined)

> **Refined using prompt-refining skill**: Explicit contracts, reasoning protocol, testability patterns.
>
> Replaces phase_template.md for production audits.

---

## Template

```markdown
# Phase {N}: {Title}

<!--
PHASE METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Risk: low | medium | high
Idempotent: yes | no
Estimated: {X} minutes
Dependencies: {phase numbers or "none"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-->

<context>
    <role>Code modification executor for Claude Code</role>
    <objective>{Single sentence: what this phase accomplishes}</objective>
    <rationale>{Why this change matters — reference audit finding}</rationale>
</context>

---

## Goal

<output_schema>
    <success_state>{Exact measurable outcome}</success_state>
    <constraints>
        - {Constraint 1: e.g., "No new dependencies"}
        - {Constraint 2: e.g., "Maintain backward compatibility"}
    </constraints>
</output_schema>

---

## Files

<input_contract>
    <file_manifest>
        | Path | Operation | Purpose |
        |------|-----------|---------|
        | `{path/to/file}` | create | {why} |
        | `{path/to/file}` | modify | {why} |
        | `{path/to/file}` | delete | {why} |
    </file_manifest>
    <preconditions>
        - {File X must exist}
        - {Directory Y must be writable}
        - {Build must be passing before starting}
    </preconditions>
</input_contract>

---

## Plan

<reasoning_protocol visibility="visible">
    <step order="1" name="explore">
        **Understand current state**
        ```bash
        {Commands to examine existing code}
        ```
        <checkpoint>Confirm: {what you should see}</checkpoint>
    </step>
    
    <step order="2" name="modify" depends_on="1">
        **Make changes**
        
        {Detailed instructions with code examples}
        
        ```{language}
        {Code to add/modify}
        ```
        
        <checkpoint>Confirm: {file now contains X}</checkpoint>
    </step>
    
    <step order="3" name="cascade" depends_on="2">
        **Update related files**
        
        {Instructions for imports, references, tests}
        
        <checkpoint>Confirm: {no broken references}</checkpoint>
    </step>
    
    <step order="4" name="verify" depends_on="3">
        **Run verification**
        ```bash
        {build_command}
        {test_command}
        ```
        <checkpoint>Confirm: all commands exit 0</checkpoint>
    </step>
</reasoning_protocol>

---

## Verify

<evaluation_suite>
    <test_case id="1" type="existence">
        <command>test -f {path/to/created/file}</command>
        <description>Created file exists</description>
    </test_case>
    
    <test_case id="2" type="content_present">
        <command>grep -q "{expected pattern}" {path/to/file}</command>
        <description>File contains expected content</description>
    </test_case>
    
    <test_case id="3" type="content_absent">
        <command>! grep -q "{removed pattern}" {path/to/file}</command>
        <description>Removed content is gone</description>
    </test_case>
    
    <test_case id="4" type="build">
        <command>{build_command}</command>
        <description>Project builds successfully</description>
    </test_case>
    
    <test_case id="5" type="test">
        <command>{test_command}</command>
        <description>All tests pass</description>
    </test_case>
</evaluation_suite>

**Execution rule:** All test cases must pass (exit 0). First failure halts verification.

---

## Acceptance Criteria

<success_criteria type="observable">
    <!-- Convert vague criteria to testable properties -->
    
    <criterion name="file_created" verify="test_case:1">
        {New file path} exists and is non-empty
    </criterion>
    
    <criterion name="content_correct" verify="test_case:2">
        File contains {specific pattern/class/function}
    </criterion>
    
    <criterion name="old_removed" verify="test_case:3">
        {Old pattern/code} no longer present in {file}
    </criterion>
    
    <criterion name="builds" verify="test_case:4">
        Build succeeds with no new warnings
    </criterion>
    
    <criterion name="tests_pass" verify="test_case:5">
        All existing tests pass, no regressions
    </criterion>
</success_criteria>

---

## Rollback

<rollback_procedure on_trigger="verification_failure OR user_request">
    <step order="1">
        ```bash
        git checkout -- {paths/to/modified/files}
        ```
    </step>
    
    <step order="2">
        ```bash
        rm -f {paths/to/created/files}
        ```
    </step>
    
    <step order="3">
        ```bash
        git checkout -- {paths/to/deleted/files}  # If deleted
        ```
    </step>
    
    <verification>
        ```bash
        git status --porcelain  # Should show no changes
        {build_command}         # Should pass
        ```
    </verification>
</rollback_procedure>

---

## Contract (Optional)

<contract rule_id="{descriptive-id}">
    <type>forbid_pattern | require_pattern | file_exists | file_contains</type>
    <pattern>{regex pattern}</pattern>
    <file_glob>{**/*.ext}</file_glob>
    <severity>error | warning</severity>
    <message>{Human-readable violation message}</message>
    <rationale>{Why this rule exists going forward}</rationale>
</contract>

---
```

---

## Schema Reference

### Required Sections

<input_contract>
    <required_sections>
        | Section | Purpose | Validation |
        |---------|---------|------------|
        | `# Phase N: Title` | Identify phase | Regex: `^# Phase \d+:` |
        | `## Goal` | Single success criterion | Contains `<output_schema>` or paragraph |
        | `## Files` | What will be touched | Contains `<file_manifest>` table |
        | `## Plan` | Step-by-step instructions | Contains `<reasoning_protocol>` or numbered steps |
        | `## Verify` | Machine-executable checks | Contains `<evaluation_suite>` or bash commands |
        | `## Acceptance Criteria` | Human-readable checklist | Contains `<success_criteria>` or checkbox list |
        | `## Rollback` | How to undo | Contains `<rollback_procedure>` or bash commands |
    </required_sections>
    
    <error_handling>
        <case trigger="missing_section">
            Report: "Phase file malformed: missing ## {Section}"
            Action: HALT, do not execute
        </case>
        <case trigger="empty_section">
            Report: "Phase file incomplete: ## {Section} is empty"
            Action: HALT, do not execute
        </case>
    </error_handling>
</input_contract>

### Optional Sections

| Section | Purpose |
|---------|---------|
| `## Note` | Special instructions or warnings |
| `## Dependencies` | Other phases that must complete first |
| `## Contract` | Extractable rule for ongoing enforcement |

---

## Testability Guide

Converting vague criteria to observable properties:

<testability_conversions>
    | Vague Criterion | Observable Property | Verification Command |
    |-----------------|--------------------|--------------------|
    | "Code is clean" | No functions > 50 lines | `awk '/^func/{c=0} {c++} c>50{exit 1}' file` |
    | "Well documented" | All public functions have docstrings | `grep -A1 "^func " file \| grep -q "///"` |
    | "No duplication" | No identical 5+ line blocks | Use `jscpd` or similar tool |
    | "Properly typed" | No `any` type annotations | `! grep -q ": any" file` |
    | "Error handling" | All throwing calls wrapped | `grep -c "try" >= grep -c "throw"` |
    | "Tests added" | New file has corresponding test | `test -f {path}_test.{ext}` |
    | "Backward compatible" | Existing tests unchanged and pass | `git diff --name-only \| grep -v _test` |
</testability_conversions>

### Verification Patterns

```bash
# Content exists
grep -q "pattern" file

# Content removed
! grep -q "pattern" file

# File exists
test -f path/to/file

# File exists and non-empty
test -s path/to/file

# File does not exist (for deletions)
test ! -f path/to/file

# First line matches
head -1 file | grep -q "pattern"

# Line count in range
[ $(wc -l < file) -le 200 ]

# No matches (count is zero)
[ $(grep -c "pattern" file) -eq 0 ]

# Exact match count
[ $(grep -c "pattern" file) -eq 3 ]

# JSON valid
python -m json.tool file > /dev/null

# YAML valid
python -c "import yaml; yaml.safe_load(open('file'))"
```

---

## Idempotency Patterns

Phases should be safe to run twice. Use these patterns:

<idempotency_patterns>
    | Instead of... | Use... |
    |---------------|--------|
    | `echo "line" >> file` | `grep -q "line" file \|\| echo "line" >> file` |
    | `mkdir dir` | `mkdir -p dir` |
    | `touch file` | `touch file` (already idempotent) |
    | `sed -i 's/a/b/' file` | Check first: `grep -q "a" file && sed -i 's/a/b/' file` |
    | `git commit -m "msg"` | `git diff --quiet \|\| git commit -m "msg"` |
    | Append import | Check if import exists first |
</idempotency_patterns>

---

## Edge Cases

<edge_cases>
    <case trigger="phase_interrupted_mid_execution">
        State: Some files modified, others not
        Recovery: Rollback procedure must restore clean state
        Prevention: Order operations to fail early, succeed atomically
    </case>
    
    <case trigger="verification_partial_failure">
        State: Some verifications pass, one fails
        Recovery: Report which verification failed, suggest fix
        Action: Do NOT mark phase complete
    </case>
    
    <case trigger="rollback_fails">
        State: Cannot restore original state
        Recovery: Report failure, preserve current state for manual intervention
        Action: User must manually restore via git
    </case>
    
    <case trigger="file_already_exists">
        State: Phase creates file that already exists
        Prevention: Check existence in preconditions
        Action: Either skip creation or error based on phase design
    </case>
    
    <case trigger="build_fails_unrelated">
        State: Build fails for reason unrelated to this phase
        Detection: Compare error to phase scope
        Action: Report that failure appears unrelated, suggest checking base state
    </case>
    
    <case trigger="test_flaky">
        State: Test passes sometimes, fails sometimes
        Detection: Same test fails on retry without code change
        Action: Flag as potential flaky test, retry up to 2 times
    </case>
</edge_cases>

---

## Examples

### Example 1: Good Phase File (Happy Path)

```markdown
# Phase 2: Extract Validation Logic

<!--
PHASE METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Risk: medium
Idempotent: yes
Estimated: 15 minutes
Dependencies: 1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-->

<context>
    <role>Code modification executor for Claude Code</role>
    <objective>Move validation methods from ConversationView to ValidationService</objective>
    <rationale>Audit finding: ConversationView.swift at 487 lines exceeds 200-line threshold. Validation logic (120 lines) is self-contained and reusable.</rationale>
</context>

---

## Goal

<output_schema>
    <success_state>ValidationService.swift exists with all validation methods; ConversationView.swift reduced to under 400 lines</success_state>
    <constraints>
        - No new external dependencies
        - All existing tests must pass unchanged
        - ValidationService must be injectable for testing
    </constraints>
</output_schema>

---

## Files

<input_contract>
    <file_manifest>
        | Path | Operation | Purpose |
        |------|-----------|---------|
        | `Sources/Services/ValidationService.swift` | create | New service with extracted validation logic |
        | `Sources/Views/ConversationView.swift` | modify | Remove validation methods, add service dependency |
        | `Sources/App/DependencyContainer.swift` | modify | Register ValidationService |
    </file_manifest>
    <preconditions>
        - ConversationView.swift exists and contains `validateInput` method
        - DependencyContainer.swift exists
        - `swift build` passes before starting
    </preconditions>
</input_contract>

---

## Plan

<reasoning_protocol visibility="visible">
    <step order="1" name="explore">
        **Understand current state**
        ```bash
        wc -l Sources/Views/ConversationView.swift
        grep -n "func validate" Sources/Views/ConversationView.swift
        ```
        <checkpoint>Confirm: File is ~487 lines, validation methods around lines 250-370</checkpoint>
    </step>
    
    <step order="2" name="create_service" depends_on="1">
        **Create ValidationService**
        
        Create `Sources/Services/ValidationService.swift`:
        
        ```swift
        import Foundation
        
        protocol ValidationServiceProtocol {
            func validateInput(_ text: String) -> ValidationResult
            func validateLength(_ text: String, max: Int) -> Bool
        }
        
        final class ValidationService: ValidationServiceProtocol {
            // Move validation methods here
        }
        ```
        
        <checkpoint>Confirm: File created with protocol and class stub</checkpoint>
    </step>
    
    <step order="3" name="extract_methods" depends_on="2">
        **Move validation methods**
        
        Cut these methods from ConversationView.swift:
        - `validateInput(_:)`
        - `validateLength(_:max:)`
        - `ValidationResult` enum
        
        Paste into ValidationService.swift implementation.
        
        <checkpoint>Confirm: Methods moved, ConversationView no longer contains them</checkpoint>
    </step>
    
    <step order="4" name="wire_dependency" depends_on="3">
        **Update ConversationView to use service**
        
        Add property:
        ```swift
        private let validationService: ValidationServiceProtocol
        ```
        
        Update init to accept service. Replace direct calls with service calls.
        
        <checkpoint>Confirm: ConversationView compiles with service dependency</checkpoint>
    </step>
    
    <step order="5" name="register" depends_on="4">
        **Register in DependencyContainer**
        
        Add to DependencyContainer.swift:
        ```swift
        container.register(ValidationServiceProtocol.self) { _ in
            ValidationService()
        }
        ```
        
        <checkpoint>Confirm: Service registered</checkpoint>
    </step>
    
    <step order="6" name="verify" depends_on="5">
        **Run verification**
        ```bash
        swift build
        swift test
        ```
        <checkpoint>Confirm: All commands exit 0</checkpoint>
    </step>
</reasoning_protocol>

---

## Verify

<evaluation_suite>
    <test_case id="1" type="existence">
        <command>test -s Sources/Services/ValidationService.swift</command>
        <description>ValidationService.swift exists and non-empty</description>
    </test_case>
    
    <test_case id="2" type="content_present">
        <command>grep -q "protocol ValidationServiceProtocol" Sources/Services/ValidationService.swift</command>
        <description>Protocol defined</description>
    </test_case>
    
    <test_case id="3" type="content_present">
        <command>grep -q "func validateInput" Sources/Services/ValidationService.swift</command>
        <description>validateInput method in service</description>
    </test_case>
    
    <test_case id="4" type="content_absent">
        <command>! grep -q "func validateInput" Sources/Views/ConversationView.swift</command>
        <description>validateInput removed from view</description>
    </test_case>
    
    <test_case id="5" type="line_count">
        <command>[ $(wc -l < Sources/Views/ConversationView.swift) -lt 400 ]</command>
        <description>ConversationView under 400 lines</description>
    </test_case>
    
    <test_case id="6" type="build">
        <command>swift build 2>&1 | grep -v warning || true</command>
        <description>Build succeeds</description>
    </test_case>
    
    <test_case id="7" type="test">
        <command>swift test</command>
        <description>All tests pass</description>
    </test_case>
</evaluation_suite>

---

## Acceptance Criteria

<success_criteria type="observable">
    <criterion name="service_exists" verify="test_case:1,2">
        ValidationService.swift exists with ValidationServiceProtocol
    </criterion>
    
    <criterion name="methods_moved" verify="test_case:3,4">
        Validation methods in service, not in view
    </criterion>
    
    <criterion name="view_smaller" verify="test_case:5">
        ConversationView.swift under 400 lines
    </criterion>
    
    <criterion name="builds" verify="test_case:6">
        Build succeeds with no new warnings
    </criterion>
    
    <criterion name="tests_pass" verify="test_case:7">
        All tests pass, no regressions
    </criterion>
</success_criteria>

---

## Rollback

<rollback_procedure on_trigger="verification_failure OR user_request">
    <step order="1">
        ```bash
        git checkout -- Sources/Views/ConversationView.swift
        git checkout -- Sources/App/DependencyContainer.swift
        ```
    </step>
    
    <step order="2">
        ```bash
        rm -f Sources/Services/ValidationService.swift
        ```
    </step>
    
    <verification>
        ```bash
        git status --porcelain
        swift build
        ```
    </verification>
</rollback_procedure>

---

## Contract

<contract rule_id="validation-service-exists">
    <type>file_exists</type>
    <pattern>Sources/Services/ValidationService.swift</pattern>
    <severity>error</severity>
    <message>ValidationService.swift must exist — validation logic should not be in views</message>
    <rationale>Keeps views focused on presentation, validation logic reusable and testable</rationale>
</contract>
```

---

### Example 2: Counter-Example (Bad Phase File)

```markdown
# Phase 2: Fix validation

## Goal

Make validation better.

## Files

- Some files

## Plan

1. Fix the validation code
2. Make sure it works

## Verify

Run tests

## Acceptance Criteria

- [ ] Code works
- [ ] Tests pass

## Rollback

Undo changes
```

**Why this is wrong:**

| Issue | Problem | Fix |
|-------|---------|-----|
| Vague goal | "Make validation better" is not measurable | Specify exact outcome: "Extract to service, reduce file to <400 lines" |
| No file manifest | "Some files" tells Claude Code nothing | List every file with operation type |
| No commands | "Fix the validation code" is not executable | Provide exact commands and code |
| Untestable verify | "Run tests" is ambiguous | Provide exact command: `swift test` |
| Vague criteria | "Code works" cannot be verified | Convert to observable: "grep -q 'pattern' file" |
| Incomplete rollback | "Undo changes" is not actionable | Provide exact git/rm commands |

---

### Example 3: Edge Case Phase (Delete Operation)

```markdown
# Phase 5: Remove Deprecated Helper

<!--
PHASE METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Risk: low
Idempotent: yes
Estimated: 5 minutes
Dependencies: 3, 4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-->

<context>
    <objective>Delete LegacyHelper.swift after migration to new utilities</objective>
    <rationale>Phases 3-4 migrated all callers. File is now dead code.</rationale>
</context>

## Goal

<output_schema>
    <success_state>LegacyHelper.swift deleted; no references remain in codebase</success_state>
</output_schema>

## Files

<input_contract>
    <file_manifest>
        | Path | Operation | Purpose |
        |------|-----------|---------|
        | `Sources/Helpers/LegacyHelper.swift` | delete | Remove deprecated file |
    </file_manifest>
    <preconditions>
        - No files import or reference LegacyHelper
        - Phases 3-4 completed successfully
    </preconditions>
</input_contract>

## Plan

<reasoning_protocol>
    <step order="1" name="verify_no_references">
        ```bash
        rg "LegacyHelper" --type swift
        ```
        <checkpoint>Confirm: No matches (or only the file itself)</checkpoint>
    </step>
    
    <step order="2" name="delete" depends_on="1">
        ```bash
        rm Sources/Helpers/LegacyHelper.swift
        ```
    </step>
    
    <step order="3" name="verify" depends_on="2">
        ```bash
        swift build
        swift test
        ```
    </step>
</reasoning_protocol>

## Verify

<evaluation_suite>
    <test_case id="1" type="not_exists">
        <command>test ! -f Sources/Helpers/LegacyHelper.swift</command>
        <description>File deleted</description>
    </test_case>
    
    <test_case id="2" type="no_references">
        <command>! rg -q "LegacyHelper" --type swift</command>
        <description>No remaining references</description>
    </test_case>
    
    <test_case id="3" type="build">
        <command>swift build</command>
    </test_case>
</evaluation_suite>

## Acceptance Criteria

<success_criteria type="observable">
    <criterion name="deleted" verify="test_case:1">
        LegacyHelper.swift no longer exists
    </criterion>
    <criterion name="no_orphan_refs" verify="test_case:2">
        No code references LegacyHelper
    </criterion>
    <criterion name="builds" verify="test_case:3">
        Project still builds
    </criterion>
</success_criteria>

## Rollback

<rollback_procedure>
    <step order="1">
        ```bash
        git checkout -- Sources/Helpers/LegacyHelper.swift
        ```
    </step>
</rollback_procedure>
```

---

## Risk Levels

| Risk | Meaning | Examples | Extra Precautions |
|------|---------|----------|-------------------|
| **low** | Safe, isolated | Add docs, extract constants, delete dead code | Standard verification |
| **medium** | Refactors, new patterns | Extract services, add protocols, caching | Additional integration tests |
| **high** | Architectural | Refactor core services, change DI, migrations | Backup, staged rollout, extra review |

Order phases low → high risk within audits.

---

## Modules Applied

| Module | Application |
|--------|-------------|
| `reasoning` | `<reasoning_protocol>` with ordered steps and checkpoints |
| `testability` | Conversion table for vague → observable criteria |
| `evaluation` | `<evaluation_suite>` with typed test cases |
| `edge_cases` | Enumerated failure modes with recovery |
| `code_review` | Severity levels in findings |
| `refactoring` | Before/after verification pattern |
| `git` | Rollback commands and idempotency |
