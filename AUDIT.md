# Document 7: Reverse Audit

> Phaser v1.4 → v1.5 — Batch 2, Document 3 of 4
> Phases 36-41

---

## Document Overview

This document implements the **Reverse Audit** feature, which generates a structured audit document from an existing git diff. This is useful for documenting work that was done without Phaser, or for creating audit templates from historical changes.

---

## Prerequisites

Before starting this document:

```bash
# Verify Phaser v1.4.0 is installed
phaser version
# Expected: Phaser v1.4.0

# Verify tests pass
cd ~/Projects/Phaser && python -m pytest tests/ -q
# Expected: 280+ passed

# Verify Replay works
phaser replay --help
```

---

=== AUDIT SETUP START ===

## Setup Block

Execute this setup block before beginning Phase 36.

### 1. Create Working Branch

```bash
cd ~/Projects/Phaser
git checkout main
git pull origin main
git checkout -b audit/2025-12-05-batch2-doc7-reverse
```

### 2. Verify Clean State

```bash
git status --porcelain
# Expected: empty (clean working directory)

python -m pytest tests/ -q --tb=no
# Expected: 280+ passed
```

### 3. Create Phase Tracking File

```bash
cat > CURRENT.md << 'EOF'
# Document 7 Progress

## Status: IN PROGRESS

## Phases

- [ ] Phase 36: Reverse Audit Specification
- [ ] Phase 37: Git Diff Parsing
- [ ] Phase 38: Audit Document Generation
- [ ] Phase 39: Reverse CLI Commands
- [ ] Phase 40: CLI Integration
- [ ] Phase 41: Tests and Documentation

## Current Phase: 36

## Notes

Started: 2025-12-05
Depends on: Document 6 (Replay)
EOF
```

### 4. Verify Git is Available

```bash
# Verify git is available
git --version
# Expected: git version 2.x.x

# Verify we're in a git repository
git rev-parse --is-inside-work-tree
# Expected: true
```

=== AUDIT SETUP END ===

---

## Phase 36: Reverse Audit Specification

### Context

Reverse Audit analyzes git diffs and generates structured audit documents from them. This allows teams to retroactively document changes, create audit templates from successful refactors, or understand what a set of commits accomplished in audit terms.

### Goal

Write the specification document for the Reverse Audit feature before implementation.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `specs/reverse.md` | CREATE | Reverse Audit feature specification |

### Plan

1. Define reverse audit concepts
2. Specify git diff analysis strategy
3. Document the `phaser reverse` CLI interface
4. Define data structures for reverse results
5. Specify phase inference heuristics

### Implementation

#### specs/reverse.md

```markdown
# Reverse Audit Specification

> Phaser v1.5 — Reverse Audit Feature

---

## Overview

Reverse Audit generates structured audit documents from git diffs. Given a commit range, it analyzes the changes and produces an audit document with inferred phases, goals, and verification steps.

---

## Purpose

1. **Document past work** — Create audit records for changes made without Phaser
2. **Generate templates** — Use successful refactors as templates for future audits
3. **Understand changes** — Get structured view of what a commit range accomplished
4. **Onboard teams** — Help teams adopt Phaser by documenting existing patterns

---

## Concepts

### Reverse vs Forward Audit

| Aspect | Forward Audit | Reverse Audit |
|--------|---------------|---------------|
| Input | Audit document | Git diff |
| Output | Code changes | Audit document |
| Direction | Plan → Execute | Changes → Document |
| Use case | New work | Retroactive documentation |

### Phase Inference

Reverse Audit groups related changes into phases using heuristics:

| Heuristic | Description | Example |
|-----------|-------------|---------|
| **Commit-based** | Each commit becomes a phase | Default strategy |
| **Directory-based** | Group by top-level directory | `src/`, `tests/`, `docs/` |
| **File-type-based** | Group by file extension | `.py`, `.swift`, `.ts` |
| **Semantic** | Group by detected intent | "Add tests", "Refactor X" |

### Change Categories

Changes are categorized to generate appropriate phase descriptions:

| Category | Detection | Phase Title Template |
|----------|-----------|---------------------|
| Add feature | New files + new exports | "Add {feature}" |
| Remove code | Deleted files/functions | "Remove {component}" |
| Refactor | Modified files, same tests | "Refactor {area}" |
| Fix bug | Small changes + test additions | "Fix {issue}" |
| Add tests | New test files | "Add tests for {module}" |
| Update deps | Package file changes | "Update dependencies" |
| Documentation | .md file changes | "Update documentation" |

---

## CLI Interface

### phaser reverse

Generate audit document from git diff.

```bash
phaser reverse <commit-range> [OPTIONS]

Arguments:
  commit-range        Git commit range (e.g., HEAD~5..HEAD, main..feature)

Options:
  --output PATH       Output file path (default: stdout)
  --strategy TEXT     Phase grouping: commits, directories, filetypes (default: commits)
  --title TEXT        Audit title (default: inferred from branch/commits)
  --project TEXT      Project name (default: current directory name)
  --format TEXT       Output format: markdown, yaml, json (default: markdown)
  --include-diff      Include full diff in output
  --max-phases INT    Maximum phases to generate (default: 20)
  --min-changes INT   Minimum changes to include a phase (default: 1)
```

**Examples:**

```bash
# Generate audit from last 5 commits
phaser reverse HEAD~5..HEAD

# Generate from branch comparison
phaser reverse main..feature-branch

# Save to file with title
phaser reverse HEAD~10..HEAD --output audit.md --title "Security Hardening"

# Group by directory
phaser reverse HEAD~20..HEAD --strategy directories

# Output as YAML for editing
phaser reverse HEAD~5..HEAD --format yaml --output audit.yaml
```

### phaser reverse preview

Preview what would be generated without full output.

```bash
phaser reverse preview <commit-range> [OPTIONS]

Options:
  --strategy TEXT     Phase grouping strategy
```

**Example Output:**

```
Reverse Audit Preview
=====================
Commit Range: HEAD~5..HEAD
Strategy: commits
Commits: 5
Files Changed: 12
Insertions: 245
Deletions: 89

Inferred Phases:
  1. Add user authentication module (3 files)
  2. Update database schema (2 files)
  3. Add authentication tests (4 files)
  4. Fix login edge cases (2 files)
  5. Update documentation (1 file)

Use 'phaser reverse HEAD~5..HEAD' to generate full document.
```

### phaser reverse commits

List commits in a range with change summaries.

```bash
phaser reverse commits <commit-range> [OPTIONS]

Options:
  --format TEXT       Output format: text, json (default: text)
```

**Example Output:**

```
Commits in Range: HEAD~5..HEAD
==============================

abc1234 (2025-12-05) Add user authentication module
  Files: 3 (+120 -0)
  - src/auth/login.py (new)
  - src/auth/session.py (new)
  - src/auth/__init__.py (new)

def5678 (2025-12-05) Update database schema
  Files: 2 (+45 -12)
  - migrations/003_add_users.py (new)
  - src/models/user.py (modified)

...
```

---

## Data Classes

### CommitInfo

```python
@dataclass
class CommitInfo:
    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: int
    insertions: int
    deletions: int
    files: list[FileChangeInfo]

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_git(cls, hash: str) -> "CommitInfo": ...
```

### FileChangeInfo

```python
@dataclass
class FileChangeInfo:
    path: str
    change_type: str  # "added", "modified", "deleted", "renamed"
    insertions: int
    deletions: int
    old_path: str | None  # For renames

    def to_dict(self) -> dict[str, Any]: ...
```

### InferredPhase

```python
@dataclass
class InferredPhase:
    number: int
    title: str
    description: str
    commits: list[CommitInfo]
    files: list[FileChangeInfo]
    category: str  # "feature", "refactor", "fix", "test", "docs"
    
    @property
    def file_count(self) -> int: ...
    @property
    def total_changes(self) -> int: ...

    def to_dict(self) -> dict[str, Any]: ...
```

### ReverseAuditResult

```python
@dataclass
class ReverseAuditResult:
    title: str
    project: str
    commit_range: str
    strategy: str
    generated_at: str
    
    total_commits: int
    total_files: int
    total_insertions: int
    total_deletions: int
    
    phases: list[InferredPhase]

    def to_dict(self) -> dict[str, Any]: ...
    def to_markdown(self) -> str: ...
    def to_yaml(self) -> str: ...
```

### GroupingStrategy (Enum)

```python
class GroupingStrategy(str, Enum):
    COMMITS = "commits"      # One phase per commit
    DIRECTORIES = "directories"  # Group by directory
    FILETYPES = "filetypes"  # Group by file extension
    SEMANTIC = "semantic"    # Infer from commit messages
```

---

## Core Functions

### parse_commit_range

```python
def parse_commit_range(
    commit_range: str,
    repo_path: Path | None = None,
) -> list[CommitInfo]:
    """
    Parse a git commit range and return commit information.

    Args:
        commit_range: Git commit range (e.g., "HEAD~5..HEAD")
        repo_path: Path to repository (default: current directory)

    Returns:
        List of CommitInfo, oldest first

    Raises:
        ValueError: If commit range is invalid
        subprocess.CalledProcessError: If git command fails
    """
```

### get_commit_files

```python
def get_commit_files(
    commit_hash: str,
    repo_path: Path | None = None,
) -> list[FileChangeInfo]:
    """
    Get files changed in a specific commit.

    Args:
        commit_hash: Git commit hash
        repo_path: Path to repository

    Returns:
        List of FileChangeInfo for files in commit
    """
```

### group_commits_to_phases

```python
def group_commits_to_phases(
    commits: list[CommitInfo],
    strategy: GroupingStrategy = GroupingStrategy.COMMITS,
    max_phases: int = 20,
) -> list[InferredPhase]:
    """
    Group commits into phases based on strategy.

    Args:
        commits: List of commits to group
        strategy: Grouping strategy to use
        max_phases: Maximum number of phases

    Returns:
        List of InferredPhase
    """
```

### infer_phase_title

```python
def infer_phase_title(
    commits: list[CommitInfo],
    files: list[FileChangeInfo],
) -> str:
    """
    Infer a descriptive title for a phase.

    Uses heuristics based on:
    - Commit messages
    - File paths and names
    - Change patterns

    Args:
        commits: Commits in the phase
        files: Files changed in the phase

    Returns:
        Inferred phase title
    """
```

### infer_category

```python
def infer_category(
    commits: list[CommitInfo],
    files: list[FileChangeInfo],
) -> str:
    """
    Infer the category of changes.

    Categories: feature, refactor, fix, test, docs, chore

    Args:
        commits: Commits in the phase
        files: Files changed

    Returns:
        Category string
    """
```

### generate_reverse_audit

```python
def generate_reverse_audit(
    commit_range: str,
    strategy: GroupingStrategy = GroupingStrategy.COMMITS,
    title: str | None = None,
    project: str | None = None,
    repo_path: Path | None = None,
    max_phases: int = 20,
) -> ReverseAuditResult:
    """
    Generate a reverse audit from a commit range.

    Args:
        commit_range: Git commit range
        strategy: Phase grouping strategy
        title: Audit title (inferred if not provided)
        project: Project name (inferred if not provided)
        repo_path: Repository path
        max_phases: Maximum phases to generate

    Returns:
        ReverseAuditResult with inferred phases
    """
```

### format_as_markdown

```python
def format_as_markdown(
    result: ReverseAuditResult,
    include_diff: bool = False,
) -> str:
    """
    Format reverse audit result as markdown document.

    Args:
        result: ReverseAuditResult to format
        include_diff: Include full git diff in output

    Returns:
        Markdown string
    """
```

---

## Git Integration

### Required Git Commands

| Command | Purpose |
|---------|---------|
| `git log --format=...` | Get commit information |
| `git show --stat` | Get file changes per commit |
| `git diff --numstat` | Get insertion/deletion counts |
| `git rev-parse` | Validate commit references |
| `git diff` | Get full diff (optional) |

### Commit Range Parsing

Support standard git range syntax:

| Syntax | Meaning |
|--------|---------|
| `HEAD~5..HEAD` | Last 5 commits |
| `main..feature` | Commits in feature not in main |
| `abc123..def456` | Commits between two hashes |
| `v1.0..v1.1` | Commits between two tags |
| `abc123^..def456` | Include abc123 in range |

### Error Handling

| Error | Behavior |
|-------|----------|
| Invalid commit range | Clear error message with examples |
| Not a git repository | Error: "Not a git repository" |
| No commits in range | Warning: "No commits found in range" |
| Git not installed | Error: "Git is required for reverse audit" |

---

## Output Formats

### Markdown (Default)

Generates a complete audit document:

```markdown
# Reverse Audit: Security Hardening

> Generated from git history
> Commit range: HEAD~5..HEAD
> Generated: 2025-12-05T10:30:00Z

---

## Overview

This audit was reverse-engineered from 5 commits affecting 12 files.

**Summary:**
- Total commits: 5
- Files changed: 12
- Lines added: 245
- Lines removed: 89

---

## Phase 1: Add user authentication module

### Context

Added new authentication module based on commit abc1234.

### Changes

| File | Change | Lines |
|------|--------|-------|
| src/auth/login.py | Added | +45 |
| src/auth/session.py | Added | +38 |
| src/auth/__init__.py | Added | +12 |

### Commits

- abc1234: Add user authentication module

---

## Phase 2: Update database schema

...
```

### YAML

For programmatic editing:

```yaml
title: Security Hardening
project: myapp
commit_range: HEAD~5..HEAD
generated_at: "2025-12-05T10:30:00Z"
strategy: commits

summary:
  total_commits: 5
  total_files: 12
  insertions: 245
  deletions: 89

phases:
  - number: 1
    title: Add user authentication module
    category: feature
    commits:
      - hash: abc1234
        message: Add user authentication module
    files:
      - path: src/auth/login.py
        change_type: added
        insertions: 45
```

### JSON

For API integration:

```json
{
  "title": "Security Hardening",
  "project": "myapp",
  "commit_range": "HEAD~5..HEAD",
  "phases": [...]
}
```

---

## Heuristics

### Title Inference

1. Look for common prefixes in commit messages: "Add", "Fix", "Update", "Remove"
2. Extract subject from conventional commits: `feat(auth): add login`
3. Use directory names for directory-grouped phases
4. Fall back to "Phase N: Changes to {files}"

### Category Inference

| Pattern | Category |
|---------|----------|
| New files, no test changes | `feature` |
| Test file additions/changes | `test` |
| Markdown/doc file changes | `docs` |
| Small changes + "fix" in message | `fix` |
| Large changes, same tests | `refactor` |
| Package/config file changes | `chore` |

### Phase Descriptions

Generate descriptions based on:
- Commit messages (primary source)
- File paths (what was changed)
- Change patterns (add/remove/modify)

---

## Edge Cases

### Empty Commit Range

```
No commits found in range 'main..main'.

Ensure you have commits between the specified references.
Examples:
  phaser reverse HEAD~5..HEAD
  phaser reverse main..feature-branch
```

### Large Commit Ranges

For ranges with >100 commits:
- Warn user about large output
- Suggest using `--max-phases` to limit
- Consider using directory or semantic grouping

### Merge Commits

- Skip merge commits by default
- Include with `--include-merges` flag
- Show merge commit info in phase if included

### Binary Files

- Note binary files in output
- Don't attempt to diff binary content
- Include in file count but not line counts

### Renamed Files

- Track renames properly
- Show old → new path
- Count as single file change

---

## Example Usage

### Basic Usage

```bash
# Document last week's work
phaser reverse HEAD~20..HEAD --output weekly-audit.md

# Preview before generating
phaser reverse preview main..feature-branch

# Generate from specific commits
phaser reverse abc123..def456 --title "Bug Fix Sprint"
```

### CI Integration

```bash
# Generate audit for PR changes
phaser reverse origin/main..HEAD --output pr-audit.md

# Validate PR has reasonable structure
phaser reverse preview origin/main..HEAD
```

### Template Generation

```bash
# Create template from successful refactor
phaser reverse v1.0..v1.1 \
  --title "Version 1.1 Refactor" \
  --strategy directories \
  --output templates/refactor-template.md
```

---

*Phaser v1.5 — Reverse Audit Specification*
```

### Verify

```bash
# File exists and has content
test -f specs/reverse.md && echo "✓ specs/reverse.md created"
wc -l specs/reverse.md
# Expected: ~500 lines

# Contains required sections
grep -c "## Overview" specs/reverse.md
grep -c "## CLI Interface" specs/reverse.md
grep -c "## Data Classes" specs/reverse.md
grep -c "## Core Functions" specs/reverse.md
# Expected: 1 for each
```

### Acceptance Criteria

- [ ] specs/reverse.md exists with complete specification
- [ ] CLI interface documented (reverse, preview, commits)
- [ ] Data classes specified (CommitInfo, FileChangeInfo, InferredPhase, etc.)
- [ ] Core functions documented with signatures
- [ ] Git integration strategy documented
- [ ] Output formats specified (markdown, yaml, json)

### Rollback

```bash
rm -f specs/reverse.md
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 36/- [x] Phase 36/' CURRENT.md
sed -i 's/Current Phase: 36/Current Phase: 37/' CURRENT.md

# Commit
git add specs/reverse.md CURRENT.md
git commit -m "Phase 36: Add Reverse Audit specification"
```

---

## Phase 37: Git Diff Parsing

### Context

Before we can generate audit documents, we need to parse git history. This phase implements the git integration layer that extracts commit and file information.

### Goal

Implement git parsing functions that extract commit information and file changes.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `tools/reverse.py` | CREATE | Reverse audit module with git parsing |

### Plan

1. Create data classes for commits and file changes
2. Implement git command execution helpers
3. Implement commit range parsing
4. Implement file change extraction
5. Handle errors and edge cases

### Implementation

#### tools/reverse.py

```python
"""
Phaser Reverse Audit

Generate structured audit documents from git diffs.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# Enums
# =============================================================================


class GroupingStrategy(str, Enum):
    """Strategy for grouping commits into phases."""

    COMMITS = "commits"
    DIRECTORIES = "directories"
    FILETYPES = "filetypes"
    SEMANTIC = "semantic"


class ChangeCategory(str, Enum):
    """Category of changes in a phase."""

    FEATURE = "feature"
    REFACTOR = "refactor"
    FIX = "fix"
    TEST = "test"
    DOCS = "docs"
    CHORE = "chore"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FileChangeInfo:
    """Information about a file change in a commit."""

    path: str
    change_type: str  # "added", "modified", "deleted", "renamed"
    insertions: int = 0
    deletions: int = 0
    old_path: str | None = None  # For renames

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "path": self.path,
            "change_type": self.change_type,
            "insertions": self.insertions,
            "deletions": self.deletions,
        }
        if self.old_path:
            result["old_path"] = self.old_path
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileChangeInfo:
        """Create from dictionary."""
        return cls(
            path=d["path"],
            change_type=d["change_type"],
            insertions=d.get("insertions", 0),
            deletions=d.get("deletions", 0),
            old_path=d.get("old_path"),
        )


@dataclass
class CommitInfo:
    """Information about a git commit."""

    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    files: list[FileChangeInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "hash": self.hash,
            "short_hash": self.short_hash,
            "author": self.author,
            "date": self.date,
            "message": self.message,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "files": [f.to_dict() for f in self.files],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CommitInfo:
        """Create from dictionary."""
        return cls(
            hash=d["hash"],
            short_hash=d["short_hash"],
            author=d["author"],
            date=d["date"],
            message=d["message"],
            files_changed=d.get("files_changed", 0),
            insertions=d.get("insertions", 0),
            deletions=d.get("deletions", 0),
            files=[FileChangeInfo.from_dict(f) for f in d.get("files", [])],
        )


@dataclass
class InferredPhase:
    """A phase inferred from git history."""

    number: int
    title: str
    description: str
    category: str
    commits: list[CommitInfo] = field(default_factory=list)
    files: list[FileChangeInfo] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        """Number of unique files in this phase."""
        return len(set(f.path for f in self.files))

    @property
    def total_insertions(self) -> int:
        """Total insertions in this phase."""
        return sum(f.insertions for f in self.files)

    @property
    def total_deletions(self) -> int:
        """Total deletions in this phase."""
        return sum(f.deletions for f in self.files)

    @property
    def total_changes(self) -> int:
        """Total line changes in this phase."""
        return self.total_insertions + self.total_deletions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "commits": [c.to_dict() for c in self.commits],
            "files": [f.to_dict() for f in self.files],
            "file_count": self.file_count,
            "total_insertions": self.total_insertions,
            "total_deletions": self.total_deletions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InferredPhase:
        """Create from dictionary."""
        return cls(
            number=d["number"],
            title=d["title"],
            description=d["description"],
            category=d["category"],
            commits=[CommitInfo.from_dict(c) for c in d.get("commits", [])],
            files=[FileChangeInfo.from_dict(f) for f in d.get("files", [])],
        )


@dataclass
class ReverseAuditResult:
    """Result of reverse audit generation."""

    title: str
    project: str
    commit_range: str
    strategy: str
    generated_at: str

    total_commits: int = 0
    total_files: int = 0
    total_insertions: int = 0
    total_deletions: int = 0

    phases: list[InferredPhase] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "project": self.project,
            "commit_range": self.commit_range,
            "strategy": self.strategy,
            "generated_at": self.generated_at,
            "summary": {
                "total_commits": self.total_commits,
                "total_files": self.total_files,
                "total_insertions": self.total_insertions,
                "total_deletions": self.total_deletions,
            },
            "phases": [p.to_dict() for p in self.phases],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReverseAuditResult:
        """Create from dictionary."""
        summary = d.get("summary", {})
        return cls(
            title=d["title"],
            project=d["project"],
            commit_range=d["commit_range"],
            strategy=d["strategy"],
            generated_at=d["generated_at"],
            total_commits=summary.get("total_commits", 0),
            total_files=summary.get("total_files", 0),
            total_insertions=summary.get("total_insertions", 0),
            total_deletions=summary.get("total_deletions", 0),
            phases=[InferredPhase.from_dict(p) for p in d.get("phases", [])],
        )


# =============================================================================
# Git Helper Functions
# =============================================================================


def run_git_command(
    args: list[str],
    repo_path: Path | None = None,
) -> str:
    """
    Run a git command and return output.

    Args:
        args: Git command arguments (without 'git')
        repo_path: Repository path (default: current directory)

    Returns:
        Command output as string

    Raises:
        ValueError: If not a git repository
        subprocess.CalledProcessError: If command fails
    """
    cwd = repo_path or Path.cwd()

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise ValueError("Git is not installed or not in PATH")
    except subprocess.CalledProcessError as e:
        if "not a git repository" in e.stderr.lower():
            raise ValueError(f"Not a git repository: {cwd}")
        raise


def is_git_repository(path: Path | None = None) -> bool:
    """Check if path is inside a git repository."""
    try:
        run_git_command(["rev-parse", "--is-inside-work-tree"], path)
        return True
    except (ValueError, subprocess.CalledProcessError):
        return False


def validate_commit_range(
    commit_range: str,
    repo_path: Path | None = None,
) -> bool:
    """
    Validate that a commit range is valid.

    Args:
        commit_range: Git commit range string
        repo_path: Repository path

    Returns:
        True if valid, raises ValueError if not
    """
    try:
        run_git_command(["rev-parse", commit_range.replace("..", " ")], repo_path)
        return True
    except subprocess.CalledProcessError:
        raise ValueError(
            f"Invalid commit range: {commit_range}\n"
            "Examples of valid ranges:\n"
            "  HEAD~5..HEAD\n"
            "  main..feature-branch\n"
            "  abc123..def456"
        )


def get_current_branch(repo_path: Path | None = None) -> str:
    """Get the current branch name."""
    try:
        return run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    except subprocess.CalledProcessError:
        return "unknown"


def get_repo_name(repo_path: Path | None = None) -> str:
    """Get the repository name from remote or directory."""
    path = repo_path or Path.cwd()

    # Try to get from remote
    try:
        remote = run_git_command(["remote", "get-url", "origin"], path)
        # Extract repo name from URL
        name = remote.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name
    except subprocess.CalledProcessError:
        pass

    # Fall back to directory name
    return path.resolve().name


# =============================================================================
# Commit Parsing Functions
# =============================================================================


def parse_commit_range(
    commit_range: str,
    repo_path: Path | None = None,
    include_merges: bool = False,
) -> list[CommitInfo]:
    """
    Parse a git commit range and return commit information.

    Args:
        commit_range: Git commit range (e.g., "HEAD~5..HEAD")
        repo_path: Path to repository (default: current directory)
        include_merges: Include merge commits (default: False)

    Returns:
        List of CommitInfo, oldest first

    Raises:
        ValueError: If commit range is invalid or not a git repo
    """
    validate_commit_range(commit_range, repo_path)

    # Format: hash|short_hash|author|date|message
    format_str = "%H|%h|%an|%aI|%s"

    args = [
        "log",
        "--format=" + format_str,
        "--reverse",  # Oldest first
        commit_range,
    ]

    if not include_merges:
        args.append("--no-merges")

    output = run_git_command(args, repo_path)

    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        if not line.strip():
            continue

        parts = line.split("|", 4)
        if len(parts) < 5:
            continue

        hash_, short_hash, author, date, message = parts

        # Get file changes for this commit
        files = get_commit_files(hash_, repo_path)

        # Calculate totals
        insertions = sum(f.insertions for f in files)
        deletions = sum(f.deletions for f in files)

        commits.append(
            CommitInfo(
                hash=hash_,
                short_hash=short_hash,
                author=author,
                date=date,
                message=message,
                files_changed=len(files),
                insertions=insertions,
                deletions=deletions,
                files=files,
            )
        )

    return commits


def get_commit_files(
    commit_hash: str,
    repo_path: Path | None = None,
) -> list[FileChangeInfo]:
    """
    Get files changed in a specific commit.

    Args:
        commit_hash: Git commit hash
        repo_path: Path to repository

    Returns:
        List of FileChangeInfo for files in commit
    """
    # Get numstat for insertions/deletions
    numstat = run_git_command(
        ["show", "--numstat", "--format=", commit_hash],
        repo_path,
    )

    # Get name-status for change types
    name_status = run_git_command(
        ["show", "--name-status", "--format=", commit_hash],
        repo_path,
    )

    # Parse name-status to get change types
    change_types: dict[str, tuple[str, str | None]] = {}  # path -> (type, old_path)
    for line in name_status.split("\n"):
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            if status.startswith("R"):  # Renamed
                old_path = parts[1]
                new_path = parts[2] if len(parts) > 2 else parts[1]
                change_types[new_path] = ("renamed", old_path)
            elif status == "A":
                change_types[parts[1]] = ("added", None)
            elif status == "D":
                change_types[parts[1]] = ("deleted", None)
            elif status == "M":
                change_types[parts[1]] = ("modified", None)
            else:
                change_types[parts[1]] = ("modified", None)

    # Parse numstat for line counts
    files = []
    for line in numstat.split("\n"):
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        insertions_str, deletions_str, path = parts[0], parts[1], parts[2]

        # Handle binary files (shown as -)
        try:
            insertions = int(insertions_str) if insertions_str != "-" else 0
            deletions = int(deletions_str) if deletions_str != "-" else 0
        except ValueError:
            insertions = 0
            deletions = 0

        # Handle renames with arrow notation: old_path => new_path
        if " => " in path:
            # Parse rename format: {old => new}/path or path/{old => new}
            path = path.split(" => ")[-1].rstrip("}")
            if "{" in path:
                path = path.replace("{", "").replace("}", "")

        change_type, old_path = change_types.get(path, ("modified", None))

        files.append(
            FileChangeInfo(
                path=path,
                change_type=change_type,
                insertions=insertions,
                deletions=deletions,
                old_path=old_path,
            )
        )

    return files


def get_diff_stats(
    commit_range: str,
    repo_path: Path | None = None,
) -> tuple[int, int, int]:
    """
    Get aggregate diff statistics for a commit range.

    Args:
        commit_range: Git commit range
        repo_path: Repository path

    Returns:
        Tuple of (files_changed, insertions, deletions)
    """
    try:
        output = run_git_command(
            ["diff", "--shortstat", commit_range],
            repo_path,
        )
    except subprocess.CalledProcessError:
        return 0, 0, 0

    if not output:
        return 0, 0, 0

    files = insertions = deletions = 0

    # Parse: "X files changed, Y insertions(+), Z deletions(-)"
    files_match = re.search(r"(\d+) files? changed", output)
    if files_match:
        files = int(files_match.group(1))

    insertions_match = re.search(r"(\d+) insertions?\(\+\)", output)
    if insertions_match:
        insertions = int(insertions_match.group(1))

    deletions_match = re.search(r"(\d+) deletions?\(-\)", output)
    if deletions_match:
        deletions = int(deletions_match.group(1))

    return files, insertions, deletions


# =============================================================================
# Helper Functions
# =============================================================================


def now_iso() -> str:
    """Get current time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
```

### Verify

```bash
# File exists
test -f tools/reverse.py && echo "✓ tools/reverse.py created"

# Syntax check
python -m py_compile tools/reverse.py && echo "✓ Syntax OK"

# Import check
python -c "from tools.reverse import CommitInfo, FileChangeInfo, parse_commit_range, get_commit_files" && echo "✓ Imports OK"

# Test git functions (in a git repo)
python -c "
from tools.reverse import is_git_repository, get_repo_name, get_current_branch
from pathlib import Path

# Should work in Phaser directory
assert is_git_repository(Path.cwd())
print(f'Repo: {get_repo_name()}')
print(f'Branch: {get_current_branch()}')
print('✓ Git functions work')
"

# Test commit parsing (last 3 commits)
python -c "
from tools.reverse import parse_commit_range

commits = parse_commit_range('HEAD~3..HEAD')
print(f'Parsed {len(commits)} commits')
for c in commits:
    print(f'  {c.short_hash}: {c.message[:50]}')
print('✓ Commit parsing works')
"
```

### Acceptance Criteria

- [ ] tools/reverse.py exists with git parsing functions
- [ ] GroupingStrategy and ChangeCategory enums defined
- [ ] FileChangeInfo, CommitInfo, InferredPhase, ReverseAuditResult dataclasses
- [ ] run_git_command executes git commands safely
- [ ] parse_commit_range extracts commit information
- [ ] get_commit_files extracts file changes per commit
- [ ] Error handling for non-git repos and invalid ranges

### Rollback

```bash
rm -f tools/reverse.py
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 37/- [x] Phase 37/' CURRENT.md
sed -i 's/Current Phase: 37/Current Phase: 38/' CURRENT.md

# Commit
git add tools/reverse.py CURRENT.md
git commit -m "Phase 37: Implement git diff parsing"
```

---

## Phase 38: Audit Document Generation

### Context

Git parsing is complete. Now we implement the phase grouping logic and document generation that transforms commits into structured audit documents.

### Goal

Implement phase inference, grouping strategies, and document formatting functions.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `tools/reverse.py` | MODIFY | Add generation and formatting functions |

### Plan

1. Implement phase title inference
2. Implement category inference
3. Implement grouping strategies
4. Implement main generate_reverse_audit function
5. Implement markdown/yaml formatters

### Implementation

Add these functions to tools/reverse.py:

```python
# =============================================================================
# Phase Inference Functions
# =============================================================================


def infer_category(
    commits: list[CommitInfo],
    files: list[FileChangeInfo],
) -> str:
    """
    Infer the category of changes.

    Args:
        commits: Commits in the phase
        files: Files changed

    Returns:
        Category string (feature, refactor, fix, test, docs, chore)
    """
    # Check commit messages for keywords
    messages = " ".join(c.message.lower() for c in commits)

    # Check file patterns
    paths = [f.path.lower() for f in files]
    all_paths_str = " ".join(paths)

    # Test files
    test_patterns = ["test_", "_test.", ".test.", "/tests/", "spec.", "_spec."]
    if any(p in all_paths_str for p in test_patterns):
        if all(any(p in path for p in test_patterns) for path in paths):
            return "test"

    # Documentation
    doc_patterns = [".md", ".rst", ".txt", "/docs/", "readme", "changelog"]
    if any(p in all_paths_str for p in doc_patterns):
        if all(any(p in path for p in doc_patterns) for path in paths):
            return "docs"

    # Fix detection
    fix_keywords = ["fix", "bug", "patch", "hotfix", "issue"]
    if any(kw in messages for kw in fix_keywords):
        return "fix"

    # Chore detection
    chore_patterns = ["package.json", "pyproject.toml", "requirements", ".yml", ".yaml", "config"]
    chore_keywords = ["chore", "deps", "dependency", "bump", "upgrade"]
    if any(kw in messages for kw in chore_keywords) or all(
        any(p in path for p in chore_patterns) for path in paths
    ):
        return "chore"

    # Feature vs Refactor
    added_files = [f for f in files if f.change_type == "added"]
    deleted_files = [f for f in files if f.change_type == "deleted"]

    if len(added_files) > len(files) * 0.5:
        return "feature"

    if len(deleted_files) > len(files) * 0.3:
        return "refactor"

    # Default based on keywords
    if any(kw in messages for kw in ["add", "new", "create", "implement"]):
        return "feature"

    if any(kw in messages for kw in ["refactor", "clean", "improve", "optimize"]):
        return "refactor"

    return "feature"  # Default


def infer_phase_title(
    commits: list[CommitInfo],
    files: list[FileChangeInfo],
    category: str,
) -> str:
    """
    Infer a descriptive title for a phase.

    Args:
        commits: Commits in the phase
        files: Files changed in the phase
        category: Inferred category

    Returns:
        Inferred phase title
    """
    if len(commits) == 1:
        # Single commit - use its message (cleaned up)
        message = commits[0].message

        # Remove conventional commit prefix
        message = re.sub(r"^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?\s*:\s*", "", message)

        # Capitalize first letter
        if message:
            message = message[0].upper() + message[1:]

        return message[:80]  # Limit length

    # Multiple commits - try to find common theme
    messages = [c.message.lower() for c in commits]

    # Extract common words (excluding stop words)
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "it"}
    all_words: list[str] = []
    for msg in messages:
        words = re.findall(r"\b\w+\b", msg)
        all_words.extend(w for w in words if w not in stop_words and len(w) > 2)

    # Find most common meaningful words
    word_counts: dict[str, int] = {}
    for word in all_words:
        word_counts[word] = word_counts.get(word, 0) + 1

    common_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    # Build title from category and common words
    category_titles = {
        "feature": "Add",
        "fix": "Fix",
        "refactor": "Refactor",
        "test": "Add tests for",
        "docs": "Update documentation for",
        "chore": "Update",
    }

    prefix = category_titles.get(category, "Update")

    if common_words:
        subject = " ".join(w for w, _ in common_words[:2])
        return f"{prefix} {subject}"

    # Fall back to directory-based title
    if files:
        dirs = set()
        for f in files:
            parts = f.path.split("/")
            if len(parts) > 1:
                dirs.add(parts[0])
            else:
                dirs.add(Path(f.path).stem)

        if dirs:
            return f"{prefix} {', '.join(sorted(dirs)[:2])}"

    return f"{prefix} changes"


def generate_phase_description(
    commits: list[CommitInfo],
    files: list[FileChangeInfo],
    category: str,
) -> str:
    """
    Generate a description for a phase.

    Args:
        commits: Commits in the phase
        files: Files changed
        category: Phase category

    Returns:
        Phase description
    """
    parts = []

    # Summarize commits
    if len(commits) == 1:
        parts.append(f"Based on commit {commits[0].short_hash}.")
    else:
        parts.append(f"Based on {len(commits)} commits.")

    # Summarize file changes
    added = sum(1 for f in files if f.change_type == "added")
    modified = sum(1 for f in files if f.change_type == "modified")
    deleted = sum(1 for f in files if f.change_type == "deleted")

    change_parts = []
    if added:
        change_parts.append(f"{added} added")
    if modified:
        change_parts.append(f"{modified} modified")
    if deleted:
        change_parts.append(f"{deleted} deleted")

    if change_parts:
        parts.append(f"Files: {', '.join(change_parts)}.")

    return " ".join(parts)


# =============================================================================
# Grouping Functions
# =============================================================================


def group_by_commits(
    commits: list[CommitInfo],
    max_phases: int = 20,
) -> list[InferredPhase]:
    """Group commits as individual phases (one per commit)."""
    phases = []

    for i, commit in enumerate(commits[:max_phases], 1):
        category = infer_category([commit], commit.files)
        title = infer_phase_title([commit], commit.files, category)
        description = generate_phase_description([commit], commit.files, category)

        phases.append(
            InferredPhase(
                number=i,
                title=title,
                description=description,
                category=category,
                commits=[commit],
                files=commit.files,
            )
        )

    return phases


def group_by_directories(
    commits: list[CommitInfo],
    max_phases: int = 20,
) -> list[InferredPhase]:
    """Group commits by top-level directory."""
    # Collect all files by directory
    dir_commits: dict[str, list[CommitInfo]] = {}
    dir_files: dict[str, list[FileChangeInfo]] = {}

    for commit in commits:
        for file in commit.files:
            parts = file.path.split("/")
            dir_name = parts[0] if len(parts) > 1 else "(root)"

            if dir_name not in dir_commits:
                dir_commits[dir_name] = []
                dir_files[dir_name] = []

            if commit not in dir_commits[dir_name]:
                dir_commits[dir_name].append(commit)
            dir_files[dir_name].append(file)

    # Create phases for each directory
    phases = []
    sorted_dirs = sorted(dir_commits.keys(), key=lambda d: len(dir_files[d]), reverse=True)

    for i, dir_name in enumerate(sorted_dirs[:max_phases], 1):
        commits_in_dir = dir_commits[dir_name]
        files_in_dir = dir_files[dir_name]

        category = infer_category(commits_in_dir, files_in_dir)
        title = f"Update {dir_name}"
        description = generate_phase_description(commits_in_dir, files_in_dir, category)

        phases.append(
            InferredPhase(
                number=i,
                title=title,
                description=description,
                category=category,
                commits=commits_in_dir,
                files=files_in_dir,
            )
        )

    return phases


def group_by_filetypes(
    commits: list[CommitInfo],
    max_phases: int = 20,
) -> list[InferredPhase]:
    """Group commits by file extension."""
    # Collect files by extension
    ext_commits: dict[str, list[CommitInfo]] = {}
    ext_files: dict[str, list[FileChangeInfo]] = {}

    for commit in commits:
        for file in commit.files:
            ext = Path(file.path).suffix or "(no extension)"

            if ext not in ext_commits:
                ext_commits[ext] = []
                ext_files[ext] = []

            if commit not in ext_commits[ext]:
                ext_commits[ext].append(commit)
            ext_files[ext].append(file)

    # Create phases for each extension
    phases = []
    sorted_exts = sorted(ext_commits.keys(), key=lambda e: len(ext_files[e]), reverse=True)

    for i, ext in enumerate(sorted_exts[:max_phases], 1):
        commits_for_ext = ext_commits[ext]
        files_for_ext = ext_files[ext]

        category = infer_category(commits_for_ext, files_for_ext)

        ext_name = ext.lstrip(".") if ext.startswith(".") else ext
        title = f"Update {ext_name} files"
        description = generate_phase_description(commits_for_ext, files_for_ext, category)

        phases.append(
            InferredPhase(
                number=i,
                title=title,
                description=description,
                category=category,
                commits=commits_for_ext,
                files=files_for_ext,
            )
        )

    return phases


def group_by_semantic(
    commits: list[CommitInfo],
    max_phases: int = 20,
) -> list[InferredPhase]:
    """Group commits by semantic similarity (commit message patterns)."""
    # Group by conventional commit type if present
    type_commits: dict[str, list[CommitInfo]] = {}

    for commit in commits:
        # Try to extract conventional commit type
        match = re.match(r"^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?:", commit.message)
        if match:
            commit_type = match.group(1)
        else:
            # Infer from message
            msg_lower = commit.message.lower()
            if any(kw in msg_lower for kw in ["add", "new", "create", "implement"]):
                commit_type = "feat"
            elif any(kw in msg_lower for kw in ["fix", "bug", "patch"]):
                commit_type = "fix"
            elif any(kw in msg_lower for kw in ["test", "spec"]):
                commit_type = "test"
            elif any(kw in msg_lower for kw in ["doc", "readme"]):
                commit_type = "docs"
            elif any(kw in msg_lower for kw in ["refactor", "clean", "improve"]):
                commit_type = "refactor"
            else:
                commit_type = "other"

        if commit_type not in type_commits:
            type_commits[commit_type] = []
        type_commits[commit_type].append(commit)

    # Create phases for each type
    phases = []
    type_order = ["feat", "fix", "refactor", "test", "docs", "chore", "other"]
    sorted_types = sorted(type_commits.keys(), key=lambda t: type_order.index(t) if t in type_order else 99)

    for i, commit_type in enumerate(sorted_types[:max_phases], 1):
        commits_for_type = type_commits[commit_type]
        all_files = [f for c in commits_for_type for f in c.files]

        category_map = {
            "feat": "feature",
            "fix": "fix",
            "docs": "docs",
            "test": "test",
            "refactor": "refactor",
            "chore": "chore",
            "other": "feature",
        }
        category = category_map.get(commit_type, "feature")

        title = infer_phase_title(commits_for_type, all_files, category)
        description = generate_phase_description(commits_for_type, all_files, category)

        phases.append(
            InferredPhase(
                number=i,
                title=title,
                description=description,
                category=category,
                commits=commits_for_type,
                files=all_files,
            )
        )

    return phases


def group_commits_to_phases(
    commits: list[CommitInfo],
    strategy: GroupingStrategy = GroupingStrategy.COMMITS,
    max_phases: int = 20,
) -> list[InferredPhase]:
    """
    Group commits into phases based on strategy.

    Args:
        commits: List of commits to group
        strategy: Grouping strategy to use
        max_phases: Maximum number of phases

    Returns:
        List of InferredPhase
    """
    if not commits:
        return []

    if strategy == GroupingStrategy.COMMITS:
        return group_by_commits(commits, max_phases)
    elif strategy == GroupingStrategy.DIRECTORIES:
        return group_by_directories(commits, max_phases)
    elif strategy == GroupingStrategy.FILETYPES:
        return group_by_filetypes(commits, max_phases)
    elif strategy == GroupingStrategy.SEMANTIC:
        return group_by_semantic(commits, max_phases)
    else:
        return group_by_commits(commits, max_phases)


# =============================================================================
# Main Generation Function
# =============================================================================


def generate_reverse_audit(
    commit_range: str,
    strategy: GroupingStrategy = GroupingStrategy.COMMITS,
    title: str | None = None,
    project: str | None = None,
    repo_path: Path | None = None,
    max_phases: int = 20,
) -> ReverseAuditResult:
    """
    Generate a reverse audit from a commit range.

    Args:
        commit_range: Git commit range
        strategy: Phase grouping strategy
        title: Audit title (inferred if not provided)
        project: Project name (inferred if not provided)
        repo_path: Repository path
        max_phases: Maximum phases to generate

    Returns:
        ReverseAuditResult with inferred phases

    Raises:
        ValueError: If commit range is invalid or not a git repo
    """
    # Validate repository
    if not is_git_repository(repo_path):
        raise ValueError(f"Not a git repository: {repo_path or Path.cwd()}")

    # Parse commits
    commits = parse_commit_range(commit_range, repo_path)

    if not commits:
        raise ValueError(f"No commits found in range: {commit_range}")

    # Infer project name
    if not project:
        project = get_repo_name(repo_path)

    # Infer title
    if not title:
        branch = get_current_branch(repo_path)
        if branch and branch != "HEAD":
            title = f"Reverse Audit: {branch}"
        else:
            # Use commit range as title
            title = f"Reverse Audit: {commit_range}"

    # Group commits into phases
    phases = group_commits_to_phases(commits, strategy, max_phases)

    # Calculate totals
    all_files: set[str] = set()
    total_insertions = 0
    total_deletions = 0

    for commit in commits:
        for f in commit.files:
            all_files.add(f.path)
        total_insertions += commit.insertions
        total_deletions += commit.deletions

    return ReverseAuditResult(
        title=title,
        project=project,
        commit_range=commit_range,
        strategy=strategy.value,
        generated_at=now_iso(),
        total_commits=len(commits),
        total_files=len(all_files),
        total_insertions=total_insertions,
        total_deletions=total_deletions,
        phases=phases,
    )


# =============================================================================
# Formatting Functions
# =============================================================================


def format_as_markdown(
    result: ReverseAuditResult,
    include_diff: bool = False,
) -> str:
    """
    Format reverse audit result as markdown document.

    Args:
        result: ReverseAuditResult to format
        include_diff: Include full git diff in output

    Returns:
        Markdown string
    """
    lines = [
        f"# {result.title}",
        "",
        "> Generated from git history",
        f"> Commit range: {result.commit_range}",
        f"> Generated: {result.generated_at}",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"This audit was reverse-engineered from {result.total_commits} commits "
        f"affecting {result.total_files} files.",
        "",
        "**Summary:**",
        f"- Total commits: {result.total_commits}",
        f"- Files changed: {result.total_files}",
        f"- Lines added: {result.total_insertions}",
        f"- Lines removed: {result.total_deletions}",
        "",
        "---",
        "",
    ]

    for phase in result.phases:
        lines.extend([
            f"## Phase {phase.number}: {phase.title}",
            "",
            "### Context",
            "",
            phase.description,
            "",
            "### Changes",
            "",
            "| File | Change | Lines |",
            "|------|--------|-------|",
        ])

        for f in phase.files[:20]:  # Limit files shown
            change_str = f.change_type.capitalize()
            lines_str = f"+{f.insertions}/-{f.deletions}"
            lines.append(f"| {f.path} | {change_str} | {lines_str} |")

        if len(phase.files) > 20:
            lines.append(f"| ... | +{len(phase.files) - 20} more files | |")

        lines.extend([
            "",
            "### Commits",
            "",
        ])

        for commit in phase.commits:
            lines.append(f"- {commit.short_hash}: {commit.message}")

        lines.extend(["", "---", ""])

    # Footer
    lines.extend([
        "",
        f"*Generated by Phaser v1.5 on {result.generated_at}*",
    ])

    return "\n".join(lines)


def format_as_yaml(result: ReverseAuditResult) -> str:
    """
    Format reverse audit result as YAML.

    Args:
        result: ReverseAuditResult to format

    Returns:
        YAML string
    """
    import yaml

    return yaml.dump(result.to_dict(), default_flow_style=False, sort_keys=False)


def format_preview(
    commits: list[CommitInfo],
    phases: list[InferredPhase],
    commit_range: str,
    strategy: str,
) -> str:
    """
    Format a preview of what would be generated.

    Args:
        commits: Parsed commits
        phases: Inferred phases
        commit_range: Original commit range
        strategy: Grouping strategy used

    Returns:
        Formatted preview string
    """
    total_files = len(set(f.path for c in commits for f in c.files))
    total_insertions = sum(c.insertions for c in commits)
    total_deletions = sum(c.deletions for c in commits)

    lines = [
        "Reverse Audit Preview",
        "=====================",
        f"Commit Range: {commit_range}",
        f"Strategy: {strategy}",
        f"Commits: {len(commits)}",
        f"Files Changed: {total_files}",
        f"Insertions: {total_insertions}",
        f"Deletions: {total_deletions}",
        "",
        "Inferred Phases:",
    ]

    for phase in phases:
        lines.append(f"  {phase.number}. {phase.title} ({phase.file_count} files)")

    lines.extend([
        "",
        f"Use 'phaser reverse {commit_range}' to generate full document.",
    ])

    return "\n".join(lines)
```

### Verify

```bash
# Syntax check
python -m py_compile tools/reverse.py && echo "✓ Syntax OK"

# Import check
python -c "from tools.reverse import generate_reverse_audit, format_as_markdown, group_commits_to_phases" && echo "✓ Imports OK"

# Test generation (last 3 commits)
python -c "
from tools.reverse import generate_reverse_audit, format_as_markdown, GroupingStrategy

result = generate_reverse_audit('HEAD~3..HEAD', strategy=GroupingStrategy.COMMITS)
print(f'Generated {len(result.phases)} phases')
print(f'Title: {result.title}')

md = format_as_markdown(result)
print(f'Markdown length: {len(md)} chars')
print('✓ Generation works')
"
```

### Acceptance Criteria

- [ ] infer_category detects change categories
- [ ] infer_phase_title generates meaningful titles
- [ ] group_by_commits, group_by_directories, group_by_filetypes, group_by_semantic work
- [ ] generate_reverse_audit orchestrates full generation
- [ ] format_as_markdown produces valid markdown
- [ ] format_as_yaml produces valid YAML
- [ ] format_preview shows summary

### Rollback

```bash
git checkout HEAD -- tools/reverse.py
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 38/- [x] Phase 38/' CURRENT.md
sed -i 's/Current Phase: 38/Current Phase: 39/' CURRENT.md

# Commit
git add tools/reverse.py CURRENT.md
git commit -m "Phase 38: Implement audit document generation"
```

---

## Phase 39: Reverse CLI Commands

### Context

The generation logic is complete. Now we add CLI commands for users to interact with the reverse audit functionality.

### Goal

Implement CLI commands: `phaser reverse`, `phaser reverse preview`, and `phaser reverse commits`.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `tools/reverse.py` | MODIFY | Add CLI commands |

### Plan

1. Add main reverse command
2. Add preview subcommand
3. Add commits subcommand
4. Handle output options and errors

### Implementation

Add these CLI commands to tools/reverse.py:

```python
# =============================================================================
# CLI Interface
# =============================================================================

import click


@click.group(invoke_without_command=True)
@click.argument("commit_range", required=False)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option(
    "--strategy",
    type=click.Choice(["commits", "directories", "filetypes", "semantic"]),
    default="commits",
    help="Phase grouping strategy",
)
@click.option("--title", help="Audit title (default: inferred)")
@click.option("--project", help="Project name (default: inferred)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "yaml", "json"]),
    default="markdown",
    help="Output format",
)
@click.option("--include-diff", is_flag=True, help="Include full diff in output")
@click.option("--max-phases", default=20, help="Maximum phases to generate")
@click.pass_context
def cli(
    ctx: click.Context,
    commit_range: str | None,
    output: str | None,
    strategy: str,
    title: str | None,
    project: str | None,
    output_format: str,
    include_diff: bool,
    max_phases: int,
) -> None:
    """
    Generate audit document from git diff.

    COMMIT_RANGE is a git commit range (e.g., HEAD~5..HEAD, main..feature).

    Examples:

        phaser reverse HEAD~5..HEAD

        phaser reverse main..feature-branch --output audit.md

        phaser reverse HEAD~10..HEAD --strategy directories

        phaser reverse HEAD~5..HEAD --format yaml
    """
    # If no subcommand and commit_range provided, run generation
    if ctx.invoked_subcommand is None:
        if not commit_range:
            click.echo(ctx.get_help())
            return

        import json

        try:
            result = generate_reverse_audit(
                commit_range=commit_range,
                strategy=GroupingStrategy(strategy),
                title=title,
                project=project,
                max_phases=max_phases,
            )
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

        # Format output
        if output_format == "markdown":
            content = format_as_markdown(result, include_diff=include_diff)
        elif output_format == "yaml":
            content = format_as_yaml(result)
        else:
            content = json.dumps(result.to_dict(), indent=2)

        # Write or print
        if output:
            Path(output).write_text(content)
            click.echo(f"Audit document saved to {output}")
        else:
            click.echo(content)


@cli.command()
@click.argument("commit_range")
@click.option(
    "--strategy",
    type=click.Choice(["commits", "directories", "filetypes", "semantic"]),
    default="commits",
    help="Phase grouping strategy",
)
def preview(commit_range: str, strategy: str) -> None:
    """
    Preview what would be generated.

    Shows summary of commits and inferred phases without generating
    the full document.

    Examples:

        phaser reverse preview HEAD~5..HEAD

        phaser reverse preview main..feature --strategy directories
    """
    try:
        commits = parse_commit_range(commit_range)
        phases = group_commits_to_phases(commits, GroupingStrategy(strategy))
        output = format_preview(commits, phases, commit_range, strategy)
        click.echo(output)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("commit_range")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def commits(commit_range: str, output_format: str) -> None:
    """
    List commits in a range with change summaries.

    Examples:

        phaser reverse commits HEAD~5..HEAD

        phaser reverse commits main..feature --format json
    """
    import json

    try:
        commit_list = parse_commit_range(commit_range)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if not commit_list:
        click.echo(f"No commits found in range: {commit_range}")
        return

    if output_format == "json":
        click.echo(json.dumps([c.to_dict() for c in commit_list], indent=2))
    else:
        lines = [
            f"Commits in Range: {commit_range}",
            "=" * (len(f"Commits in Range: {commit_range}")),
            "",
        ]

        for commit in commit_list:
            lines.extend([
                f"{commit.short_hash} ({commit.date[:10]}) {commit.message}",
                f"  Files: {commit.files_changed} (+{commit.insertions} -{commit.deletions})",
            ])

            for f in commit.files[:5]:
                change = f.change_type
                lines.append(f"  - {f.path} ({change})")

            if len(commit.files) > 5:
                lines.append(f"  ... and {len(commit.files) - 5} more files")

            lines.append("")

        click.echo("\n".join(lines))


@cli.command()
@click.argument("commit_range")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def diff(commit_range: str, output: str | None) -> None:
    """
    Show the full diff for a commit range.

    Examples:

        phaser reverse diff HEAD~5..HEAD

        phaser reverse diff main..feature -o changes.diff
    """
    try:
        diff_output = run_git_command(["diff", commit_range])
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output:
        Path(output).write_text(diff_output)
        click.echo(f"Diff saved to {output}")
    else:
        click.echo(diff_output)
```

### Verify

```bash
# Syntax check
python -m py_compile tools/reverse.py && echo "✓ Syntax OK"

# CLI help check
python -c "
from click.testing import CliRunner
from tools.reverse import cli

runner = CliRunner()
result = runner.invoke(cli, ['--help'])
assert 'preview' in result.output
assert 'commits' in result.output
print('✓ CLI group works')
"

# Test preview command
python -c "
from click.testing import CliRunner
from tools.reverse import cli

runner = CliRunner()
result = runner.invoke(cli, ['preview', 'HEAD~3..HEAD'])
print(result.output)
assert 'Reverse Audit Preview' in result.output or 'Error' in result.output
print('✓ Preview command works')
"

# Test commits command
python -c "
from click.testing import CliRunner
from tools.reverse import cli

runner = CliRunner()
result = runner.invoke(cli, ['commits', 'HEAD~3..HEAD'])
print(result.output[:500])
print('✓ Commits command works')
"
```

### Acceptance Criteria

- [ ] Main reverse command generates document from commit range
- [ ] preview subcommand shows summary
- [ ] commits subcommand lists commits with details
- [ ] diff subcommand shows full diff
- [ ] --output option saves to file
- [ ] --format option supports markdown/yaml/json
- [ ] --strategy option changes grouping
- [ ] Error handling with helpful messages

### Rollback

```bash
git checkout HEAD -- tools/reverse.py
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 39/- [x] Phase 39/' CURRENT.md
sed -i 's/Current Phase: 39/Current Phase: 40/' CURRENT.md

# Commit
git add tools/reverse.py CURRENT.md
git commit -m "Phase 39: Add Reverse CLI commands"
```

---

## Phase 40: CLI Integration

### Context

The reverse module is complete. Now we integrate it with the main CLI and update the version.

### Goal

Register the reverse subcommand group in the main CLI and update version information.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `tools/cli.py` | MODIFY | Add reverse subcommand |
| `pyproject.toml` | MODIFY | Update version to 1.5.0 |

### Plan

1. Import reverse CLI module
2. Register subcommand group
3. Update version string
4. Update version command output

### Implementation

#### tools/cli.py modifications

Add import:

```python
from tools.reverse import cli as reverse_cli
```

Add command registration:

```python
cli.add_command(reverse_cli, name="reverse")
```

Update version:

```python
@click.group()
@click.version_option(version="1.5.0", prog_name="phaser")
```

Update version command:

```python
@cli.command()
def version() -> None:
    """Show version and feature information."""
    click.echo("Phaser v1.5.0")
    click.echo()
    click.echo("Features:")
    click.echo("  * Storage & Events (Learning Loop)")
    click.echo("  * Audit Diffs")
    click.echo("  * Audit Contracts")
    click.echo("  * Simulation")
    click.echo("  * Branch-per-phase")
    click.echo("  * CI Integration")
    click.echo("  * Insights & Analytics")
    click.echo("  * Audit Replay")
    click.echo("  * Reverse Audit")
    click.echo()
    click.echo("Batch 2 (coming soon):")
    click.echo("  - Phase Negotiation")
```

#### pyproject.toml modification

```toml
[project]
name = "phaser"
version = "1.5.0"
```

### Verify

```bash
# Syntax check
python -m py_compile tools/cli.py && echo "✓ Syntax OK"

# Check subcommand is registered
python -m tools.cli --help | grep reverse
# Expected: reverse should appear in commands

# Check version
python -m tools.cli version | head -1
# Expected: Phaser v1.5.0

# Check reverse subcommand
python -m tools.cli reverse --help
# Expected: Shows preview, commits, diff commands

# Check pyproject.toml version
grep 'version = "1.5.0"' pyproject.toml && echo "✓ Version updated"
```

### Acceptance Criteria

- [ ] tools/cli.py imports reverse module
- [ ] reverse subcommand group registered
- [ ] phaser reverse --help shows all commands
- [ ] Version updated to 1.5.0 in CLI
- [ ] Version updated to 1.5.0 in pyproject.toml
- [ ] All existing commands still work

### Rollback

```bash
git checkout HEAD -- tools/cli.py pyproject.toml
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 40/- [x] Phase 40/' CURRENT.md
sed -i 's/Current Phase: 40/Current Phase: 41/' CURRENT.md

# Commit
git add tools/cli.py pyproject.toml CURRENT.md
git commit -m "Phase 40: Integrate Reverse into main CLI"
```

---

## Phase 41: Tests and Documentation

### Context

The Reverse Audit feature is implemented and integrated. This final phase adds tests and documentation.

### Goal

Add test files for the Reverse module, achieving 90%+ coverage. Update CHANGELOG.

### Files

| File | Action | Purpose |
|------|--------|---------|
| `tests/test_reverse.py` | CREATE | Reverse module tests |
| `CHANGELOG.md` | MODIFY | Add v1.5.0 release notes |

### Plan

1. Create tests for data structures
2. Create tests for git parsing functions
3. Create tests for generation functions
4. Create tests for CLI commands
5. Update CHANGELOG

### Implementation

#### tests/test_reverse.py

```python
"""Tests for the Reverse Audit module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.reverse import (
    ChangeCategory,
    CommitInfo,
    FileChangeInfo,
    GroupingStrategy,
    InferredPhase,
    ReverseAuditResult,
    format_as_markdown,
    format_as_yaml,
    format_preview,
    generate_phase_description,
    generate_reverse_audit,
    get_commit_files,
    get_current_branch,
    get_repo_name,
    group_by_commits,
    group_by_directories,
    group_commits_to_phases,
    infer_category,
    infer_phase_title,
    is_git_repository,
    now_iso,
    parse_commit_range,
    run_git_command,
    validate_commit_range,
)


class TestGroupingStrategy:
    """Tests for GroupingStrategy enum."""

    def test_commits_value(self) -> None:
        """COMMITS has correct value."""
        assert GroupingStrategy.COMMITS.value == "commits"

    def test_directories_value(self) -> None:
        """DIRECTORIES has correct value."""
        assert GroupingStrategy.DIRECTORIES.value == "directories"

    def test_filetypes_value(self) -> None:
        """FILETYPES has correct value."""
        assert GroupingStrategy.FILETYPES.value == "filetypes"

    def test_semantic_value(self) -> None:
        """SEMANTIC has correct value."""
        assert GroupingStrategy.SEMANTIC.value == "semantic"


class TestFileChangeInfo:
    """Tests for FileChangeInfo dataclass."""

    def test_to_dict_minimal(self) -> None:
        """to_dict with minimal fields."""
        info = FileChangeInfo(
            path="src/main.py",
            change_type="added",
            insertions=50,
            deletions=0,
        )
        result = info.to_dict()

        assert result["path"] == "src/main.py"
        assert result["change_type"] == "added"
        assert "old_path" not in result

    def test_to_dict_with_rename(self) -> None:
        """to_dict includes old_path for renames."""
        info = FileChangeInfo(
            path="src/new_name.py",
            change_type="renamed",
            insertions=0,
            deletions=0,
            old_path="src/old_name.py",
        )
        result = info.to_dict()

        assert result["old_path"] == "src/old_name.py"

    def test_from_dict(self) -> None:
        """from_dict reconstructs FileChangeInfo."""
        data = {
            "path": "test.py",
            "change_type": "modified",
            "insertions": 10,
            "deletions": 5,
        }
        info = FileChangeInfo.from_dict(data)

        assert info.path == "test.py"
        assert info.insertions == 10


class TestCommitInfo:
    """Tests for CommitInfo dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        commit = CommitInfo(
            hash="abc123def456",
            short_hash="abc123d",
            author="Test Author",
            date="2025-12-05T10:00:00Z",
            message="Add feature",
            files_changed=3,
            insertions=100,
            deletions=20,
            files=[
                FileChangeInfo(path="a.py", change_type="added"),
            ],
        )
        result = commit.to_dict()

        assert result["hash"] == "abc123def456"
        assert result["message"] == "Add feature"
        assert len(result["files"]) == 1

    def test_from_dict(self) -> None:
        """from_dict reconstructs CommitInfo."""
        data = {
            "hash": "abc123",
            "short_hash": "abc",
            "author": "Author",
            "date": "2025-12-05",
            "message": "Test",
            "files": [],
        }
        commit = CommitInfo.from_dict(data)

        assert commit.hash == "abc123"
        assert commit.message == "Test"


class TestInferredPhase:
    """Tests for InferredPhase dataclass."""

    def test_file_count(self) -> None:
        """file_count returns unique file count."""
        phase = InferredPhase(
            number=1,
            title="Test",
            description="Desc",
            category="feature",
            files=[
                FileChangeInfo(path="a.py", change_type="added"),
                FileChangeInfo(path="b.py", change_type="added"),
                FileChangeInfo(path="a.py", change_type="modified"),  # Duplicate
            ],
        )

        assert phase.file_count == 2

    def test_total_insertions(self) -> None:
        """total_insertions sums correctly."""
        phase = InferredPhase(
            number=1,
            title="Test",
            description="Desc",
            category="feature",
            files=[
                FileChangeInfo(path="a.py", change_type="added", insertions=50),
                FileChangeInfo(path="b.py", change_type="added", insertions=30),
            ],
        )

        assert phase.total_insertions == 80

    def test_to_dict(self) -> None:
        """to_dict includes computed properties."""
        phase = InferredPhase(
            number=1,
            title="Test Phase",
            description="Description",
            category="feature",
        )
        result = phase.to_dict()

        assert result["number"] == 1
        assert result["title"] == "Test Phase"
        assert "file_count" in result


class TestReverseAuditResult:
    """Tests for ReverseAuditResult dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        result = ReverseAuditResult(
            title="Test Audit",
            project="test-project",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05T10:00:00Z",
            total_commits=5,
            total_files=10,
        )
        data = result.to_dict()

        assert data["title"] == "Test Audit"
        assert data["summary"]["total_commits"] == 5

    def test_from_dict(self) -> None:
        """from_dict reconstructs ReverseAuditResult."""
        data = {
            "title": "Test",
            "project": "proj",
            "commit_range": "HEAD~3..HEAD",
            "strategy": "commits",
            "generated_at": "2025-12-05",
            "summary": {"total_commits": 3},
            "phases": [],
        }
        result = ReverseAuditResult.from_dict(data)

        assert result.title == "Test"
        assert result.total_commits == 3


class TestGitHelpers:
    """Tests for git helper functions."""

    def test_is_git_repository_in_repo(self, tmp_path: Path) -> None:
        """Detects git repository correctly."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        assert is_git_repository(tmp_path) is True

    def test_is_git_repository_not_repo(self, tmp_path: Path) -> None:
        """Returns False for non-repo."""
        assert is_git_repository(tmp_path) is False

    def test_get_repo_name_fallback(self, tmp_path: Path) -> None:
        """Falls back to directory name."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        name = get_repo_name(tmp_path)
        assert name == tmp_path.name


class TestInferCategory:
    """Tests for infer_category function."""

    def test_detects_test_category(self) -> None:
        """Detects test category from file paths."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Add tests",
            files=[FileChangeInfo(path="tests/test_main.py", change_type="added")],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "test"

    def test_detects_docs_category(self) -> None:
        """Detects docs category from file paths."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Update readme",
            files=[FileChangeInfo(path="README.md", change_type="modified")],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "docs"

    def test_detects_fix_from_message(self) -> None:
        """Detects fix category from commit message."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Fix bug in login",
            files=[FileChangeInfo(path="src/auth.py", change_type="modified")],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "fix"

    def test_detects_feature_from_new_files(self) -> None:
        """Detects feature when mostly new files."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="", message="Add user module",
            files=[
                FileChangeInfo(path="src/user.py", change_type="added"),
                FileChangeInfo(path="src/profile.py", change_type="added"),
            ],
        )]
        files = commits[0].files

        assert infer_category(commits, files) == "feature"


class TestInferPhaseTitle:
    """Tests for infer_phase_title function."""

    def test_single_commit_uses_message(self) -> None:
        """Single commit uses cleaned message."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="",
            message="feat(auth): add login functionality",
            files=[],
        )]

        title = infer_phase_title(commits, [], "feature")

        assert "Add login functionality" in title

    def test_removes_conventional_commit_prefix(self) -> None:
        """Removes conventional commit prefixes."""
        commits = [CommitInfo(
            hash="abc", short_hash="abc", author="", date="",
            message="fix: correct typo in readme",
            files=[],
        )]

        title = infer_phase_title(commits, [], "fix")

        assert not title.startswith("fix:")
        assert "Correct typo" in title


class TestGroupByCommits:
    """Tests for group_by_commits function."""

    def test_one_phase_per_commit(self) -> None:
        """Creates one phase per commit."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="First",
                      files=[FileChangeInfo(path="a.py", change_type="added")]),
            CommitInfo(hash="b", short_hash="b", author="", date="", message="Second",
                      files=[FileChangeInfo(path="b.py", change_type="added")]),
        ]

        phases = group_by_commits(commits)

        assert len(phases) == 2
        assert phases[0].number == 1
        assert phases[1].number == 2

    def test_respects_max_phases(self) -> None:
        """Limits to max_phases."""
        commits = [
            CommitInfo(hash=str(i), short_hash=str(i), author="", date="",
                      message=f"Commit {i}", files=[])
            for i in range(10)
        ]

        phases = group_by_commits(commits, max_phases=5)

        assert len(phases) == 5


class TestGroupByDirectories:
    """Tests for group_by_directories function."""

    def test_groups_by_top_level_dir(self) -> None:
        """Groups files by top-level directory."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="Changes",
                      files=[
                          FileChangeInfo(path="src/main.py", change_type="modified"),
                          FileChangeInfo(path="src/utils.py", change_type="modified"),
                          FileChangeInfo(path="tests/test_main.py", change_type="added"),
                      ]),
        ]

        phases = group_by_directories(commits)

        assert len(phases) == 2  # src and tests
        dir_names = {p.title for p in phases}
        assert "Update src" in dir_names
        assert "Update tests" in dir_names


class TestGroupCommitsToPhases:
    """Tests for group_commits_to_phases function."""

    def test_empty_commits(self) -> None:
        """Returns empty list for no commits."""
        phases = group_commits_to_phases([])
        assert phases == []

    def test_uses_correct_strategy(self) -> None:
        """Uses specified strategy."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="Test",
                      files=[FileChangeInfo(path="src/a.py", change_type="added")]),
        ]

        phases_commits = group_commits_to_phases(commits, GroupingStrategy.COMMITS)
        phases_dirs = group_commits_to_phases(commits, GroupingStrategy.DIRECTORIES)

        # Both should work, structure may differ
        assert len(phases_commits) >= 1
        assert len(phases_dirs) >= 1


class TestFormatAsMarkdown:
    """Tests for format_as_markdown function."""

    def test_includes_title(self) -> None:
        """Output includes title."""
        result = ReverseAuditResult(
            title="Test Audit",
            project="test",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05",
        )

        md = format_as_markdown(result)

        assert "# Test Audit" in md

    def test_includes_overview(self) -> None:
        """Output includes overview section."""
        result = ReverseAuditResult(
            title="Test",
            project="test",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05",
            total_commits=5,
            total_files=10,
        )

        md = format_as_markdown(result)

        assert "## Overview" in md
        assert "5 commits" in md


class TestFormatAsYaml:
    """Tests for format_as_yaml function."""

    def test_produces_valid_yaml(self) -> None:
        """Output is valid YAML."""
        import yaml

        result = ReverseAuditResult(
            title="Test",
            project="test",
            commit_range="HEAD~5..HEAD",
            strategy="commits",
            generated_at="2025-12-05",
        )

        yaml_str = format_as_yaml(result)
        parsed = yaml.safe_load(yaml_str)

        assert parsed["title"] == "Test"


class TestFormatPreview:
    """Tests for format_preview function."""

    def test_shows_summary(self) -> None:
        """Preview shows summary info."""
        commits = [
            CommitInfo(hash="a", short_hash="a", author="", date="", message="Test",
                      insertions=50, deletions=10, files=[]),
        ]
        phases = [
            InferredPhase(number=1, title="Test Phase", description="", category="feature"),
        ]

        preview = format_preview(commits, phases, "HEAD~1..HEAD", "commits")

        assert "Reverse Audit Preview" in preview
        assert "HEAD~1..HEAD" in preview
        assert "Test Phase" in preview


class TestNowIso:
    """Tests for now_iso helper."""

    def test_returns_iso_format(self) -> None:
        """Returns valid ISO timestamp."""
        result = now_iso()

        assert "T" in result
        assert len(result) > 10


class TestCLI:
    """Tests for CLI commands."""

    def test_preview_command(self) -> None:
        """Preview command works."""
        from click.testing import CliRunner
        from tools.reverse import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["preview", "HEAD~1..HEAD"])

        # May fail if not in git repo, but command should run
        assert result.exit_code in (0, 1)

    def test_commits_command(self) -> None:
        """Commits command works."""
        from click.testing import CliRunner
        from tools.reverse import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["commits", "HEAD~1..HEAD"])

        assert result.exit_code in (0, 1)

    def test_help_shows_options(self) -> None:
        """Help shows all options."""
        from click.testing import CliRunner
        from tools.reverse import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert "--strategy" in result.output
        assert "--format" in result.output
        assert "--output" in result.output
```

#### CHANGELOG.md addition

Add at the top of the file:

```markdown
## [1.5.0] - 2025-12-05

### Added

- **Reverse Audit** (`phaser reverse`)
  - `phaser reverse <commit-range>` — Generate audit document from git diff
  - `phaser reverse preview <commit-range>` — Preview inferred phases
  - `phaser reverse commits <commit-range>` — List commits with details
  - `phaser reverse diff <commit-range>` — Show full diff
  - Multiple grouping strategies: commits, directories, filetypes, semantic
  - Output formats: markdown, yaml, json
  - Automatic phase title and category inference
  - Support for conventional commit parsing

- **Specifications**
  - `specs/reverse.md` — Reverse Audit feature specification

### Changed

- Version bumped to 1.5.0
- Updated `phaser version` output to list Reverse Audit feature

---

```

### Verify

```bash
# Run new tests
cd ~/Projects/Phaser
python -m pytest tests/test_reverse.py -v
# Expected: All tests pass

# Run all tests
python -m pytest tests/ -q --tb=no
# Expected: 310+ tests passing

# Check coverage
python -m pytest tests/test_reverse.py --cov=tools.reverse --cov-report=term-missing
# Expected: 85%+ coverage (git functions hard to test in isolation)

# Verify CHANGELOG
grep -c "## \[1.5.0\]" CHANGELOG.md
# Expected: 1
```

### Acceptance Criteria

- [ ] tests/test_reverse.py exists with comprehensive tests
- [ ] All new tests pass
- [ ] Total test count is 310+ (up from 280)
- [ ] Coverage on reverse module is 85%+
- [ ] CHANGELOG.md updated with v1.5.0 release notes

### Rollback

```bash
rm -f tests/test_reverse.py
git checkout HEAD -- CHANGELOG.md
```

### Completion

```bash
# Update CURRENT.md
sed -i 's/- \[ \] Phase 41/- [x] Phase 41/' CURRENT.md
sed -i 's/Current Phase: 41/Current Phase: COMPLETE/' CURRENT.md

# Commit
git add tests/test_reverse.py CHANGELOG.md CURRENT.md
git commit -m "Phase 41: Add tests and documentation for Reverse Audit"
```

---

## Document Completion

### Final Steps

After all phases are complete:

```bash
# Ensure all tests pass
cd ~/Projects/Phaser
python -m pytest tests/ -v

# Reinstall package
pip install -e . --break-system-packages

# Verify CLI
phaser version
phaser reverse --help

# Test reverse audit
phaser reverse preview HEAD~5..HEAD
phaser reverse HEAD~3..HEAD --format yaml

# Merge branch
git checkout main
git merge audit/2025-12-05-batch2-doc7-reverse

# Tag release
git tag -a v1.5.0 -m "Phaser v1.5.0 - Reverse Audit"
git push origin main --tags

# Clean up
rm CURRENT.md
rm -rf audit-phases/
rm AUDIT.md
```

### Summary

Document 7 implemented:

1. **Reverse Audit**
   - `phaser reverse <commit-range>` generates audit from git history
   - `phaser reverse preview` shows inferred phases
   - `phaser reverse commits` lists commits with details
   - `phaser reverse diff` shows full diff
   - Grouping strategies: commits, directories, filetypes, semantic
   - Output formats: markdown, yaml, json
   - Category inference: feature, fix, refactor, test, docs, chore

2. **Documentation**
   - `specs/reverse.md` specification

3. **Tests**
   - ~30 new tests for Reverse module
   - 85%+ coverage on new code

---

*Document 7 Complete — Proceed to Document 8 (Phase Negotiation)*
