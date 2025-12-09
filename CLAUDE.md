# Phaser

Phaser is an audit automation system that enables Claude (in claude.ai) to generate comprehensive code audits with executable phases, which Claude Code then executes automatically.

---

## What Phaser Does

1. **Claude (claude.ai)** analyzes a codebase and produces an audit with:
   - Findings organized by severity
   - Improvement phases (executable prompts)
   - A setup block that Claude Code can parse

2. **User** pastes the setup block into Claude Code

3. **Claude Code** creates `.audit/` folder with all files, then executes phases one by one when user says "next"

4. **On completion**, Claude Code archives the audit, creates a git tag, and cleans up

---

## Project Structure

```
Phaser/
├── CLAUDE.md              ← You are here
├── README.md              ← User-facing documentation
├── global-claude-snippet.md ← One-time addition to ~/.claude/CLAUDE.md
├── specs/                 ← Feature specifications
│   ├── bridge.md          ← Setup block parsing
│   ├── cli.md             ← CLI command reference
│   ├── ignore_parser.md   ← Inline ignore directives
│   ├── tool_input.md      ← Hook input reconstruction
│   └── ...
├── templates/
│   ├── CONTEXT.template.md   ← Template for .audit/CONTEXT.md
│   ├── CURRENT.template.md   ← Template for .audit/CURRENT.md (full report)
│   └── phase.template.md     ← Template for individual phase files
├── tools/                 ← CLI modules (845+ tests)
├── examples/
│   └── impromptu-setup-block.md ← Complete example audit
└── docs/
    ├── quick-reference.md    ← Commands cheat sheet
    └── creating-audits.md    ← How to generate audits
```

---

## Key Concepts

### Setup Block
A single text block containing all audit files, delimited by:
- `=== AUDIT SETUP START ===` / `=== AUDIT SETUP END ===`
- `===FILE: {path}===` / `===END FILE===` for each file

Claude Code parses this and creates the `.audit/` folder structure.

### CONTEXT.md
The automation brain. Contains:
- Metadata (project, slug, date)
- Phase status checklist (`[ ]`, `[x]`, `[SKIPPED]`)
- Commands (next, skip, redo, status, abandon)
- Automation rules (execution, archiving, error handling)

### Phase Files
Individual prompts in `.audit/phases/NN-slug.md`. Each contains:
- Context (why this change)
- Goal (one sentence)
- Files (what to create/modify)
- Plan (step-by-step)
- Acceptance criteria
- Rollback commands

### CURRENT.md
Full audit report for user reference. Gets archived to `~/Documents/Audits/` on completion.

---

## Commands (User → Claude Code)

| Command | Action |
|---------|--------|
| `next` | Execute next incomplete phase |
| `skip` | Mark current phase as SKIPPED |
| `skip phase N` | Skip specific phase |
| `redo N` | Re-run phase N |
| `status` | Show phase checklist |
| `abandon` | Delete .audit/ without archiving |

---

## Automation Rules

### Phase Execution
1. Find first `[ ]` phase
2. Read `.audit/phases/NN-*.md`
3. Execute instructions
4. Run verification (build, test)
5. On success: mark `[x]`, report done
6. On failure: retry up to 3 times, then stop

### Completion
When all phases are `[x]` or `[SKIPPED]`:
1. Run final `make test`
2. Commit uncommitted changes
3. Archive CURRENT.md to `~/Documents/Audits/{project}/`
4. Create git tag `audit/{date}-{slug}`
5. Delete `.audit/` folder
6. Report summary

---

## Creating New Audits

When user asks for an audit:

1. Analyze their codebase (via manifest, uploads, or description)
2. Identify issues by category and severity
3. Create improvement phases (ordered by risk: low → high)
4. Generate setup block using templates
5. Deliver to user

See `docs/creating-audits.md` for detailed instructions.

---

## File Locations

| What | Where |
|------|-------|
| User's global config | `~/.claude/CLAUDE.md` |
| Active audit | `{project}/.audit/` |
| Archives | `~/Documents/Audits/{project}/` |
| Phaser templates | `~/Projects/Phaser/templates/` |

---

*Phaser v1.8.1*
