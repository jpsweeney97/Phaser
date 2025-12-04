# Phaser Quick Reference

The audit automation system for Claude Code.

---

## Commands

| Say This | Claude Code Does |
|----------|------------------|
| `next` | Execute next incomplete phase |
| `continue` | Same as next |
| `proceed` | Same as next |
| `go` | Same as next |
| `skip` | Skip next incomplete phase |
| `skip phase 3` | Skip specific phase |
| `redo 2` | Re-run phase 2 |
| `redo phase 5` | Re-run phase 5 |
| `status` | Show phase checklist |
| `abandon` | Delete audit without archiving |
| `show full audit` | Display CURRENT.md |

---

## Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. I deliver audit → You paste setup block                         │
│                                                                     │
│  2. Claude Code creates .audit/ folder                              │
│                                                                     │
│  3. You say "next" repeatedly                                       │
│     └── Claude Code executes phases                                 │
│     └── Marks complete on success                                   │
│     └── 3 retries on failure, then stops                            │
│                                                                     │
│  4. All phases done → Auto-completion sequence:                     │
│     └── Run final test suite                                        │
│     └── Commit any uncommitted changes                              │
│     └── Archive to ~/Documents/Audits/{project}/                    │
│     └── Create git tag: audit/{date}-{slug}                         │
│     └── Delete .audit/ folder                                       │
│     └── Report summary                                              │
│                                                                     │
│  5. You (optional): git push --tags                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## What Happens at Completion

When the last phase finishes, Claude Code automatically:

| Step | What | Command |
|------|------|---------|
| 1 | Final test | `make test` |
| 2 | Commit stragglers | `git add -A && git commit -m "Complete {slug} audit"` |
| 3 | Archive report | Copy to `~/Documents/Audits/` |
| 4 | Tag milestone | `git tag audit/{date}-{slug}` |
| 5 | Cleanup | Delete `.audit/` folder |
| 6 | Summary | Show commits, tag, archive path |

**Your only action:** Optionally `git push --tags`

---

## File Locations

| What | Where |
|------|-------|
| Active audit | `{project}/.audit/` |
| Full report | `{project}/.audit/CURRENT.md` |
| Context + rules | `{project}/.audit/CONTEXT.md` |
| Phase prompts | `{project}/.audit/phases/` |
| Archives | `~/Documents/Audits/{project}/` |
| Global config | `~/.claude/CLAUDE.md` |

---

## Phase Status Markers

| Marker | Meaning |
|--------|---------|
| `[ ]` | Incomplete (pending) |
| `[x]` | Complete (verified) |
| `[SKIPPED]` | Skipped by user |

---

## Archive Naming

| Scenario | Filename |
|----------|----------|
| All complete | `2024-12-04-audit-slug.md` |
| Some skipped | `2024-12-04-audit-slug.md` |
| All skipped | `2024-12-04-audit-slug-SKIPPED.md` |
| Interrupted by new audit | `2024-12-04-audit-slug-INCOMPLETE.md` |
| Duplicate | `2024-12-04-audit-slug-2.md` |

---

## Git Tags

| Scenario | Tag Name |
|----------|----------|
| Normal completion | `audit/2024-12-04-architecture-refactor` |
| Duplicate | `audit/2024-12-04-architecture-refactor-2` |

---

## One-Time Setup

1. Update `~/.claude/CLAUDE.md` with audit system reference (see Deliverable 1)
2. Done — all projects inherit this

---

## Per-Audit Setup

1. I deliver a setup block
2. Open Claude Code in project: `cd ~/Projects/YourProject && claude`
3. Paste: "Set up this audit" + the block
4. Claude Code confirms ready
5. Say "next" to begin

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No active audit found" | Run setup block first |
| Phase keeps failing | Say "skip" and move on, or fix manually |
| Wrong phase ran | Say "redo N" for the correct phase |
| Want to start over | Say "abandon", then re-run setup block |
| Archive didn't happen | Check `~/Documents/Audits/` manually |
| Tag already exists | Claude Code appends -2, -3, etc. |

---

## Tips

- **Don't manually commit between phases** — Claude Code commits after each phase
- **Read phase prompts** — they're in `.audit/phases/` if you want to preview
- **Edit prompts if needed** — `.audit/` files are yours to modify
- **Multiple projects** — each has its own `.audit/`, no conflicts

---

## Emergency Rollback

If everything goes wrong:

```bash
# Undo all changes since last commit
git checkout -- .

# Remove audit folder manually
rm -rf .audit/

# Start fresh
```

---

*Phaser v1 — December 2024*
