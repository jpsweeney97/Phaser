# Changelog

All notable changes to Phaser will be documented in this file.

## [1.7.0] - 2025-12-06

### Added

#### Analytics (`phaser analytics`)

- `phaser analytics show` — Display execution history with metrics
- `phaser analytics show --format json|csv|markdown` — Export formats
- `phaser analytics export <file>` — Export to file
- `phaser analytics import <report.md>` — Import from EXECUTION_REPORT.md
- `phaser analytics clear` — Clear analytics data (with --dry-run, --force)

#### Analytics Data Model

- `ExecutionRecord` — Full audit execution with computed properties
- `PhaseRecord` — Individual phase results
- `AggregatedStats` — Cross-execution statistics
- `AnalyticsQuery` — Flexible filtering (date range, status, project)
- Persistent storage in `.phaser/analytics/` per project

#### Specifications

- `docs/specs/specs-analytics-v1.md` — Analytics feature specification

### Changed

- Version bumped to 1.7.0

### Stats

- 131 new tests (499 → 630 total)
- 3,500+ lines added across analytics module, CLI, and tests

---

## [1.5.0] - 2025-12-05

### Added

#### CI Integration (`phaser ci`)

- `phaser ci init` — Generate GitHub Actions workflow for contract checking
- `phaser ci status` — Show CI configuration status
- `phaser ci remove` — Remove CI workflow file
- Supports customizable Python version, triggers, and branches
- Dry-run mode for previewing workflow

#### Insights & Analytics (`phaser insights`)

- `phaser insights summary` — High-level audit statistics
- `phaser insights audits` — List audits with phase counts and duration
- `phaser insights contracts` — Contract violation statistics
- `phaser insights files` — File change hotspots
- `phaser insights events` — Event type statistics
- `phaser insights trends` — Trends over time (daily/weekly/monthly)
- Supports `--global` flag for cross-project analytics
- Flexible date filtering with relative formats (7d, 4w, 3m)

#### Reverse Audit (`phaser reverse`)

- `phaser reverse generate <commit-range>` — Generate audit document from git diff
- `phaser reverse preview <commit-range>` — Preview inferred phases
- `phaser reverse commits <commit-range>` — List commits with details
- `phaser reverse diff <commit-range>` — Show full diff
- Multiple grouping strategies: commits, directories, filetypes, semantic
- Output formats: markdown, yaml, json
- Automatic phase title and category inference
- Support for conventional commit parsing

#### Phase Negotiation (`phaser negotiate`)

- `phaser negotiate <audit-file>` — Interactive phase customization
- `phaser negotiate preview <audit-file>` — Preview phases in audit
- `phaser negotiate skip <audit-file> --phases N,M` — Quick skip phases
- `phaser negotiate apply <audit-file> --ops <file.yaml>` — Batch apply operations
- `phaser negotiate export <audit-file>` — Export negotiated audit
- `phaser negotiate status <audit-file>` — Show session status
- Operations: split, merge, reorder, skip, modify, reset
- Session persistence with resume capability

#### Specifications

- `specs/ci.md` — CI Check feature specification
- `specs/insights.md` — Insights feature specification
- `specs/reverse.md` — Reverse Audit feature specification
- `specs/negotiate.md` — Phase Negotiation feature specification

### Changed

- Version bumped to 1.5.0
- Updated `phaser version` output to list all new features

---

## [1.2.0] - 2025-12-05

### Added

#### Learning Loop (Storage + Events)

- `.phaser/` directory for persistent state
- `PhaserStorage` class for audit history, events, config
- `EventEmitter` class with 12 event types
- Event replay capability

#### Audit Diffs

- `capture_manifest()` — Snapshot directory state
- `compare_manifests()` — Compute changes
- Pre/post manifest capture during audits
- `phaser diff` CLI commands

#### Audit Contracts

- 6 rule types: forbid_pattern, require_pattern, file_exists, file_not_exists, file_contains, file_not_contains
- `check_contract()` — Find violations
- `check_all_contracts()` — Batch checking for CI
- `phaser contracts` CLI commands
- `phaser check` for CI integration

#### Simulation

- `begin_simulation()` — Enter sandbox
- `rollback_simulation()` — Undo all changes
- Git stash integration
- File change tracking
- `phaser simulate` CLI commands

#### Branch-per-phase

- `begin_branch_mode()` — Initialize
- `create_phase_branch()` — Named branches
- `merge_all_branches()` — Squash/rebase/merge
- `phaser branches` CLI commands

#### Unified CLI

- `phaser` command as single entry point
- Subcommands: diff, contracts, simulate, branches
- CI-friendly `phaser check` command

### Changed

- Templates updated for v1.2 features
- Documentation expanded

### Infrastructure

- 7 specification documents in `specs/`
- 200+ tests
- pyproject.toml with entry points

## [1.1.0] - 2025-12-04

### Added

- Initial Phaser release
- Audit automation for Claude Code
- Setup block parsing
- Phase execution with verification
- Auto-archive on completion
- Git tag creation
- Stale audit detection
- Archive incomplete command
