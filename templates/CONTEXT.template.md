# CONTEXT.md Template

Use this template when generating new audits. Replace all `{placeholders}`.

---

```markdown
# Audit Context: {project_name}

> **For Claude Code:** Read this file completely before starting any audit-related work.

---

## Metadata

| Field | Value |
|-------|-------|
| Project | {project_name} |
| Audit | {audit_slug} |
| Date | {YYYY-MM-DD} |
| Version | 1 |

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
- [x] = Complete (verified)
- [SKIPPED] = Skipped by user

---

## Commands

Recognize these commands from the user (case-insensitive, flexible phrasing):

| User Says | Action |
|-----------|--------|
| "next", "continue", "proceed", "go" | Execute next incomplete phase |
| "skip", "skip this", "skip phase N" | Mark phase as SKIPPED |
| "redo N", "redo phase N", "re-run phase N" | Reset phase to incomplete and execute |
| "status", "audit status", "show status" | Display phase checklist |
| "abandon", "abandon audit" | Delete .audit/ without archiving |
| "show full audit", "full report" | Display contents of CURRENT.md |

---

## Automation Rules

### 1. Phase Execution

When executing a phase:

1. Identify the first phase marked [ ] (incomplete)
2. If no incomplete phases exist, trigger completion (see Rule 5)
3. Read the corresponding file: .audit/phases/{NN}-{slug}.md
4. Execute all instructions in the phase file
5. Run verification steps (build, test, lint as applicable)
6. On success:
   - Update this file: change [ ] to [x] for that phase
   - Report: "Phase N complete: {description}"
   - Check if all phases are now complete/skipped (trigger Rule 5 if yes)
7. On failure:
   - Attempt to fix the issue (up to 3 attempts)
   - If fixed, proceed to success
   - If still failing after 3 attempts, report what failed, what was attempted, and suggest alternatives
   - Leave phase as [ ]
   - Do NOT continue to next phase

### 2. Phase Skipping

When user requests skip:

1. If "skip" with no number: skip the next incomplete phase
2. If "skip phase N": skip phase N specifically
3. Update this file: change [ ] to [SKIPPED]
4. Report: "Phase N skipped: {description}"
5. Check if all phases are now complete/skipped (trigger Rule 5 if yes)

### 3. Phase Redo

When user requests redo:

1. Validate phase number exists
2. Update this file: change [x] or [SKIPPED] back to [ ]
3. Execute the phase (follow Rule 1)

### 4. Status Report

When user requests status:

1. Display the Phase Status section from this file
2. Summarize: "N complete, M skipped, P remaining"

### 5. Completion & Auto-Archive

Triggered when all phases are [x] or [SKIPPED]:

1. Run final verification:
   - Execute: make test (or appropriate test command)
   - If tests fail: report failure, do NOT proceed with archive, leave .audit/ in place

2. Commit any uncommitted changes:
   - Check: git status --porcelain
   - If changes exist: git add -A && git commit -m "Complete {audit_slug} audit"

3. Create archive directory:
   - Create ~/Documents/Audits/{project_name}/ if it doesn't exist

4. Determine archive filename:
   - If ALL phases are [SKIPPED]: {date}-{audit_slug}-SKIPPED.md
   - Otherwise: {date}-{audit_slug}.md
   - If filename exists, append -2, -3, etc. until unique

5. Copy .audit/CURRENT.md to archive path

6. Create git tag:
   - Execute: git tag audit/{date}-{audit_slug}
   - If tag exists, append -2, -3, etc.

7. Delete .audit/ folder entirely

8. Report summary:
   - "Audit complete."
   - "Phases: N completed, M skipped"
   - "Commits made: (list recent commits from this audit)"
   - "Tag created: audit/{date}-{audit_slug}"
   - "Archived to: {full_path}"
   - "To push tag: git push --tags"

### 6. Abandon

When user requests abandon:

1. Delete .audit/ folder entirely
2. Do NOT archive anything
3. Report: "Audit abandoned. Removed .audit/ folder."

### 7. Error Handling

| Situation | Response |
|-----------|----------|
| "next" but no .audit/ exists | "No active audit found." |
| "skip phase 99" (invalid) | "Invalid phase number. This audit has N phases." |
| Phase file missing | "Phase file not found: {path}. Check .audit/phases/ directory." |
| Cannot create archive directory | Report error and suggest manual creation |
| Cannot delete .audit/ | Report error and suggest manual deletion |

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
