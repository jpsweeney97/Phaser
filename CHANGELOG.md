# Changelog

All notable changes to Phaser will be documented in this file.

## [1.3.0] - 2025-12-05

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

#### Specifications

- `specs/ci.md` — CI Check feature specification
- `specs/insights.md` — Insights feature specification

### Changed

- Version bumped to 1.3.0
- Updated `phaser version` output to list new features

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
