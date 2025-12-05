# Post-Audit Validation Prompt Template

Copy this prompt to claude.ai along with your post-audit manifest to validate audit completion.

---

## The Prompt

Copy everything below this line:

---

## Post-Audit Validation Request

I've completed a Phaser audit and want to validate that all changes were applied correctly.

### Original Audit Summary

**Project:** {project_name}
**Audit Slug:** {audit_slug}
**Date:** {date}
**Phases Completed:** {N} of {total}

### Phase Goals (from CURRENT.md)

{Copy the phase summary table from your archived CURRENT.md, e.g.:}

| #   | Description                | Status |
| --- | -------------------------- | ------ |
| 1   | Add security documentation | ✓      |
| 2   | Add MIT license            | ✓      |
| 3   | Fix singleton pattern      | ✓      |
| ... | ...                        | ...    |

### Key Acceptance Criteria

{List the most important acceptance criteria from each phase:}

1. Phase 1: README.md contains "Security Note" section
2. Phase 2: LICENSE file exists with MIT header
3. Phase 3: ExportService uses dependency injection
   {...}

### Post-Audit Manifest

{Attach or paste your {date}-{slug}-post.yaml manifest file}

---

### Please Validate

1. **Completeness:** Were all phase goals achieved based on the manifest?
2. **Correctness:** Do the file changes match the stated objectives?
3. **Regressions:** Were any files modified that shouldn't have been?
4. **Quality:** Are there any concerns about the implementation quality?
5. **Gaps:** Is anything missing that should have been addressed?

Provide a structured validation report with:

- ✓ Confirmed changes (with evidence from manifest)
- ⚠ Potential issues (with explanation)
- ✗ Missing or incorrect items (with details)

---

## Tips for Best Results

1. **Include the full manifest** — Don't truncate; Claude needs all file contents
2. **Copy phase descriptions exactly** — From your archived CURRENT.md
3. **List specific acceptance criteria** — The more specific, the better validation
4. **Mention any skipped phases** — So Claude knows what to exclude
5. **Note any manual changes** — If you modified things outside the audit

---

## Example Validation Response

> ### Validation Report: security-hardening audit
>
> **Overall: ✓ PASS** (10/10 phases verified)
>
> #### Confirmed Changes
>
> - ✓ Phase 1: README.md contains "Security Note" section (line 45-67)
> - ✓ Phase 2: LICENSE exists, contains "MIT License" (line 1)
> - ✓ Phase 3: ExportService.swift no longer contains "shared" singleton
>   ...
>
> #### Potential Issues
>
> - ⚠ Phase 7: StateManager.swift was modified but not listed in phase files
>
> #### Summary
>
> All primary objectives achieved. One minor scope deviation noted.

---

*Phaser v1.1*
