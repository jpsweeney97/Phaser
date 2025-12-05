# Branching Specification

> Phaser v1.2 — Git branch per phase for reviewable audits

---

## Purpose

Branch-per-phase mode creates a git branch for each audit phase:

- **Make changes reviewable** — Each phase becomes a PR-able unit
- **Enable selective merging** — Accept some phases, reject others
- **Support team workflows** — Get approval before merging
- **Provide rollback points** — Each branch is a natural checkpoint

---

## Branch Naming

```
audit/{audit-slug}/phase-{NN}-{phase-slug}
```

### Examples

```
audit/security-hardening/phase-01-input-validation
audit/security-hardening/phase-02-auth-headers
audit/security-hardening/phase-03-rate-limiting
audit/code-cleanup/phase-01-remove-dead-code
audit/code-cleanup/phase-02-extract-utils
```

### Rules

- `audit-slug`: From audit metadata, lowercase with hyphens
- `NN`: Two-digit phase number (01, 02, ..., 99)
- `phase-slug`: From phase filename, lowercase with hyphens
- Total branch name should not exceed 100 characters

---

## Branch Structure

Branches form a linear chain where each builds on the previous:

```
main ─────────────────────────────────────────────────────────►
  │
  └──► audit/security/phase-01-validation
         │
         └──► audit/security/phase-02-headers
                │
                └──► audit/security/phase-03-rate-limit
```

### Why Linear?

- Each phase may depend on previous phases
- Merge conflicts are minimized
- Review order matches execution order
- Squash merge combines all changes cleanly

---

## Data Schemas

### BranchInfo

Information about a single phase branch:

```python
@dataclass
class BranchInfo:
    phase_num: int           # Phase number (1, 2, 3, ...)
    phase_slug: str          # Slug from phase filename
    branch_name: str         # Full branch name
    created_at: str          # ISO timestamp when created
    commit_sha: str | None   # SHA of phase commit (if committed)
    merged: bool             # Whether branch has been merged

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "phase_num": self.phase_num,
            "phase_slug": self.phase_slug,
            "branch_name": self.branch_name,
            "created_at": self.created_at,
            "commit_sha": self.commit_sha,
            "merged": self.merged,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BranchInfo":
        """Deserialize from persistence."""
        return cls(
            phase_num=d["phase_num"],
            phase_slug=d["phase_slug"],
            branch_name=d["branch_name"],
            created_at=d["created_at"],
            commit_sha=d.get("commit_sha"),
            merged=d.get("merged", False),
        )
```

### BranchContext

Tracks the state of branch mode for an audit:

```python
@dataclass
class BranchContext:
    audit_id: str              # Audit identifier
    audit_slug: str            # Audit slug for branch naming
    root: Path                 # Project root directory
    base_branch: str           # Base branch (usually "main")
    current_phase: int | None  # Currently active phase (if any)
    branches: list[BranchInfo] # All phase branches
    active: bool               # Whether branch mode is active

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "audit_id": self.audit_id,
            "audit_slug": self.audit_slug,
            "root": str(self.root),
            "base_branch": self.base_branch,
            "current_phase": self.current_phase,
            "branches": [b.to_dict() for b in self.branches],
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BranchContext":
        """Deserialize from persistence."""
        return cls(
            audit_id=d["audit_id"],
            audit_slug=d["audit_slug"],
            root=Path(d["root"]),
            base_branch=d["base_branch"],
            current_phase=d.get("current_phase"),
            branches=[BranchInfo.from_dict(b) for b in d.get("branches", [])],
            active=d.get("active", True),
        )

    def get_branch(self, phase_num: int) -> BranchInfo | None:
        """Get branch info for a phase number."""
        for b in self.branches:
            if b.phase_num == phase_num:
                return b
        return None

    def current_branch_name(self) -> str | None:
        """Get name of current phase branch."""
        if self.current_phase is None:
            return None
        branch = self.get_branch(self.current_phase)
        return branch.branch_name if branch else None

    def last_branch_name(self) -> str | None:
        """Get name of most recent phase branch."""
        if not self.branches:
            return None
        return self.branches[-1].branch_name
```

### MergeStrategy

Enum for merge strategies:

```python
class MergeStrategy(str, Enum):
    SQUASH = "squash"   # Squash all commits into one
    REBASE = "rebase"   # Rebase and fast-forward
    MERGE = "merge"     # Create merge commits
```

---

## Operations

### begin_branch_mode

Initialize branch mode for an audit:

```python
def begin_branch_mode(
    root: Path,
    audit_id: str,
    audit_slug: str,
    base_branch: str | None = None,
    storage: PhaserStorage | None = None,
) -> BranchContext:
    """
    Initialize branch mode for an audit.

    Args:
        root: Project root directory
        audit_id: Audit identifier
        audit_slug: Audit slug for branch naming
        base_branch: Base branch (default: current branch)
        storage: Optional storage instance

    Returns:
        BranchContext for tracking branches

    Steps:
    1. Verify git repository
    2. Record base branch (default: current)
    3. Verify no uncommitted changes
    4. Initialize empty branch list
    5. Save context to storage
    """
```

### create_phase_branch

Create a branch for a phase:

```python
def create_phase_branch(
    ctx: BranchContext,
    phase_num: int,
    phase_slug: str,
) -> BranchInfo:
    """
    Create branch for a phase.

    Args:
        ctx: Active branch context
        phase_num: Phase number
        phase_slug: Phase slug for naming

    Returns:
        BranchInfo for the new branch

    Steps:
    1. Generate branch name: audit/{slug}/phase-{NN}-{phase_slug}
    2. Determine base: previous phase branch or base_branch
    3. Create branch from base
    4. Checkout the new branch
    5. Record in context
    6. Return BranchInfo
    """
```

### commit_phase

Commit changes for a phase:

```python
def commit_phase(
    ctx: BranchContext,
    phase_num: int,
    message: str | None = None,
) -> str | None:
    """
    Commit current changes for phase.

    Args:
        ctx: Active branch context
        phase_num: Phase number
        message: Commit message (default: "Phase {N}: {slug}")

    Returns:
        Commit SHA or None if nothing to commit

    Steps:
    1. Stage all changes (git add -A)
    2. Create commit with message
    3. Update BranchInfo with commit SHA
    4. Return SHA
    """
```

### merge_all_branches

Merge all phase branches into target:

```python
def merge_all_branches(
    ctx: BranchContext,
    target: str | None = None,
    strategy: MergeStrategy = MergeStrategy.SQUASH,
) -> bool:
    """
    Merge all phase branches into target.

    Args:
        ctx: Active branch context
        target: Target branch (default: base_branch)
        strategy: Merge strategy to use

    Returns:
        True if merge succeeded

    Steps:
    1. Checkout target branch
    2. For each phase branch (in order):
       - Apply merge strategy
       - Update BranchInfo.merged = True
    3. Return success status
    """
```

### cleanup_branches

Delete phase branches:

```python
def cleanup_branches(
    ctx: BranchContext,
    merged_only: bool = True,
) -> int:
    """
    Delete phase branches.

    Args:
        ctx: Active branch context
        merged_only: If True, only delete merged branches

    Returns:
        Number of branches deleted

    Steps:
    1. For each branch:
       - If merged_only and not merged: skip
       - Delete branch (git branch -d or -D)
    2. Return count
    """
```

### get_branch_context

Load existing branch context:

```python
def get_branch_context(
    storage: PhaserStorage,
    audit_id: str,
) -> BranchContext | None:
    """
    Load branch context from storage.

    Returns:
        BranchContext if exists, None otherwise
    """
```

### end_branch_mode

End branch mode:

```python
def end_branch_mode(ctx: BranchContext) -> None:
    """
    End branch mode, cleanup context.

    Steps:
    1. Mark context inactive
    2. Remove context from storage
    """
```

---

## Merge Strategies

| Strategy | Command                          | Result                    | When to Use           |
| -------- | -------------------------------- | ------------------------- | --------------------- |
| squash   | `git merge --squash`             | One commit with all changes | Clean history        |
| rebase   | `git rebase` + `git merge --ff`  | Preserve individual commits | Audit trail          |
| merge    | `git merge --no-ff`              | Merge commit per phase    | Full history         |

### Squash (Default)

```bash
git checkout main
git merge --squash audit/security/phase-03-rate-limit
git commit -m "Complete security-hardening audit"
```

Result: Single commit on main with all audit changes.

### Rebase

```bash
git checkout audit/security/phase-03-rate-limit
git rebase main
git checkout main
git merge --ff-only audit/security/phase-03-rate-limit
```

Result: Phase commits appear on main in order.

### Merge

```bash
git checkout main
git merge --no-ff audit/security/phase-01-validation -m "Phase 1: Input validation"
git merge --no-ff audit/security/phase-02-headers -m "Phase 2: Auth headers"
git merge --no-ff audit/security/phase-03-rate-limit -m "Phase 3: Rate limiting"
```

Result: Merge commit for each phase, preserving branch structure.

---

## CLI Interface

```bash
# Enable branch mode for current audit
phaser branch enable
phaser branch enable --base main
python -m tools.branches enable

# Show branch status
phaser branch status
python -m tools.branches status

# Merge all phase branches
phaser branch merge --strategy squash
phaser branch merge --strategy rebase --target main
python -m tools.branches merge --strategy squash

# Cleanup (delete merged branches)
phaser branch cleanup
phaser branch cleanup --all  # Delete all, even unmerged
python -m tools.branches cleanup
```

### CLI Commands

| Command   | Description                              |
| --------- | ---------------------------------------- |
| `enable`  | Enable branch mode for current audit     |
| `status`  | Show branch mode status and branches     |
| `merge`   | Merge all phase branches into target     |
| `cleanup` | Delete phase branches                    |

### CLI Options

**enable:**
- `--base BRANCH`: Base branch (default: current)

**merge:**
- `--strategy [squash|rebase|merge]`: Merge strategy (default: squash)
- `--target BRANCH`: Target branch (default: base)

**cleanup:**
- `--all`: Delete all branches, not just merged

---

## Integration with Audit Workflow

### New Metadata Field

```markdown
| Branch Mode | enabled |
```

Values: `enabled`, `disabled` (default)

### Workflow

1. User enables branch mode: `branch enable`
2. On each "next":
   - Create/checkout phase branch
   - Execute phase
   - Commit changes to branch
3. On audit complete:
   - Offer merge options
   - Merge using chosen strategy
   - Cleanup branches (optional)

### Commands in CONTEXT.md

| User Says        | Action                           |
| ---------------- | -------------------------------- |
| `branch enable`  | Enable branch-per-phase mode     |
| `branch status`  | Show branch mode status          |
| `branch merge`   | Merge all phase branches         |
| `branch cleanup` | Delete phase branches            |

---

## GitHub Integration (Optional)

For teams using GitHub:

### Create PR for Each Phase

```bash
# After completing a phase
gh pr create \
  --base audit/security/phase-01-validation \
  --head audit/security/phase-02-headers \
  --title "Phase 2: Auth headers" \
  --body "Part of security-hardening audit"
```

### Create Combined PR

```bash
# After all phases complete
gh pr create \
  --base main \
  --head audit/security/phase-03-rate-limit \
  --title "Security Hardening Audit" \
  --body "Phases 1-3 of security audit"
```

### Link Phases

PR descriptions can reference previous phases:

```markdown
## Phase 2: Auth Headers

Builds on #123 (Phase 1: Input Validation)

### Changes
- Added auth header validation
- Updated middleware

### Next
Phase 3: Rate Limiting
```

---

## Edge Cases

### Branch Already Exists

**Scenario:** Branch name collision from failed previous run.

**Handling:**
1. Check if branch exists before creating
2. If exists and has commits: warn user, offer to reuse or delete
3. If exists and empty: delete and recreate

### Remote Branches

**Scenario:** Some branches pushed to remote, others local only.

**Handling:**
1. Cleanup operates on local branches only
2. Warn if remote branches exist
3. Offer: `git push origin --delete <branch>` command

### Merge Conflicts

**Scenario:** Conflict during merge.

**Handling:**
1. Stop merge process
2. Report conflicting files
3. Offer options:
   - Resolve manually and continue
   - Abort merge
   - Try different strategy

### Interrupted Checkout

**Scenario:** Checkout fails due to uncommitted changes.

**Handling:**
1. Warn about uncommitted changes
2. Offer options:
   - Stash and continue
   - Commit and continue
   - Abort

### Detached HEAD

**Scenario:** Repository is in detached HEAD state.

**Handling:**
1. Detect detached HEAD
2. Refuse to start branch mode
3. Suggest: `git checkout <branch>` first

---

## Storage

Branch context is persisted for recovery:

```
.phaser/
└── branches.yaml    # Active branch context (if any)
```

Format:
```yaml
audit_id: "security-audit-001"
audit_slug: "security-hardening"
root: "/path/to/project"
base_branch: "main"
current_phase: 2
branches:
  - phase_num: 1
    phase_slug: "input-validation"
    branch_name: "audit/security-hardening/phase-01-input-validation"
    created_at: "2025-12-05T10:00:00Z"
    commit_sha: "abc123"
    merged: false
  - phase_num: 2
    phase_slug: "auth-headers"
    branch_name: "audit/security-hardening/phase-02-auth-headers"
    created_at: "2025-12-05T10:30:00Z"
    commit_sha: null
    merged: false
active: true
```

---

## Safety Guarantees

| Guarantee                    | Mechanism                                |
| ---------------------------- | ---------------------------------------- |
| No data loss                 | Branches preserve all commits            |
| Reversible                   | Branches can be deleted without merging  |
| Original branch preserved    | Base branch unchanged until merge        |
| Recovery from interruption   | Context persisted to storage             |

---

## Git Commands Used

| Command                               | Purpose                          |
| ------------------------------------- | -------------------------------- |
| `git branch --show-current`           | Get current branch               |
| `git branch <name>`                   | Create branch                    |
| `git branch -d <name>`                | Delete merged branch             |
| `git branch -D <name>`                | Force delete branch              |
| `git checkout <branch>`               | Switch branches                  |
| `git checkout -b <branch>`            | Create and checkout              |
| `git add -A`                          | Stage all changes                |
| `git commit -m "..."`                 | Create commit                    |
| `git merge --squash <branch>`         | Squash merge                     |
| `git merge --no-ff <branch>`          | Merge with commit                |
| `git rebase <branch>`                 | Rebase onto branch               |
| `git rev-parse --verify <ref>`        | Check if ref exists              |

---

*Phaser v1.2*
