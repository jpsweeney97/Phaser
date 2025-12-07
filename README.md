# Phaser

Audit automation for Claude Code.

---

## What's New in v1.8

- **Hook-Based Enforcement:** Real-time contract checking via Claude Code hooks
- **Inline Ignores:** Suppress violations with `# phaser:ignore <rule-id>`
- **Install Command:** `phaser enforce install` for quick hook setup

## What's New in v1.7

- **Reverse Audit:** Generate audit documents from existing git history
- **Phase Negotiation:** Customize phases before execution (split, merge, reorder, skip)
- **Replay:** Re-run past audits to detect regressions
- **CI Integration:** GitHub Actions workflow generation for contract checking
- **Insights & Analytics:** Statistics and trends from audit history
- **Simulation:** Preview changes before committing with automatic rollback
- **Branch-per-phase:** Create reviewable git branches for each phase
- **Audit Contracts:** Extract and enforce quality rules from audit findings
- **Manifest Diffing:** See exactly what changed during each phase

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

This command is idempotent — safe to run multiple times without creating duplicates.

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

| Say            | Does                        |
| -------------- | --------------------------- |
| `next`         | Run next phase              |
| `skip`         | Skip current phase          |
| `skip phase 3` | Skip specific phase         |
| `redo 2`       | Re-run phase 2              |
| `status`       | Show progress               |
| `abandon`      | Delete audit without saving |

---

## Post-Audit Validation

After an audit completes, validate that all changes were applied correctly:

1. Audit completion generates a manifest at:
   `~/Documents/Audits/{project}/manifests/{date}-{slug}-post.yaml`

2. Use the validation prompt template:
   `templates/validation-prompt.template.md`

3. Submit to claude.ai with your audit goals and manifest

See `docs/post-audit-validation.md` for detailed instructions.

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

On completion, archived (see Archive Location below).

---

## Archive Location

Completed audits are archived to:

- **macOS:** `~/Documents/Audits/{project}/`
- **Linux:** `~/.local/share/phaser/audits/{project}/`

Override with: `export PHASER_ARCHIVE_DIR=~/my/custom/path`

---

## Project Contents

```
Phaser/
├── CLAUDE.md                 ← Context for Claude Code
├── README.md                 ← This file
├── global-claude-snippet.md  ← Add to ~/.claude/CLAUDE.md
├── specs/                    ← Feature specifications
├── tools/                    ← CLI modules
├── tests/                    ← Test suite (391 tests)
├── templates/                ← Audit templates
├── examples/                 ← Sample audits
└── docs/                     ← Additional documentation
```

---

## Troubleshooting

| Problem                    | Solution                                                   |
| -------------------------- | ---------------------------------------------------------- |
| "No active audit found"    | Paste the setup block first                                |
| Claude Code ignores "next" | Restart Claude Code, try again                             |
| Phase fails repeatedly     | Say `skip`, or fix manually                                |
| Tests require credentials  | Check if audit includes mock/stub phases for auth services |

---

## Examples

See `examples/impromptu-setup-block.md` for a complete audit of a macOS SwiftUI app.

---

## CLI Reference

Phaser v1.7 provides a unified CLI for all operations:

```bash
phaser --help              # Show all commands
phaser version             # Show version and features
```

### Core Commands

```bash
phaser check               # Run all contract checks (CI integration)
phaser manifest <dir>      # Capture directory manifest
phaser info                # Show Phaser configuration
```

### Diff (Manifest Comparison)

```bash
phaser diff capture <dir>            # Capture manifest to file
phaser diff compare <a> <b>          # Compare two manifests
```

### Contracts (Quality Rules)

```bash
phaser contracts list                # List all contracts
phaser contracts check               # Check all contracts
phaser contracts create              # Create a new contract
phaser contracts enable <id>         # Enable a contract
phaser contracts disable <id>        # Disable a contract
```

### Enforce (Hook-Based Contracts)

Continuous contract enforcement via Claude Code hooks:

```bash
# Install hooks (adds to .claude/settings.json)
phaser enforce install

# Or install to user settings (applies to all projects)
phaser enforce install --scope user

# Preview without writing
phaser enforce install --dry-run
```

Once installed, contracts are checked automatically:

- **PreToolUse**: Blocks edits that violate `error`-severity contracts
- **PostToolUse**: Warns about `warning`-severity violations

**Contracts location:**

- Project: `.claude/contracts/*.yaml`
- User: `~/.phaser/contracts/*.yaml`

**Inline ignores:**

```python
x = 1  # phaser:ignore rule-id
# phaser:ignore-next-line rule-id
y = 2
```

### Simulate (Dry-Run)

```bash
phaser simulate run                  # Run audit in simulation mode
phaser simulate status               # Show simulation status
phaser simulate commit               # Keep simulated changes
phaser simulate rollback             # Rollback simulated changes
```

### Branches (Branch-per-Phase)

```bash
phaser branches enable               # Enable branch mode
phaser branches status               # Show branch status
phaser branches merge                # Merge all phase branches
phaser branches cleanup              # Delete merged branches
```

### CI (Continuous Integration)

```bash
phaser ci init                       # Generate GitHub Actions workflow
phaser ci status                     # Show CI configuration status
phaser ci remove                     # Remove CI workflow file
```

### Insights (Analytics)

```bash
phaser insights summary              # High-level statistics
phaser insights audits               # List audits with stats
phaser insights contracts            # Contract violation stats
phaser insights files                # File change hotspots
phaser insights events               # Event statistics
phaser insights trends               # Trends over time
```

### Replay (Regression Detection)

```bash
phaser replay list                   # List audits available for replay
phaser replay show <id>              # Show audit details
phaser replay run <id>               # Replay audit, check for regressions
```

### Reverse (Generate from Git)

```bash
phaser reverse generate <range>      # Generate audit from commits
phaser reverse preview <range>       # Preview inferred phases
phaser reverse commits <range>       # List commits in range
phaser reverse diff <range>          # Show full diff
```

### Negotiate (Customize Phases)

```bash
phaser negotiate interactive <file>  # Interactive customization
phaser negotiate preview <file>      # Preview phases
phaser negotiate skip <file> -p 1,3  # Quick skip phases
phaser negotiate apply <file> --ops ops.yaml  # Batch apply
phaser negotiate export <file> -o out.md      # Export result
phaser negotiate status <file>       # Session status
```

---

### CI Integration

Use `phaser check` in your CI pipeline to enforce contracts:

```yaml
# GitHub Actions example
- name: Check contracts
  run: phaser check --fail-on-error
```

Or generate a complete workflow:

```bash
phaser ci init --python-version 3.12
```

---

*Phaser v1.8.0*
