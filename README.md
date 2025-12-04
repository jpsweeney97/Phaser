# Phaser

Audit automation for Claude Code.

---

## What Is Phaser?

Phaser connects two Claude experiences:

1. **Claude (claude.ai)** — Analyzes your codebase and generates a structured audit with executable phases
2. **Claude Code** — Executes those phases automatically when you say "next"

You paste an audit, say "next" repeatedly, and your codebase improves phase by phase.

---

## Setup (One Time)

Add the Phaser trigger to your global Claude Code config:

```bash
grep -q "AUDIT-SYSTEM" ~/.claude/CLAUDE.md 2>/dev/null || cat global-claude-snippet.md >> ~/.claude/CLAUDE.md
```

This command is idempotent—safe to run multiple times without creating duplicates.

Or manually copy the content from `global-claude-snippet.md` into your `~/.claude/CLAUDE.md` file's "Project-Specific Context" section.

---

## Usage

### Security Note: Permission Flag

Phaser requires `--dangerously-skip-permissions` because it needs to:

- Create the `.audit/` directory and files
- Modify `.gitignore`
- Create archives in `~/Documents/Audits/`
- Create git tags

**Risks:**

- Claude Code can modify any file without prompting
- Malformed audit blocks could write to unintended paths
- No confirmation before destructive operations

**Mitigations:**

- Only use with audits from trusted sources (your own claude.ai sessions)
- Review the setup block before pasting
- Ensure you have git commits to revert to

**Alternative:** Run without the flag and approve each file operation manually (slower but safer for untrusted audits).

### 1. Get an Audit

In claude.ai, ask for an audit:

> "Audit my project. Here's the manifest: [paste or upload]"

Claude generates a setup block.

### 2. Install the Audit

```bash
cd ~/Projects/YourProject
claude --dangerously-skip-permissions
```

Then paste:
```
Set up this audit:
[paste the setup block]
```

### 3. Execute Phases

```
next
```

Repeat until done. Claude Code handles everything:
- Executes each phase
- Runs tests
- Marks progress
- Archives on completion
- Creates git tag

### 4. Push Tag (Optional)

```bash
git push --tags
```

---

## Commands

| Say | Does |
|-----|------|
| `next` | Run next phase |
| `skip` | Skip current phase |
| `skip phase 3` | Skip specific phase |
| `redo 2` | Re-run phase 2 |
| `status` | Show progress |
| `abandon` | Delete audit without saving |

---

## File Structure

When an audit is active:

```
YourProject/
├── .audit/
│   ├── CONTEXT.md      ← Automation rules + status
│   ├── CURRENT.md      ← Full audit report
│   └── phases/
│       ├── 01-*.md     ← Phase 1 prompt
│       ├── 02-*.md     ← Phase 2 prompt
│       └── ...
└── ... your code
```

On completion, archived to:
```
~/Documents/Audits/YourProject/2024-12-04-audit-slug.md
```

---

## Project Contents

```
Phaser/
├── CLAUDE.md                 ← Context for Claude Code
├── README.md                 ← This file
├── global-claude-snippet.md  ← Add to ~/.claude/CLAUDE.md
├── templates/                ← For generating new audits
├── examples/                 ← Sample audits
└── docs/                     ← Additional documentation
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No active audit found" | Paste the setup block first |
| Claude Code ignores "next" | Restart Claude Code, try again |
| Phase fails repeatedly | Say `skip`, or fix manually |
| Keychain dialogs during tests | Ensure Phase 6 mocks KeychainService |

---

## Examples

See `examples/impromptu-setup-block.md` for a complete audit of a macOS SwiftUI app.

---

*Phaser v1.1*
