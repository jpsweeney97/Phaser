# CURRENT.md Template (Full Audit Report)

This is the comprehensive audit report. Gets archived on completion.

---

```markdown
# {Project Name} Repository Audit

**Audit Date:** {YYYY-MM-DD}
**Audit Slug:** {audit-slug}
**Files Analyzed:** {count}
**Total Size:** {size}

---

## I. Overview

### Project Understanding

{2-3 paragraph description of what the project does, its purpose, and key functionality}

### Tech Stack

- **Platform:** {e.g., macOS 14+}
- **Language:** {e.g., Swift 5.9+}
- **UI Framework:** {e.g., SwiftUI with @Observable}
- **Architecture:** {e.g., Environment-based DI}
- **Storage:** {e.g., Local JSON + Keychain}
- **Dependencies:** {e.g., None / list them}

### Key Entry Points

1. `{MainFile.swift}` — {description}
2. `{OtherFile.swift}` — {description}
3. `{AnotherFile.swift}` — {description}

---

## II. Findings Summary

### {Category 1} ({X} Major, {Y} Minor)

- {Finding 1 summary}
- {Finding 2 summary}

### {Category 2} ({X} Major, {Y} Minor)

- {Finding 1 summary}
- {Finding 2 summary}

{Repeat for all categories: Architecture, Code Quality, Testing, Performance, Reliability, Security, DevEx, Documentation, UX/UI}

---

## III. Detailed Findings

### {Category}

**{Severity}: {Issue Title}**
- **Location:** `{file path}`
- **Issue:** {Description of the problem}
- **Impact:** {Why this matters}
- **Fix:** {Brief solution}

{Repeat for each finding}

---

## IV. Improvement Phases

| # | Description | Risk | Est. Effort |
|---|-------------|------|-------------|
| 1 | {Phase 1 title} | Low | {time} |
| 2 | {Phase 2 title} | Low | {time} |
| 3 | {Phase 3 title} | Medium | {time} |
| ... | ... | ... | ... |

Total estimated effort: {X hours} across {N} phases

---

## V. Deep Dives

### {Issue Title}

**Problem:** {Detailed description}

**Current State:**
{Code example or description of current implementation}

**Impact:**
- {Impact 1}
- {Impact 2}

**Proposed Solution:**
{Detailed solution with code examples}

**Files Affected:**
- `{file1}`
- `{file2}`

{Repeat for top 3-5 critical issues}

---

## VI. Metadata

| Field | Value |
|-------|-------|
| Audit Date | {YYYY-MM-DD} |
| Audit Slug | {slug} |
| Files Analyzed | {count} |
| Total Size | {size} |
| Test Count | {count} |
| Phases | {count} |
| Post-Audit Manifest | Generated on completion |
```

---

## Guidelines

### Severity Levels

| Severity | Meaning |
|----------|---------|
| **Major** | Significant impact on maintainability, performance, or reliability. Should be fixed. |
| **Minor** | Small issues, nice-to-haves, or low-impact improvements. |

### Categories

Use these standard categories:
1. Architecture & Design
2. Code Quality
3. Testing Strategy
4. Performance & Scalability
5. Reliability
6. Security
7. Developer Experience (DevEx)
8. Documentation
9. UX/UI

### Phase Ordering

1. Quick wins first (low risk, high impact)
2. Medium refactors next
3. Architectural changes last (highest risk)

### Deep Dives

Include deep dives for:
- The most impactful issues
- Issues that need detailed explanation
- Complex refactors that benefit from examples
