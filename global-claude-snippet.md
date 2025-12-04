# Global CLAUDE.md Snippet

Add this to your `~/.claude/CLAUDE.md` file.

**Location:** Inside or after the "Project-Specific Context" section.

---

## The Snippet

```markdown
## Project-Specific Context

For project-specific instructions, check for:

- `CLAUDE.md` in project root
- `.claude/` directory with settings or commands
- `.audit/` directory for active audits
- `docs/PRD.md` for requirements

<!-- AUDIT-SYSTEM -->

**Active Audit System — MANDATORY:**
BEFORE doing anything when the user says "next", "continue", "proceed", "go", "status", "skip", "redo", or "phase":

1. Check if `.audit/` directory exists in the current project
2. If it exists, read `.audit/CONTEXT.md` FIRST
3. Follow the instructions in CONTEXT.md exactly
4. Do NOT improvise or suggest other work

If `.audit/` exists and user says "next": execute the next incomplete phase per CONTEXT.md rules.

<!-- /AUDIT-SYSTEM -->

Project CLAUDE.md takes precedence over this global file for project-specific decisions.
```

---

## Installation

**Option A: Append directly**
```bash
cat ~/Projects/Phaser/global-claude-snippet.md >> ~/.claude/CLAUDE.md
```
Then edit `~/.claude/CLAUDE.md` to remove the explanatory text, keeping only the snippet.

**Option B: Manual**
1. Open `~/.claude/CLAUDE.md`
2. Find your "Project-Specific Context" section
3. Replace it with the snippet above
4. Save

---

## Verification

```bash
grep "AUDIT-SYSTEM" ~/.claude/CLAUDE.md
```

Should return:
```
<!-- AUDIT-SYSTEM -->
```

---

*Phaser v1*
