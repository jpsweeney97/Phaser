# CONTEXT.md Template

Use this template when generating new audits. Replace all `{placeholders}`.

---

```markdown
# Audit Context: {project_name}

> **For Claude Code:** Read this file completely before starting any audit-related work.

---

## Metadata

| Field        | Value           |
| ------------ | --------------- |
| Project      | {project_name}  |
| Audit        | {audit_slug}    |
| Date         | {YYYY-MM-DD}    |
| Version      | 1.2             |
| Test Command | {test_command}  |
| Archive Dir  | {archive_dir or "auto"} |
| Last Activity | {YYYY-MM-DD HH:MM} |
| Simulation   | {enabled/disabled} |
| Branch Mode  | {enabled/disabled} |

> **Note:** Default test_command is `make test`. Set appropriately for your project (`npm test`, `pytest`, `xcodebuild test`, `cargo test`, etc.).

> **Note:** Default archive location is `~/Documents/Audits/` (macOS) or `~/.local/share/phaser/audits/` (Linux). Override with `PHASER_ARCHIVE_DIR` environment variable.

> **Note:** Claude Code updates "Last Activity" after every phase execution, skip, or status check.

---

## Naming Rules

Project and Audit names must:

- Start with alphanumeric character (a-z, A-Z, 0-9)
- Contain only: letters, numbers, hyphen (-), underscore (\_)
- Not contain path separators (/ or \)
- Not exceed 50 characters

Claude Code validates these before creating archives or tags. Invalid names are rejected with clear error message.

---

## Summary

{2-3 sentence summary of what this audit covers and its primary goals}

---

## Phase Status

- [ ] Phase 1: {description}
- [ ] Phase 2: {description}
- [ ] Phase 3: {description}
      {... add more phases as needed}

**Legend:**

- [ ] = Incomplete (pending)
- [IN PROGRESS] = Execution started, not yet verified
- [x] = Complete (verified)
- [SKIPPED] = Skipped by user

---

## Commands

Recognize these exact phrases (case-insensitive):

### Execute Next Phase

- "next"
- "continue"
- "proceed"
- "go"
- "next phase"
- "run next"
- "run next phase"

### Skip Phase

- "skip" (skips next incomplete)
- "skip this"
- "skip phase N" (where N is phase number)
- "skip N"

### Redo Phase

- "redo N" (where N is phase number)
- "redo phase N"
- "re-run N"
- "re-run phase N"
- "rerun N"

### Show Status

- "status"
- "audit status"
- "show status"
- "progress"
- "show progress"

### Abandon Audit

- "abandon"
- "abandon audit"
- "cancel audit"
- "delete audit"

### Show Full Report

- "show full audit"
- "full report"
- "show report"
- "show current"

### Archive Incomplete

- "archive incomplete"
- "save and close"
- "archive as is"

Action: Archive current state to {date}-{slug}-INCOMPLETE.md and delete .audit/

### Show Diff

- "show diff"
- "audit diff"
- "what changed"

Action: Display diff summary from pre/post manifests (if available)

### Simulate Audit

- "simulate"
- "dry-run"
- "preview"
- "simulate all"

Action: Run all remaining phases in simulation mode, then rollback.
Shows what would change without committing.

### Simulate Phase

- "simulate phase N"
- "dry-run phase N"
- "preview phase N"

Action: Simulate specific phase only, then rollback.

**Not recognized:** Free-form requests like "what's next", "do the next thing", or "can you run phase 3" — use the exact phrases above.

---

## Automation Rules

### 0. Stale Audit Check

When first reading this file in a session:

1. Parse "Last Activity" from Metadata
2. Calculate days since last activity
3. If 7+ days have passed:
   - Warn: "This audit has been inactive for N days."
   - Show last completed phase and remaining phases
   - Offer options:
     - "Say 'resume' to continue where you left off"
     - "Say 'archive incomplete' to save current state and close"
     - "Say 'abandon' to delete without saving"
   - Wait for user response before proceeding
4. If less than 7 days: proceed normally

### 1. Phase Execution

When executing a phase:

1. Identify the first phase marked [ ] (incomplete)
2. If phase is marked [IN PROGRESS], see Rule 1a
3. If no incomplete phases exist, trigger completion (see Rule 5)
4. Update this file: change [ ] to [IN PROGRESS] for that phase
5. Read the corresponding file: .audit/phases/{NN}-{slug}.md
6. Execute all instructions in the phase file
7. Run verification steps (build, test, lint as applicable)
8. Run verification commands from ## Verify section
9. If ANY verification fails: treat as phase failure (retry logic applies)
10. Only mark [x] after ALL verifications pass
11. On success:
    - Update this file: change [IN PROGRESS] to [x] for that phase
    - Update Metadata: set "Last Activity" to current timestamp
    - Report: "Phase N complete: {description}"
    - Check if all phases are now complete/skipped (trigger Rule 5 if yes)
12. On failure:
    - Attempt to fix the issue (up to 3 attempts)
    - If fixed, proceed to success
    - If still failing after 3 attempts, report what failed, what was attempted, and suggest alternatives
    - Update this file: change [IN PROGRESS] back to [ ]
    - Do NOT continue to next phase

### 1a. Handling Interrupted Phases

If a phase is marked [IN PROGRESS] when starting:

1. Warn user: "Phase N was interrupted. Changes may be partially applied."
2. Offer options: "Say 'continue' to resume, 'rollback N' to undo, or 'skip' to skip."
3. If continue: proceed with execution (phase instructions should be idempotent)
4. If rollback: execute rollback commands from phase file, then mark [ ]
5. If skip: mark [SKIPPED]

### 2. Phase Skipping

When user requests skip:

1. If "skip" with no number: skip the next incomplete phase
2. If "skip phase N": skip phase N specifically
3. Update this file: change [ ] to [SKIPPED]
4. Update Metadata: set "Last Activity" to current timestamp
5. Report: "Phase N skipped: {description}"
6. Check if all phases are now complete/skipped (trigger Rule 5 if yes)

### 3. Phase Redo

When user requests redo:

1. Validate phase number exists
2. Update this file: change [x] or [SKIPPED] back to [ ]
3. Execute the phase (follow Rule 1)

### 4. Status Report

When user requests status:

1. Display the Phase Status section from this file
2. If active simulation: show "[SIMULATION MODE]" warning
3. Summarize: "N complete, M skipped, P remaining"
4. Update Metadata: set "Last Activity" to current timestamp

### 5. Completion & Auto-Archive

Triggered when all phases are [x] or [SKIPPED]:

1. Run final verification:

   - Execute the Test Command specified in Metadata above
   - If tests fail: report failure, do NOT proceed with archive, leave .audit/ in place

2. Commit any uncommitted changes:

   - Check: git status --porcelain
   - If changes exist: git add -A && git commit -m "Complete {audit_slug} audit"

3. Prepare archive:

   - Determine archive base directory:
     - If `PHASER_ARCHIVE_DIR` environment variable is set: use that
     - If macOS: use `~/Documents/Audits/`
     - If Linux: use `~/.local/share/phaser/audits/`
   - Create {archive_base}/{project_name}/ if it doesn't exist
   - Determine final filename:
     - If ALL phases are [SKIPPED]: {date}-{audit_slug}-SKIPPED.md
     - Otherwise: {date}-{audit_slug}.md
   - If filename exists, try -2, -3, etc. (max -99, then error)
   - Set temp_path = {final_path}.tmp

4. Atomic archive:

   - Copy .audit/CURRENT.md to temp_path
   - Verify: temp_path exists AND has size > 0
   - If verification fails: report "Archive failed: could not write to {temp_path}", leave .audit/ intact, STOP
   - Rename temp_path to final_path (atomic on POSIX filesystems)
   - If rename fails: report error, leave .audit/ intact, STOP
   - Verify: final_path exists

4a. Generate diff report (if tools/diff.py exists):

   - Load pre-audit manifest from .phaser/manifests/{audit_id}-pre.yaml
   - Capture post-audit manifest
   - Compare and generate diff summary
   - Include diff summary in completion report

5. Create git tag:

   - Execute: git tag audit/{date}-{audit_slug}
   - If tag exists, append -2, -3, etc.

6. Generate post-audit manifest:

   - Set manifest_dir = {archive_base}/{project_name}/manifests/
   - Create manifest_dir if it doesn't exist
   - Set manifest_path = {manifest_dir}/{date}-{audit_slug}-post.yaml
   - If .audit/tools/serialize.py exists:
     - Run: python .audit/tools/serialize.py --root . --output {manifest_path} --quiet
     - If successful: record manifest_path for report
     - If failed: warn "Post-audit manifest generation failed: {error}" and continue
   - If serializer not found: note "Post-audit manifest skipped (serializer not found)"

7. Only after successful archive and tag:

   - Delete .audit/ folder entirely

8. Report summary:
   - "Audit complete."
   - "Phases: N completed, M skipped"
   - "Commits made: (list recent commits from this audit)"
   - "Tag created: audit/{date}-{audit_slug}"
   - "Archived to: {full_path}"
   - If manifest was generated: "Post-audit manifest: {manifest_path}"
   - "To push tag: git push --tags"
   - If manifest was generated: "To validate: Upload manifest to claude.ai with original audit goals"

### 6. Abandon

When user requests abandon:

1. Delete .audit/ folder entirely
2. Do NOT archive anything
3. Report: "Audit abandoned. Removed .audit/ folder."

### 7. Simulation Mode

When user requests simulation ("simulate", "dry-run", "preview"):

1. Verify no active simulation exists
2. Stash any uncommitted changes (will be restored after)
3. Execute phases in sandbox:
   - Track all files created
   - Track all files modified
   - Track all files deleted
4. After all phases complete (or first failure if fail_fast):
   - Capture diff summary
   - Rollback all changes
   - Restore stashed changes
5. Report:
   - "Simulation complete"
   - "Phases: N passed, M failed"
   - "Would create X files, modify Y files, delete Z files"
   - "First failure: Phase P" (if any)
   - "To apply these changes for real, say 'next'"

If "simulate phase N": only simulate that specific phase.

**Recovery:** If simulation is interrupted, context is saved to .phaser/simulation.yaml.
On next run, offer: "resume", "rollback", or "abandon".

### 8. Branch Mode

When user enables branch mode ("branch mode", "enable branches"):

1. Verify no active branch mode exists
2. Record current branch as base
3. For each phase:
   - Create branch: `audit/{audit_slug}/phase-{NN}-{phase_slug}`
   - Execute phase on that branch
   - Commit changes with message: "Phase {N}: {description}"
4. After all phases complete:
   - Offer merge strategies: "squash", "rebase", or "merge"
   - Default: squash all branches into base
5. Cleanup: Delete phase branches after merge

Branch naming: `audit/{audit_slug}/phase-01-{phase_slug}`

**Commands:**
- "branch status" — Show current branch state
- "merge branches" — Merge all phase branches to base
- "cleanup branches" — Delete merged branches

### 9. Error Handling

| Situation                       | Response                                                        |
| ------------------------------- | --------------------------------------------------------------- |
| "next" but no .audit/ exists    | "No active audit found."                                        |
| "skip phase 99" (invalid)       | "Invalid phase number. This audit has N phases."                |
| Phase file missing              | "Phase file not found: {path}. Check .audit/phases/ directory." |
| Cannot create archive directory | Report error and suggest manual creation                        |
| Cannot delete .audit/           | Report error and suggest manual deletion                        |

**Archive Failure Recovery:**
If archive fails at any step, .audit/ is preserved. User options:

- Fix the issue (free disk space, fix permissions) and say "next" to retry completion
- Manually copy to archive location (see Metadata for path)
- Say "abandon" to delete .audit/ without archiving

---

## Critical Reminders

1. Always read this file first when user mentions audit, phases, or uses commands above
2. Update this file after every phase execution (success, skip, or redo)
3. State is persistent — this file on disk is the source of truth
4. Build and test after each phase before marking complete
5. 3 attempts max on failures, then stop and report

---

## Project-Specific Context

{Brief description of project, tech stack, key constraints}

---
```
