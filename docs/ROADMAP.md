# Phaser Roadmap

Future features and enhancements under consideration.

---

## v1.9 (Planned)

### Auto-Execute Mode

**Problem:** Running multi-phase audits requires saying "next" repeatedly, which adds friction for trusted audits on your own codebase.

**Solution:** Add `--auto` flag to execute all phases without manual intervention.

```bash
phaser execute --auto              # Run all phases without stopping
phaser execute --auto --dry-run    # Simulate all, then prompt once to confirm
phaser execute --auto --fail-fast  # Stop on first phase failure (default)
phaser execute --auto --continue   # Continue past failures, report at end
```

**CLI Integration:**
```bash
# Full workflow: prepare audit + execute all phases
phaser execute audit.md --auto

# Or with simulation preview first
phaser execute audit.md --auto --dry-run
```

**Safety Features:**
- `--dry-run` shows what would happen before committing
- `--fail-fast` (default) stops at first failure
- Progress logged to `.audit/execution.log`
- Can still `abandon` or Ctrl+C to stop

**Implementation Notes:**
- Modify CONTEXT.md automation rules to support continuous mode
- Add execution log for post-hoc review
- Consider `--pause-on-warning` flag for hybrid control

---

### Bash File Write Detection

**Problem:** Files written via `echo > file` or `cat > file` in Bash bypass the Write/Edit hooks.

**Evaluation:** Assess feasibility of hooking Bash tool for file write patterns.

**Risk:** High false positive rate. Many legitimate uses of redirection.

**Decision:** Evaluate, may defer to v2.0 or document as known limitation.

---

### Auto-Fix Suggestions

**Problem:** When enforcement blocks a violation, Claude must figure out the fix.

**Solution:** Contracts could optionally include fix suggestions or transformation rules.

```yaml
rule_id: no-print
type: forbid_pattern
pattern: 'print\('
message: Use logging instead
fix_hint: "Replace print() with logging.info()"
# Future: fix_pattern for auto-replacement
```

**Risk:** Auto-fix could introduce bugs. Start with hints only.

---

## v2.0 (Future)

### Plugin Architecture

Package Phaser as a Claude Code plugin with:
- Commands exposed via plugin manifest
- Hooks bundled in plugin
- Distribution via plugin marketplace

### Subagent Orchestration

Parallel audit execution via isolated subagent contexts for large codebases.

### Remote Contracts

Fetch contracts from a URL or registry for team-wide enforcement.

---

## Deferred / Not Planned

| Feature | Reason |
|---------|--------|
| IDE/LSP integration | Claude Code is the IDE layer |
| Daemon/watch mode | Hooks provide this already |
| Network calls in enforce | Offline-first design principle |

---

*Last updated: 2025-12-07*
