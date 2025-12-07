"""Tests for ignore directive parsing."""

import pytest

from tools.ignore_parser import (
    IgnoreDirective,
    get_comment_pattern,
    parse_ignores,
    should_ignore,
)


class TestGetCommentPattern:
    def test_python(self) -> None:
        pattern = get_comment_pattern("test.py")
        assert pattern is not None

    def test_javascript(self) -> None:
        pattern = get_comment_pattern("test.js")
        assert pattern is not None

    def test_swift(self) -> None:
        pattern = get_comment_pattern("test.swift")
        assert pattern is not None

    def test_unknown_extension(self) -> None:
        pattern = get_comment_pattern("test.xyz")
        assert pattern is None


class TestParseIgnores:
    def test_python_ignore_same_line(self) -> None:
        content = "x = 1  # phaser:ignore no-magic-numbers"
        directives = parse_ignores(content, "test.py")
        assert len(directives) == 1
        assert directives[0].rule_ids == ["no-magic-numbers"]
        assert directives[0].scope == "line"
        assert directives[0].line_number == 1

    def test_python_ignore_next_line(self) -> None:
        content = "# phaser:ignore-next-line no-print\nprint('hello')"
        directives = parse_ignores(content, "test.py")
        assert len(directives) == 1
        assert directives[0].scope == "next-line"
        assert directives[0].line_number == 1

    def test_python_ignore_all(self) -> None:
        content = "x = 1  # phaser:ignore-all"
        directives = parse_ignores(content, "test.py")
        assert len(directives) == 1
        assert directives[0].rule_ids == []

    def test_multiple_rules(self) -> None:
        content = "x = 1  # phaser:ignore rule-a, rule-b"
        directives = parse_ignores(content, "test.py")
        assert directives[0].rule_ids == ["rule-a", "rule-b"]

    def test_javascript_comment(self) -> None:
        content = "const x = 1; // phaser:ignore no-const"
        directives = parse_ignores(content, "test.js")
        assert len(directives) == 1
        assert directives[0].rule_ids == ["no-const"]

    def test_swift_comment(self) -> None:
        content = "let x = optional! // phaser:ignore no-force-unwrap"
        directives = parse_ignores(content, "test.swift")
        assert len(directives) == 1
        assert directives[0].rule_ids == ["no-force-unwrap"]

    def test_html_comment(self) -> None:
        content = '<div><!-- phaser:ignore no-inline-style --></div>'
        directives = parse_ignores(content, "test.html")
        assert len(directives) == 1
        assert directives[0].rule_ids == ["no-inline-style"]


class TestShouldIgnore:
    def test_same_line_match(self) -> None:
        directive = IgnoreDirective(["rule-a"], line_number=5, scope="line")
        assert should_ignore("rule-a", 5, [directive])

    def test_same_line_no_match(self) -> None:
        directive = IgnoreDirective(["rule-a"], line_number=5, scope="line")
        assert not should_ignore("rule-a", 6, [directive])

    def test_next_line_match(self) -> None:
        directive = IgnoreDirective(["rule-a"], line_number=4, scope="next-line")
        assert should_ignore("rule-a", 5, [directive])

    def test_ignore_all(self) -> None:
        directive = IgnoreDirective([], line_number=5, scope="line")
        assert should_ignore("any-rule", 5, [directive])

    def test_wrong_rule(self) -> None:
        directive = IgnoreDirective(["rule-a"], line_number=5, scope="line")
        assert not should_ignore("rule-b", 5, [directive])

    def test_none_line_number(self) -> None:
        directive = IgnoreDirective(["rule-a"], line_number=5, scope="line")
        assert not should_ignore("rule-a", None, [directive])
