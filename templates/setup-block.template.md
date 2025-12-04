# Setup Block Template

This is the format for delivering audits to users. Claude Code parses this to create the `.audit/` folder.

---

## Structure

```
=== AUDIT SETUP START ===

SETUP INSTRUCTIONS FOR CLAUDE CODE:
{Standard setup instructions - copy from below}

---

===FILE: .audit/CONTEXT.md===
{Content of CONTEXT.md}
===END FILE===

===FILE: .audit/phases/01-{slug}.md===
{Content of phase 1}
===END FILE===

===FILE: .audit/phases/02-{slug}.md===
{Content of phase 2}
===END FILE===

{... more phases ...}

===FILE: .audit/CURRENT.md===
{Content of full audit report}
===END FILE===

=== AUDIT SETUP END ===
```

---

## Standard Setup Instructions

Copy this block at the start of every setup block:

```
SETUP INSTRUCTIONS FOR CLAUDE CODE:

Parse this block and perform the following steps:

1. ARCHIVE EXISTING AUDIT (if .audit/ folder exists):
   - Read metadata from .audit/CONTEXT.md for project_name, audit_slug, audit_date
   - Create ~/Documents/Audits/{project_name}/ if it doesn't exist
   - Copy .audit/CURRENT.md to ~/Documents/Audits/{project_name}/{audit_date}-{audit_slug}-INCOMPLETE.md
   - Delete .audit/ folder

2. CREATE DIRECTORY STRUCTURE:
   - Create .audit/
   - Create .audit/phases/

3. CREATE FILES:
   - For each ===FILE: {path}=== section below, create the file at that path
   - Write all content between ===FILE: {path}=== and ===END FILE=== to that file

4. UPDATE .gitignore:
   - If .gitignore exists and doesn't contain ".audit/", append it
   - If .gitignore doesn't exist, create it with ".audit/" as content

5. UPDATE GLOBAL CLAUDE.md (first audit only):
   - Read ~/.claude/CLAUDE.md
   - Search for "<!-- AUDIT-SYSTEM -->"
   - If NOT found, append the Phaser snippet to the "Project-Specific Context" section

6. CONFIRM:
   - List all files created
   - Note any modifications to .gitignore or ~/.claude/CLAUDE.md
   - Say: "Audit ready. Say 'next' to begin Phase 1."
```

---

## File Delimiters

| Delimiter | Purpose |
|-----------|---------|
| `=== AUDIT SETUP START ===` | Start of setup block |
| `=== AUDIT SETUP END ===` | End of setup block |
| `===FILE: {path}===` | Start of file content |
| `===END FILE===` | End of file content |

**Important:**
- No markdown code fences inside the block
- Plain text only
- Consistent delimiters (Claude Code searches for exact strings)

---

## Example File Section

```
===FILE: .audit/phases/01-example.md===
# Phase 1: Example Phase

## Context

This is an example phase.

## Goal

Demonstrate the format.

## Files

- example.swift (modify)

## Plan

1. Do the thing
2. Verify it works

## Acceptance Criteria

- [ ] Thing is done
- [ ] Tests pass

## Rollback

git checkout -- example.swift
===END FILE===
```

---

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Audit slug | lowercase-kebab-case | `architecture-refactor` |
| Phase files | `NN-slug.md` | `01-export-service-di.md` |
| Archive | `{date}-{slug}.md` | `2024-12-04-architecture-refactor.md` |
| Git tag | `audit/{date}-{slug}` | `audit/2024-12-04-architecture-refactor` |

---

## Integrity Verification (Recommended)

Add a checksum line immediately before the closing delimiter:

```
CHECKSUM: sha256:{64-character-hex-hash}
=== AUDIT SETUP END ===
```

The hash covers all content from `=== AUDIT SETUP START ===` up to (not including) the CHECKSUM line.

**Claude Code validation procedure:**

1. Extract content between START marker and CHECKSUM line
2. Compute SHA256 hash of that content
3. Compare to stated checksum
4. If mismatch: "Setup block appears truncated or corrupted. Please re-copy the complete block from source."

This catches truncated pastes and copy errors before they cause confusing failures.
