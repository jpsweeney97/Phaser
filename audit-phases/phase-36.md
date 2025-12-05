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

