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

