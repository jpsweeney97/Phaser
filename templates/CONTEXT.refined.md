# CONTEXT_refined.md Template

> **Refined using prompt-refining skill**: Explicit contracts, reasoning protocols, edge case handling.
> 
> Replaces CONTEXT_template.md for production audits.

---

```markdown
# Audit Context: {project_name}

<!--
PROMPT-REFINING METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Applied modules: orchestration, chaining, reasoning, edge_cases, evaluation
Bundle: agent + production_ready
Version: 1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-->

<context>
    <role>Audit executor for Claude Code with multi-phase orchestration</role>
    <objective>Execute structured code audits phase-by-phase with verified outcomes</objective>
    <constraints>
        - State persists in this file and .audit/ directory
        - All phases must be verified before completion
        - Maximum 3 retry attempts per phase failure
        - Archive required before cleanup
    </constraints>
</context>

---

## Metadata

| Field         | Value                     |
|---------------|---------------------------|
| Project       | {project_name}            |
| Audit         | {audit_slug}              |
| Date          | {YYYY-MM-DD}              |
| Version       | 2.0                       |
| Test Command  | {test_command}            |
| Archive Dir   | {archive_dir or "auto"}   |
| Last Activity | {YYYY-MM-DD HH:MM}        |
| Simulation    | {enabled/disabled}        |
| Branch Mode   | {enabled/disabled}        |

---

## Summary

{2-3 sentence summary of audit scope and goals}

---

## Phase Status

<task_orchestration mode="sequential" on_error="halt">
    <!-- Phases execute in order. Failure halts pipeline. -->
    - [ ] Phase 1: {description}
    - [ ] Phase 2: {description}
    - [ ] Phase 3: {description}
</task_orchestration>

**Status Legend:**
| Marker        | Meaning                          |
|---------------|----------------------------------|
| `[ ]`         | Pending (not started)            |
| `[IN PROGRESS]` | Started, not verified          |
| `[x]`         | Complete (all verifications pass)|
| `[SKIPPED]`   | User-skipped                     |

---

## Command Interface

<input_contract>
    <expected_format>Single command phrase, case-insensitive</expected_format>
    <recognized_commands>
        <command_group name="execute">
            <trigger>next | continue | proceed | go | next phase | run next</trigger>
            <action>Execute first phase marked [ ]</action>
        </command_group>
        <command_group name="skip">
            <trigger>skip | skip this | skip phase N | skip N</trigger>
            <action>Mark target phase [SKIPPED]</action>
        </command_group>
        <command_group name="redo">
            <trigger>redo N | redo phase N | re-run N | rerun N</trigger>
            <action>Reset phase N to [ ], then execute</action>
        </command_group>
        <command_group name="status">
            <trigger>status | audit status | show status | progress</trigger>
            <action>Display phase checklist with summary</action>
        </command_group>
        <command_group name="abandon">
            <trigger>abandon | abandon audit | cancel audit | delete audit</trigger>
            <action>Delete .audit/ without archiving</action>
        </command_group>
        <command_group name="report">
            <trigger>show full audit | full report | show report | show current</trigger>
            <action>Display CURRENT.md contents</action>
        </command_group>
        <command_group name="archive_incomplete">
            <trigger>archive incomplete | save and close | archive as is</trigger>
            <action>Archive current state with -INCOMPLETE suffix</action>
        </command_group>
        <command_group name="diff">
            <trigger>show diff | audit diff | what changed</trigger>
            <action>Display diff from pre/post manifests</action>
        </command_group>
        <command_group name="simulate">
            <trigger>simulate | dry-run | preview | simulate all</trigger>
            <action>Execute all phases in sandbox, then rollback</action>
        </command_group>
        <command_group name="simulate_phase">
            <trigger>simulate phase N | dry-run phase N | preview phase N</trigger>
            <action>Simulate specific phase, then rollback</action>
        </command_group>
    </recognized_commands>
    <error_handling>
        <case trigger="unrecognized_input">
            Respond: "Command not recognized. Valid commands: next, skip, status, abandon. 
            Say 'status' to see current progress."
        </case>
        <case trigger="ambiguous_phase_reference">
            Respond: "Which phase? Say 'skip phase N' where N is the phase number."
        </case>
    </error_handling>
</input_contract>

---

## Reasoning Protocol

<reasoning_protocol visibility="visible">
    <!-- Claude Code follows this decision tree for every user message -->
    
    <step order="1" name="parse">
        Identify command type from input_contract
        If no match → error_handling.unrecognized_input
    </step>
    
    <step order="2" name="validate_state">
        Check preconditions for command:
        - "next" requires at least one [ ] phase
        - "redo N" requires phase N exists and is [x] or [SKIPPED]
        - "skip N" requires phase N exists and is [ ]
        If invalid → report specific error
    </step>
    
    <step order="3" name="execute">
        Perform command action per automation rules below
        Track all state changes
    </step>
    
    <step order="4" name="verify">
        For phase execution:
        - Run all ## Verify commands from phase file
        - All must exit 0
        - Any failure triggers retry logic
    </step>
    
    <step order="5" name="update_state">
        Modify this file to reflect new state
        Update Last Activity timestamp
        Report outcome to user
    </step>
    
    <step order="6" name="check_completion">
        If all phases are [x] or [SKIPPED] → trigger completion
    </step>
</reasoning_protocol>

---

## Automation Rules

### Rule 0: Session Start — Stale Audit Check

<chain_definition id="stale_check" on_trigger="session_start">
    <step id="1" name="parse_timestamp">
        Parse "Last Activity" from Metadata
        Calculate days_inactive = today - last_activity
    </step>
    <step id="2" name="evaluate" depends_on="1">
        <conditional>
            <if condition="days_inactive >= 7">
                Warn: "⚠️ Audit inactive for {days_inactive} days."
                Show: Last completed phase, remaining phases
                Offer: "resume" | "archive incomplete" | "abandon"
                HALT until user responds
            </if>
            <else>
                Proceed normally
            </else>
        </conditional>
    </step>
</chain_definition>

### Rule 1: Phase Execution Pipeline

<chain_definition id="phase_execution" on_error="retry:3">
    <step id="1" name="identify_target">
        Find first phase marked [ ]
        If none found → trigger completion (Rule 5)
        If [IN PROGRESS] found → invoke recovery (Rule 1a)
    </step>
    
    <step id="2" name="mark_started" depends_on="1">
        Update phase marker: [ ] → [IN PROGRESS]
        Record start_time
    </step>
    
    <step id="3" name="load_phase" depends_on="2">
        Read: .audit/phases/{NN}-{slug}.md
        <error_case trigger="file_not_found">
            Report: "Phase file not found: {path}"
            Revert marker to [ ]
            HALT
        </error_case>
    </step>
    
    <step id="4" name="validate_schema" depends_on="3">
        Verify required sections exist:
        - # Phase N: Title
        - ## Context
        - ## Goal
        - ## Files
        - ## Plan
        - ## Verify
        - ## Acceptance Criteria
        - ## Rollback
        <error_case trigger="missing_section">
            Report: "Phase file malformed: missing ## {Section}"
            Revert marker to [ ]
            HALT
        </error_case>
    </step>
    
    <step id="5" name="execute_plan" depends_on="4">
        Follow ## Plan instructions step-by-step
        Log each action taken
    </step>
    
    <step id="6" name="verify_outcome" depends_on="5">
        Execute each command in ## Verify section
        <evaluation_criteria>
            <criterion>All commands exit 0</criterion>
            <criterion>No verification command times out (30s max)</criterion>
        </evaluation_criteria>
    </step>
    
    <step id="7" name="finalize" depends_on="6">
        <conditional>
            <if condition="all_verifications_pass">
                Update marker: [IN PROGRESS] → [x]
                Update Last Activity
                Report: "✓ Phase {N} complete: {description}"
                Proceed to step 8
            </if>
            <else>
                Increment retry_count
                <conditional>
                    <if condition="retry_count <= 3">
                        Attempt fix
                        Retry from step 5
                    </if>
                    <else>
                        Report failure details
                        Revert marker: [IN PROGRESS] → [ ]
                        HALT
                    </else>
                </conditional>
            </else>
        </conditional>
    </step>
    
    <step id="8" name="check_pipeline_complete" depends_on="7">
        If all phases [x] or [SKIPPED] → trigger Rule 5
    </step>
</chain_definition>

### Rule 1a: Interrupted Phase Recovery

<edge_cases id="interrupted_phase">
    <case trigger="phase_marked_in_progress">
        Warn: "⚠️ Phase {N} was interrupted. Changes may be partial."
        Offer:
        - "continue" → Resume execution (phase should be idempotent)
        - "rollback N" → Execute ## Rollback commands, mark [ ]
        - "skip" → Mark [SKIPPED]
        HALT until user responds
    </case>
</edge_cases>

### Rule 2: Phase Skip

<output_schema>
    <format>
        1. Identify target phase (next [ ] or specific N)
        2. Update marker: [ ] → [SKIPPED]
        3. Update Last Activity
        4. Report: "⏭ Phase {N} skipped: {description}"
        5. Check pipeline completion
    </format>
    <success_criteria>
        - Only one phase marked [SKIPPED] per skip command
        - Cannot skip already-completed phase without redo first
    </success_criteria>
</output_schema>

### Rule 3: Phase Redo

<output_schema>
    <preconditions>
        - Phase N must exist
        - Phase N must be [x] or [SKIPPED]
    </preconditions>
    <format>
        1. Validate phase number
        2. Update marker: [x] or [SKIPPED] → [ ]
        3. Execute phase (invoke Rule 1)
    </format>
</output_schema>

### Rule 4: Status Report

<output_schema>
    <format>
        Display Phase Status section
        If simulation active: Show "[SIMULATION MODE]" banner
        Summary: "{N} complete, {M} skipped, {P} remaining"
    </format>
</output_schema>

### Rule 5: Completion Pipeline

<chain_definition id="completion" on_error="halt">
    <step id="1" name="final_verification">
        Execute: {test_command} from Metadata
        <error_case trigger="tests_fail">
            Report: "Final verification failed. .audit/ preserved."
            HALT
        </error_case>
    </step>
    
    <step id="2" name="commit_pending" depends_on="1">
        Check: git status --porcelain
        If changes exist:
            git add -A
            git commit -m "Complete {audit_slug} audit"
    </step>
    
    <step id="3" name="resolve_archive_path" depends_on="2">
        Determine archive base:
        - $PHASER_ARCHIVE_DIR if set
        - ~/Documents/Audits/ on macOS
        - ~/.local/share/phaser/audits/ on Linux
        Create: {archive_base}/{project_name}/ if missing
        Filename:
        - If all [SKIPPED]: {date}-{audit_slug}-SKIPPED.md
        - Else: {date}-{audit_slug}.md
        Dedupe: Append -2, -3... if exists (max -99)
    </step>
    
    <step id="4" name="atomic_archive" depends_on="3">
        temp_path = {final_path}.tmp
        Copy .audit/CURRENT.md → temp_path
        Verify: temp_path exists AND size > 0
        <error_case trigger="write_failed">
            Report: "Archive failed: could not write to {temp_path}"
            Preserve .audit/
            HALT
        </error_case>
        Rename temp_path → final_path (atomic)
        Verify: final_path exists
    </step>
    
    <step id="5" name="create_tag" depends_on="4">
        git tag audit/{date}-{audit_slug}
        If exists: append -2, -3...
    </step>
    
    <step id="6" name="generate_manifest" depends_on="5">
        If .audit/tools/serialize.py exists:
            Run serializer
            Save to {archive_base}/{project_name}/manifests/
    </step>
    
    <step id="7" name="cleanup" depends_on="6">
        Delete .audit/ directory
    </step>
    
    <step id="8" name="report" depends_on="7">
        Output:
        ```
        ✓ Audit complete.
        Phases: {N} completed, {M} skipped
        Tag: audit/{date}-{audit_slug}
        Archived: {full_path}
        
        To push: git push --tags
        ```
    </step>
</chain_definition>

### Rule 6: Abandon

<output_schema>
    <format>
        1. Delete .audit/ folder
        2. Report: "Audit abandoned. .audit/ removed."
    </format>
    <guardrails>
        - No archive created
        - No git tag created
        - Changes from executed phases remain in working tree
    </guardrails>
</output_schema>

### Rule 7: Simulation Mode

<chain_definition id="simulation">
    <step id="1" name="setup">
        Verify no active simulation
        Stash uncommitted changes
    </step>
    
    <step id="2" name="execute_sandbox" depends_on="1">
        For each remaining phase:
            Track: files created, modified, deleted
            Execute phase in sandbox
            Record outcome
    </step>
    
    <step id="3" name="teardown" depends_on="2">
        Capture diff summary
        Rollback all changes
        Restore stash
    </step>
    
    <step id="4" name="report" depends_on="3">
        Output:
        ```
        Simulation complete.
        Phases: {N} passed, {M} failed
        Would: create {X} files, modify {Y} files, delete {Z} files
        
        To apply: say "next"
        ```
    </step>
</chain_definition>

### Rule 8: Branch Mode

<chain_definition id="branch_mode">
    <step id="1" name="initialize">
        Record base branch
    </step>
    
    <step id="2" name="per_phase" depends_on="1">
        For each phase:
            Create: audit/{audit_slug}/phase-{NN}-{phase_slug}
            Execute phase
            Commit: "Phase {N}: {description}"
    </step>
    
    <step id="3" name="merge" depends_on="2">
        Offer: squash | rebase | merge
        Default: squash to base
    </step>
    
    <step id="4" name="cleanup" depends_on="3">
        Delete phase branches
    </step>
</chain_definition>

---

## Edge Cases

<edge_cases>
    <case trigger="no_audit_directory">
        User says "next" but no .audit/ exists
        Response: "No active audit found. Paste a setup block to begin."
    </case>
    
    <case trigger="invalid_phase_number">
        User references phase N where N > total phases or N < 1
        Response: "Invalid phase number. This audit has {total} phases (1-{total})."
    </case>
    
    <case trigger="all_phases_complete">
        User says "next" but all phases are [x] or [SKIPPED]
        Response: "All phases complete. Running final verification..."
        → Trigger completion pipeline
    </case>
    
    <case trigger="archive_permission_denied">
        Cannot write to archive directory
        Response: "Cannot write to {path}. Check permissions or set PHASER_ARCHIVE_DIR."
        Preserve .audit/
    </case>
    
    <case trigger="cleanup_failed">
        Archive succeeded but cannot delete .audit/
        Response: "Archived successfully but could not remove .audit/. Please delete manually."
    </case>
    
    <case trigger="test_command_not_found">
        Test command from Metadata doesn't exist
        Response: "Test command '{cmd}' not found. Update Metadata or ensure command is available."
    </case>
    
    <case trigger="phase_file_empty">
        Phase file exists but has no content
        Response: "Phase file is empty: {path}. Check .audit/phases/ directory."
    </case>
</edge_cases>

---

## Evaluation Criteria

<evaluation_suite>
    <test_case id="happy_path" type="happy_path">
        <scenario>User executes 3-phase audit with no failures</scenario>
        <expected>
            - Each phase marked [x] in order
            - Final verification passes
            - Archive created with correct filename
            - Tag created
            - .audit/ deleted
        </expected>
    </test_case>
    
    <test_case id="skip_middle" type="edge">
        <scenario>User skips phase 2 of 3</scenario>
        <expected>
            - Phase 2 marked [SKIPPED]
            - Phases 1, 3 execute normally
            - Archive filename does NOT include -SKIPPED
        </expected>
    </test_case>
    
    <test_case id="all_skipped" type="edge">
        <scenario>User skips all phases</scenario>
        <expected>
            - Archive filename includes -SKIPPED
            - No commits made (nothing to commit)
        </expected>
    </test_case>
    
    <test_case id="retry_success" type="edge">
        <scenario>Phase fails verification, fix succeeds on retry 2</scenario>
        <expected>
            - Two execution attempts logged
            - Phase marked [x] after second attempt
            - Audit continues normally
        </expected>
    </test_case>
    
    <test_case id="max_retries" type="adversarial">
        <scenario>Phase fails all 3 retry attempts</scenario>
        <expected>
            - Phase reverted to [ ]
            - Clear error message with failure details
            - Suggestions for manual intervention
            - .audit/ preserved
        </expected>
    </test_case>
    
    <test_case id="stale_audit" type="edge">
        <scenario>Audit inactive for 10 days</scenario>
        <expected>
            - Warning displayed on session start
            - Options offered: resume, archive incomplete, abandon
            - No automatic action taken
        </expected>
    </test_case>
</evaluation_suite>

---

## Examples

<examples>
    <example type="happy_path" name="execute_next_phase">
        <input>next</input>
        <o>
            Reading Phase 2: Extract validation logic...
            
            Executing plan:
            1. Creating ValidationService.swift
            2. Moving validation methods
            3. Updating imports in ConversationView.swift
            
            Running verification:
            ✓ grep -q "class ValidationService" Sources/ValidationService.swift
            ✓ swift build
            ✓ swift test
            
            ✓ Phase 2 complete: Extract validation logic to dedicated service
        </o>
    </example>
    
    <example type="edge_case" name="skip_specific_phase">
        <input>skip phase 3</input>
        <o>
            ⏭ Phase 3 skipped: Add comprehensive error handling
            
            Remaining: 2 phases
        </o>
    </example>
    
    <example type="error_case" name="phase_verification_failure">
        <input>next</input>
        <o>
            Reading Phase 4: Implement caching layer...
            
            Executing plan:
            1. Creating CacheManager.swift
            2. Integrating with NetworkService
            
            Running verification:
            ✓ test -f Sources/CacheManager.swift
            ✗ swift test (exit code 1)
            
            Attempt 1/3: Analyzing test failure...
            Found: Missing import in CacheManager.swift
            Fixing...
            
            Retry verification:
            ✓ swift test
            
            ✓ Phase 4 complete: Implement caching layer
        </o>
    </example>
    
    <example type="counter_example" name="unrecognized_command">
        <input>do the next thing please</input>
        <wrong_output>Executing phase 2...</wrong_output>
        <reason>Input doesn't match recognized command patterns</reason>
        <correct_output>
            Command not recognized. Valid commands: next, skip, status, abandon.
            Say 'status' to see current progress.
        </correct_output>
    </example>
</examples>

---

## Project-Specific Context

{Brief description of project, tech stack, key constraints}

---

## Critical Reminders

1. **Read First**: Always read this file completely when user mentions audit/phases
2. **State is Truth**: This file on disk is the source of truth for phase status
3. **Verify Always**: Never mark [x] without all verifications passing
4. **Update Timestamp**: Set Last Activity after every state change
5. **Atomic Archive**: Use temp file + rename pattern for safe archiving
6. **Preserve on Failure**: Keep .audit/ intact if any completion step fails

---
```

## Migration Notes

To upgrade from CONTEXT_template.md to CONTEXT_refined.md:

1. The command interface is unchanged — all existing commands work
2. Reasoning protocol is now explicit — Claude Code follows documented decision tree
3. Edge cases are now enumerated — predictable behavior in failure scenarios
4. Evaluation criteria added — can be used for testing automation

## Modules Applied

| Module | Application |
|--------|-------------|
| `orchestration` | Phase pipeline as task_orchestration |
| `chaining` | Multi-step rules as chain_definition |
| `reasoning` | Explicit reasoning_protocol for commands |
| `edge_cases` | Comprehensive boundary conditions |
| `evaluation` | Test cases for validation |
| `examples` | Happy path, edge, error, counter examples |
| `guardrails` | Safety constraints on destructive operations |
