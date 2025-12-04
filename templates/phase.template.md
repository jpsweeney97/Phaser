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

## Risk Levels

Tag phases by risk in the audit:

| Risk | Meaning | Examples |
|------|---------|----------|
| Low | Safe, isolated changes | Add linting, extract constants, add docs |
| Medium | Refactors, new patterns | Decompose views, add protocols, caching |
| High | Architectural changes | Refactor core services, change DI patterns |

Order phases low → high risk within the audit.
