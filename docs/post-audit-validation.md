# Post-Audit Validation Guide

Validate that your completed audit achieved its goals by comparing the final codebase state against the original objectives.

---

## Overview

Post-audit validation provides an independent verification that:

1. All phase goals were achieved
2. Changes match the stated objectives
3. No unintended modifications occurred
4. Implementation quality meets standards

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. Audit completes in Claude Code                                          │
│     └── All phases marked [x] or [SKIPPED]                                  │
│                                                                             │
│  2. Automatic manifest generation                                           │
│     └── Post-audit manifest saved to:                                       │
│         ~/Documents/Audits/{project}/manifests/{date}-{slug}-post.yaml      │
│                                                                             │
│  3. Manual validation in claude.ai                                          │
│     └── Upload manifest + audit goals                                       │
│     └── Claude compares actual changes vs intended changes                  │
│     └── Receive structured validation report                                │
│                                                                             │
│  4. Address any gaps                                                        │
│     └── Fix issues manually or run follow-up audit                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Completed Phaser audit
- Archived CURRENT.md (in ~/Documents/Audits/{project}/)
- Post-audit manifest (in ~/Documents/Audits/{project}/manifests/)

If manifest generation was skipped, you can generate it manually:

```bash
cd ~/Projects/YourProject
python ~/Projects/Phaser/tools/serialize.py --root . --output manifest-post.yaml
```

---

## Step-by-Step

### 1. Locate Your Files

After audit completion, find:

| File          | Location                                                         | Contains                         |
| ------------- | ---------------------------------------------------------------- | -------------------------------- |
| Audit Report  | `~/Documents/Audits/{project}/{date}-{slug}.md`                  | Phase goals, acceptance criteria |
| Post Manifest | `~/Documents/Audits/{project}/manifests/{date}-{slug}-post.yaml` | Final codebase state             |

### 2. Prepare Validation Request

Open your archived audit report and extract:

- Phase summary table
- Key acceptance criteria from each phase
- Any notes about skipped phases

### 3. Submit to claude.ai

Use the template in `templates/validation-prompt.template.md`:

1. Copy the prompt template
2. Fill in your audit details
3. Attach or paste the post-audit manifest
4. Submit to claude.ai

### 4. Review Validation Report

Claude will provide:

| Section           | Description                        |
| ----------------- | ---------------------------------- |
| Confirmed Changes | Evidence that phase goals were met |
| Potential Issues  | Anomalies or concerns              |
| Missing Items     | Goals that weren't achieved        |
| Recommendations   | Suggested follow-up actions        |

### 5. Address Gaps

If validation reveals issues:

- **Minor gaps:** Fix manually and commit
- **Significant gaps:** Create follow-up audit phases
- **False positives:** Document why the concern doesn't apply

---

## What Gets Validated

### Checked

- Files listed in phase plans were modified
- Content matches acceptance criteria
- No unexpected file modifications
- Code patterns match requirements (e.g., "uses DI" vs "uses singleton")

### Not Checked

- Runtime behavior (requires actual execution)
- Test coverage quality (only checks tests exist)
- Performance characteristics
- Security vulnerabilities (beyond pattern matching)

---

## Comparison Types

### Before/After Comparison

For maximum validation, provide both manifests:

1. **Pre-audit manifest:** Generated before starting audit
2. **Post-audit manifest:** Generated after completion

This allows Claude to:

- Identify exactly which files changed
- Verify changes match phase scope
- Detect unrelated modifications

### Post-Only Validation

With only the post-audit manifest, Claude can verify:

- Required files exist
- Required content is present
- File structure matches expectations

But cannot verify:

- What specifically changed
- Whether changes were minimal
- Unrelated file modifications

---

## Troubleshooting

| Problem                | Solution                                    |
| ---------------------- | ------------------------------------------- |
| Manifest not generated | Run serializer manually (see Prerequisites) |
| Manifest too large     | Claude may truncate; summarize large files  |
| False positives        | Provide more context about expected changes |
| Missing phase details  | Include full CURRENT.md, not just summary   |

---

## Best Practices

1. **Generate pre-audit manifest** before starting for better comparison
2. **Don't modify files manually** between phases (tracked in commits)
3. **Include all phases** even skipped ones, noting they were skipped
4. **Be specific** about acceptance criteria for better validation
5. **Save validation reports** for audit trail

---

*Phaser v1.1*
