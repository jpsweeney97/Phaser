"""Parse inline ignore directives from source files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tools.enforce import Violation


@dataclass
class IgnoreDirective:
    """An ignore directive found in source code."""

    rule_ids: list[str]  # Empty list means ignore-all
    line_number: int
    scope: str  # "line" or "next-line"


# Comment patterns by file extension
COMMENT_PATTERNS: dict[tuple[str, ...], str] = {
    # Hash comments
    (".py", ".rb", ".sh", ".yaml", ".yml", ".toml"): r"#\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)",
    # Double-slash comments
    (
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".swift",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".java",
        ".kt",
        ".cs",
    ): r"//\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)",
    # HTML comments
    (".html", ".xml", ".vue", ".svelte"): r"<!--\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)\s*-->",
    # CSS comments
    (".css", ".scss", ".less"): r"/\*\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)\s*\*/",
}


def get_comment_pattern(file_path: str) -> Optional[re.Pattern]:
    """Get the comment pattern for a file based on its extension."""
    ext = Path(file_path).suffix.lower()
    for extensions, pattern in COMMENT_PATTERNS.items():
        if ext in extensions:
            return re.compile(pattern)
    return None


def parse_ignores(content: str, file_path: str) -> list[IgnoreDirective]:
    """Parse all ignore directives from file content."""
    pattern = get_comment_pattern(file_path)
    if not pattern:
        return []

    directives: list[IgnoreDirective] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if not match:
            continue

        directive_type = match.group(1)
        rule_ids_str = match.group(2).strip()

        # Parse rule IDs
        if directive_type == "ignore-all" or not rule_ids_str:
            rule_ids: list[str] = []  # Empty means all
        else:
            rule_ids = [r.strip() for r in rule_ids_str.split(",") if r.strip()]

        # Determine scope
        if directive_type == "ignore-next-line":
            scope = "next-line"
        else:
            scope = "line"

        directives.append(
            IgnoreDirective(
                rule_ids=rule_ids,
                line_number=line_num,
                scope=scope,
            )
        )

    return directives


def should_ignore(
    violation_rule_id: str,
    violation_line: Optional[int],
    directives: list[IgnoreDirective],
) -> bool:
    """Check if a violation should be ignored based on directives."""
    if violation_line is None:
        return False

    for directive in directives:
        # Check if this directive applies to this line
        if directive.scope == "line" and directive.line_number != violation_line:
            continue
        if directive.scope == "next-line" and directive.line_number != violation_line - 1:
            continue

        # Check if rule matches
        if not directive.rule_ids:  # ignore-all
            return True
        if violation_rule_id in directive.rule_ids:
            return True

    return False


def filter_violations(
    violations: list[Violation], file_path: str, content: str
) -> tuple[list[Violation], list[Violation]]:
    """Filter violations based on ignore directives.

    Returns:
        (remaining_violations, ignored_violations)
    """
    directives = parse_ignores(content, file_path)
    if not directives:
        return violations, []

    remaining: list[Violation] = []
    ignored: list[Violation] = []

    for v in violations:
        if should_ignore(v.rule_id, v.line_number, directives):
            ignored.append(v)
        else:
            remaining.append(v)

    return remaining, ignored
