# Changelog

All notable changes to Phaser will be documented in this file.

## [1.4.0] - 2025-12-05

### Added

#### Audit Replay

- `phaser replay run <slug>` — Replay an audit to detect regressions
- `phaser replay list` — List audits available for replay
- `phaser replay show <slug>` — Show audit details for replay
- Detects contract violations that have reappeared
- Detects file regressions (deleted files reappearing, created files missing)
- `--fail-on-regression` flag for CI integration
- `--scope` flag to check only contracts or files
- Replay history stored in `.phaser/replays.json`

#### Specifications

- `specs/replay.md` — Replay feature specification

### Changed

- Version bumped to 1.4.0
- Updated `phaser version` output to list Replay feature

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
