# Phase File Template

Use this template for each phase. Replace all `{placeholders}`.

---

```markdown
# Phase {N}: {Title}

## Context

{Why this change is needed. Reference to audit findings. 2-3 sentences.}

## Goal

{Exact outcome of this phase — one sentence.}

## Files

- `path/to/file.swift` (modify)
- `path/to/new-file.swift` (create)
- `path/to/delete.swift` (delete)

## Plan

1. **Explore current state:**
   {Commands to understand current code}
   rg "pattern" --type swift
   
2. **Make changes:**
   {Detailed instructions with code examples if needed}

3. **Update related files:**
   {Any cascading changes}

4. **Verify:**
   make build
   make test

## Verify

{Commands that must succeed before marking complete. All must exit 0.}

grep -q "expected content" path/to/file
test -f path/to/new/file
test -s path/to/file
! grep -q "removed content" path/to/file

## Acceptance Criteria

- [ ] {Specific criterion 1}
- [ ] {Specific criterion 2}
- [ ] {Specific criterion 3}
- [ ] Build succeeds with no warnings related to this change
- [ ] All tests pass

## Rollback

{Commands to undo this phase if needed}

git checkout -- path/to/files
rm -f path/to/new/files
```

---

## Guidelines

### Context
- Explain WHY this change matters
- Reference the audit finding that identified this issue
- Keep it brief — 2-3 sentences

### Goal
- One sentence
- Specific and measurable
- Example: "Extract ConversationView into 4 focused components, reducing it from 500 to under 200 lines."

### Files
- List ALL files that will be touched
- Mark each as (create), (modify), or (delete)
- Order by importance

### Plan
- Step-by-step instructions
- Include actual commands to run
- Include code snippets for complex changes
- End with verification steps

### Acceptance Criteria
- Specific, checkable items
- Include "Build succeeds" and "Tests pass"
- 4-6 criteria typical

### Rollback
- Git commands to undo changes
- rm commands for created files
- Should restore to pre-phase state

---

## Schema

### Required Sections

Every phase file MUST contain these sections in order:

| Section                | Purpose                   | Validation                       |
| ---------------------- | ------------------------- | -------------------------------- |
| # Phase N: Title       | Identify phase            | Must start with "# Phase"        |
| ## Context             | Why this change matters   | Non-empty paragraph              |
| ## Goal                | Single success criterion  | One sentence/paragraph           |
| ## Files               | What will be touched      | List with (create/modify/delete) |
| ## Plan                | Step-by-step instructions | Numbered steps                   |
| ## Verify              | Machine-executable checks | Bash commands, all must exit 0   |
| ## Acceptance Criteria | Human-readable checklist  | Checkbox list                    |
| ## Rollback            | How to undo if needed     | Git/rm commands                  |

### Optional Sections

| Section         | Purpose                                   |
| --------------- | ----------------------------------------- |
| ## Note         | Special instructions or warnings for user |
| ## Dependencies | Other phases that must complete first     |

### Validation

Claude Code should verify all required sections exist before executing a phase.
If any required section is missing, report:
"Phase file malformed: missing ## {Section}. Check .audit/phases/{filename}."

### Idempotency Guidance

Phase instructions should be idempotent (safe to run twice) when possible:

- Use "add if not present" instead of "append"
- Check if file exists before creating
- Use grep to verify before adding lines

This prevents duplicate changes if a phase is interrupted and restarted.

### Verification Best Practices

Write verifications that:

- Are idempotent (safe to run multiple times)
- Check outcomes, not actions ("file contains X" not "I ran sed")
- Cover each acceptance criterion with at least one command
- Fail fast with clear signal (exit non-zero)

Common patterns:

- `grep -q "pattern" file` — content exists
- `! grep -q "pattern" file` — content removed
- `test -f file` — file exists
- `test -s file` — file exists and non-empty
- `test ! -f file` — file does not exist
- `head -1 file | grep -q "pattern"` — first line matches

---

## Risk Levels

Tag phases by risk in the audit:

| Risk | Meaning | Examples |
|------|---------|----------|
| Low | Safe, isolated changes | Add linting, extract constants, add docs |
| Medium | Refactors, new patterns | Decompose views, add protocols, caching |
| High | Architectural changes | Refactor core services, change DI patterns |

Order phases low → high risk within the audit.
