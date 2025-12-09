# Specification: Phaser CLI

**Module:** `tools/cli.py`  
**Version:** 1.7.0  
**Status:** Stable

---

## 1. Overview

The Phaser CLI provides a unified command-line interface for audit automation. All features are accessible via the `phaser` command with subcommands.

```bash
phaser <command> [subcommand] [options] [arguments]
```

---

## 2. Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--verbose` | `-v` | Enable verbose output |
| `--quiet` | `-q` | Suppress non-essential output |
| `--version` | | Show version and exit |
| `--help` | | Show help and exit |

---

## 3. Command Reference

### 3.1 Bridge Commands

#### `phaser validate <file>`

Validate an audit document without executing.

```bash
phaser validate AUDIT.md
phaser validate AUDIT.md --strict
phaser validate AUDIT.md --json
```

| Option | Description |
|--------|-------------|
| `--strict` | Treat warnings as errors |
| `--json` | Output as JSON |

**Exit Codes:**
- `0`: Valid document
- `1`: Validation errors

---

#### `phaser prepare <file>`

Split audit document into phase files and generate execution prompt.

```bash
phaser prepare AUDIT.md
phaser prepare AUDIT.md --project ~/Projects/MyApp
phaser prepare AUDIT.md --print-prompt
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project` | `.` | Target project directory |
| `--output-dir` | `audit-phases` | Phase files directory |
| `--no-clipboard` | false | Don't copy prompt to clipboard |
| `--print-prompt` | false | Print prompt to stdout |
| `--dry-run` | false | Show what would be done |
| `--skip-validation` | false | Skip document validation |
| `--force` | false | Overwrite existing audit-phases/ |

**Creates:**
```
project/
├── audit-phases/
│   ├── setup.md
│   └── phase-NN.md ...
├── .audit-meta/
│   ├── phaser-version
│   └── baseline-tests
└── AUDIT.md (copy)
```

---

#### `phaser execute <file>`

Prepare audit and launch Claude Code for autonomous execution.

```bash
phaser execute AUDIT.md
phaser execute AUDIT.md --no-permissions
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project` | `.` | Target project directory |
| `--output-dir` | `audit-phases` | Phase files directory |
| `--no-permissions` | false | Don't grant Claude Code permissions |
| `--force` | false | Overwrite existing files |

**Requirements:**
- Claude Code CLI must be installed (`claude` command available)

---

### 3.2 Analytics Commands

#### `phaser analytics show`

Display execution history and statistics.

```bash
phaser analytics show
phaser analytics show --last 10
phaser analytics show --status success
phaser analytics show --format json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--last` | `5` | Number of executions to show |
| `--since` | | Show executions since date |
| `--until` | | Show executions until date |
| `--status` | `all` | Filter: `success`, `partial`, `failed`, `all` |
| `--format` | `table` | Output: `table`, `json`, `markdown` |
| `--verbose` | false | Show per-phase details |
| `--project` | `.` | Project directory |

---

#### `phaser analytics export`

Export analytics data to file.

```bash
phaser analytics export -o report.json
phaser analytics export --format csv -o history.csv
```

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `json` | Output: `json`, `markdown`, `csv` |
| `--output` | stdout | Output file path |
| `--since` | | Export executions since date |
| `--until` | | Export executions until date |
| `--project` | `.` | Project directory |

---

#### `phaser analytics import`

Import execution report into analytics.

```bash
phaser analytics import EXECUTION_REPORT.md
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project` | `.` | Project directory |

---

#### `phaser analytics clear`

Clear analytics data.

```bash
phaser analytics clear --all
phaser analytics clear --before 2025-01-01
```

| Option | Description |
|--------|-------------|
| `--all` | Clear all data |
| `--before` | Clear executions before date |
| `--force` | Skip confirmation prompt |
| `--dry-run` | Show what would be deleted |
| `--project` | Project directory |

---

#### `phaser analytics delete <id>`

Delete specific execution record.

```bash
phaser analytics delete abc123
```

---

### 3.3 Contract Commands

#### `phaser check`

Check all contracts against codebase (CI integration).

```bash
phaser check
phaser check --fail-on-error
phaser check --format json
```

| Option | Description |
|--------|-------------|
| `--root` | Project root directory |
| `--fail-on-error` | Exit 1 if any contract fails |
| `--format` | Output: `text`, `json` |

---

#### `phaser contracts list`

List configured contracts.

```bash
phaser contracts list
phaser contracts list --verbose
```

---

#### `phaser contracts check`

Check specific contract.

```bash
phaser contracts check no-force-unwrap
```

---

### 3.4 Enforce Commands

#### `phaser enforce check`

Run contract enforcement (hook integration).

```bash
echo '{"tool_name":"Write",...}' | phaser enforce check --stdin
phaser enforce check --file input.json
```

| Option | Description |
|--------|-------------|
| `--stdin` | Read hook input from stdin |
| `--file` | Read hook input from file |
| `--severity` | Filter: `error`, `warning`, `all` |

**Exit Codes:**
- `0`: Success (allow or deny decision made)
- `3`: Malformed input

---

#### `phaser enforce install`

Install Claude Code hooks for contract enforcement.

```bash
phaser enforce install
phaser enforce install --dry-run
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would be installed |
| `--force` | Overwrite existing hooks |

---

### 3.5 Diff Commands

#### `phaser diff capture`

Capture directory manifest.

```bash
phaser diff capture .
phaser diff capture ~/Projects/App -o manifest.yaml
```

---

#### `phaser diff compare`

Compare two manifests.

```bash
phaser diff compare pre.yaml post.yaml
phaser diff compare pre.yaml post.yaml --detailed
```

---

### 3.6 Simulation Commands

#### `phaser simulate run`

Run audit in simulation mode.

```bash
phaser simulate run --audit-id my-audit
phaser simulate run --phases 1-5
```

---

#### `phaser simulate status`

Show simulation status.

```bash
phaser simulate status
```

---

#### `phaser simulate commit`

Commit simulation changes.

```bash
phaser simulate commit
```

---

#### `phaser simulate rollback`

Rollback simulation changes.

```bash
phaser simulate rollback
```

---

### 3.7 Branch Commands

#### `phaser branches start`

Start branch-per-phase mode.

```bash
phaser branches start --audit my-audit
```

---

#### `phaser branches status`

Show branch mode status.

```bash
phaser branches status
```

---

#### `phaser branches merge`

Merge phase branches.

```bash
phaser branches merge --squash
```

---

### 3.8 Other Commands

#### `phaser manifest`

Capture manifest (alias for `phaser diff capture`).

```bash
phaser manifest .
phaser manifest ~/Projects/App -o manifest.yaml
```

---

#### `phaser version`

Show version and feature information.

```bash
phaser version
```

---

#### `phaser info`

Show Phaser configuration info.

```bash
phaser info
phaser info --global
phaser info --project
```

---

#### `phaser reverse`

Generate audit from git history.

```bash
phaser reverse --since HEAD~10
```

---

#### `phaser negotiate`

Customize phases before execution.

```bash
phaser negotiate AUDIT.md
```

---

#### `phaser replay`

Replay past audit execution.

```bash
phaser replay --execution abc123
```

---

#### `phaser insights`

View codebase insights.

```bash
phaser insights show
phaser insights trend
```

---

#### `phaser verify`

Run post-audit verification.

```bash
phaser verify AUDIT.md
```

---

#### `phaser ci`

CI integration commands.

```bash
phaser ci check
phaser ci report
```

---

## 4. Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error / validation failure |
| `2` | Usage error (invalid arguments) |
| `3` | Malformed input (enforce) |

---

## 5. Environment Variables

| Variable | Description |
|----------|-------------|
| `PHASER_STORAGE_DIR` | Override storage location |
| `NO_COLOR` | Disable colored output |

---

## 6. Configuration

CLI reads configuration from:

1. `~/.phaser/config.yaml` (global)
2. `.phaser/config.yaml` (project)

Project config takes precedence.

---

## 7. Output Formats

### 7.1 Table (default)

```
┌────────────┬────────┬────────┬───────────┐
│ Execution  │ Status │ Phases │ Tests     │
├────────────┼────────┼────────┼───────────┤
│ abc123     │ ✓      │ 5/5    │ +12 (142) │
│ def456     │ ⚠      │ 3/5    │ +8 (150)  │
└────────────┴────────┴────────┴───────────┘
```

### 7.2 JSON

```json
{
  "records": [...],
  "stats": {...},
  "query": {...}
}
```

### 7.3 Markdown

```markdown
# Execution Report

| Execution | Status | Phases | Tests |
|-----------|--------|--------|-------|
| abc123    | ✓      | 5/5    | +12   |
```

### 7.4 CSV

```csv
execution_id,status,phases_completed,phases_total,tests_added
abc123,success,5,5,12
```

---

## 8. Subcommand Groups

| Group | Module | Description |
|-------|--------|-------------|
| `diff` | `tools/diff.py` | Manifest operations |
| `contracts` | `tools/contracts.py` | Contract management |
| `simulate` | `tools/simulate.py` | Simulation mode |
| `branches` | `tools/branches.py` | Branch-per-phase |
| `ci` | `tools/ci.py` | CI integration |
| `insights` | `tools/insights.py` | Analytics views |
| `replay` | `tools/replay.py` | Execution replay |
| `reverse` | `tools/reverse.py` | Reverse audit |
| `negotiate` | `tools/negotiate.py` | Phase customization |
| `verify` | `tools/validate.py` | Post-audit checks |
| `enforce` | `tools/enforce.py` | Hook enforcement |
| `analytics` | `tools/analytics.py` | Execution history |

---

## 9. Dependencies

- `click`: Command-line framework
- `pyperclip`: Clipboard support (optional)

---

*Specification for tools/cli.py — Phaser v1.7.0*
