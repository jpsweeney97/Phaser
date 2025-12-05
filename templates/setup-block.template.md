# Setup Block Template

This is the format for delivering audits to users. Claude Code parses this to create the `.audit/` folder.

> **Note:** Setup blocks should include `.audit/tools/serialize.py` to enable
> automatic post-audit manifest generation. Copy the serializer from
> `Phaser/tools/serialize.py` into your setup block.

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

===FILE: .audit/tools/serialize.py===
{Copy full content from Phaser/tools/serialize.py}
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
   a. Verify .audit/CONTEXT.md exists and is readable
      - If missing: warn "Existing .audit/ folder is malformed (no CONTEXT.md)"
      - Ask: "Say 'abandon' to delete it, or fix manually"
      - Do NOT proceed until user responds
   b. Read metadata from .audit/CONTEXT.md
      - Extract: project_name, audit_slug, audit_date
      - If any missing: use defaults (project_name=current_directory_name, audit_slug=unknown, audit_date=today)
   c. Determine archive directory:
      - If PHASER_ARCHIVE_DIR environment variable is set: use that
      - If macOS: use ~/Documents/Audits/
      - If Linux: use ~/.local/share/phaser/audits/
   d. Create {archive_dir}/{project_name}/ if needed
   e. Set temp_path = {archive_dir}/{audit_date}-{audit_slug}-INCOMPLETE.md.tmp
   f. Copy .audit/CURRENT.md to temp_path
   g. Verify temp_path exists and has content
      - If failed: report error, do NOT delete .audit/, STOP
   h. Rename temp_path to final (remove .tmp)
   i. Verify final path exists
      - If failed: report error, do NOT delete .audit/, STOP
   j. Only now: delete .audit/ folder

2. CREATE DIRECTORY STRUCTURE:
   - Create .audit/
   - Create .audit/phases/
   - Create .audit/tools/

3. CREATE FILES:
   - For each ===FILE: {path}=== section below, create the file at that path
   - Write all content between ===FILE: {path}=== and ===END FILE=== to that file
   - After creating CONTEXT.md, set "Last Activity" in Metadata to current timestamp
   - Verify .audit/tools/serialize.py was created (required for post-audit manifest)

3a. INITIALIZE PHASER STORAGE:
   - Create .phaser/ directory if it doesn't exist
   - Create .phaser/manifests/ subdirectory
   - Add .phaser/ to .gitignore if not present
   - This enables diff tracking, contracts, and event logging

3b. CAPTURE PRE-AUDIT MANIFEST (if tools/diff.py exists):
   - Run: python -m tools.diff capture . -o .phaser/manifests/{audit_id}-pre.yaml
   - If tools/diff.py not available, skip (backward compatibility)
   - This enables "show diff" command after audit completion

4. VALIDATE METADATA:
   - Read project_name and audit_slug from .audit/CONTEXT.md
   - Verify both start with alphanumeric and contain only allowed characters (a-z, A-Z, 0-9, hyphen, underscore)
   - Verify neither contains / or \
   - Verify neither exceeds 50 characters
   - If invalid: report error with valid name examples, delete .audit/, abort

5. UPDATE .gitignore:
   - If .gitignore exists and doesn't contain ".audit/", append it
   - If .gitignore doesn't exist, create it with ".audit/" as content

6. UPDATE GLOBAL CLAUDE.md (first audit only):
   - Read ~/.claude/CLAUDE.md
   - Search for "<!-- AUDIT-SYSTEM -->"
   - If NOT found, append the Phaser snippet to the "Project-Specific Context" section

7. CONFIRM:
   - List all files created
   - Note .phaser/ storage initialized
   - Note any modifications to .gitignore or ~/.claude/CLAUDE.md
   - If Simulation or Branch Mode enabled in metadata, mention it
   - Say: "Audit ready. Say 'next' to begin Phase 1."
   - Mention: "After completion, contracts will be extracted from phases with ## Contract sections."
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
