# Specification: Inline Ignore Directives

**Module:** `tools/ignore_parser.py`  
**Version:** 1.7.0  
**Status:** Stable  
**Related:** `specs/enforce.md` Section 2.1

---

## 1. Purpose

Inline ignore directives allow developers to suppress specific contract violations on a per-line basis. This provides escape hatches for intentional violations while maintaining enforcement for the rest of the codebase.

---

## 2. Directive Syntax

### 2.1 General Format

```
<comment-start> phaser:<directive> [rule-ids] <comment-end>
```

**Components:**
- `<comment-start>`: Language-appropriate comment marker
- `phaser:`: Required prefix
- `<directive>`: One of `ignore`, `ignore-next-line`, `ignore-all`
- `[rule-ids]`: Optional comma-separated list of rule IDs
- `<comment-end>`: Required for block comments (HTML, CSS)

### 2.2 Directive Types

| Directive | Scope | Description |
|-----------|-------|-------------|
| `ignore` | Same line | Suppress violations on this line only |
| `ignore-next-line` | Next line | Suppress violations on the following line |
| `ignore-all` | Same line | Suppress ALL violations on this line |

---

## 3. Comment Patterns by Language

### 3.1 Hash Comments (`#`)

**Extensions:** `.py`, `.rb`, `.sh`, `.yaml`, `.yml`, `.toml`

```python
# Python
value = optional!  # phaser:ignore no-force-unwrap
value = other!  # phaser:ignore-next-line no-force-unwrap
another = thing!  # Suppressed by previous line

# Multiple rules
risky_code()  # phaser:ignore rule-a, rule-b

# All rules on this line
dangerous()  # phaser:ignore-all
```

```yaml
# YAML
key: value!  # phaser:ignore no-force-unwrap
```

### 3.2 Double-Slash Comments (`//`)

**Extensions:** `.js`, `.ts`, `.jsx`, `.tsx`, `.swift`, `.go`, `.rs`, `.c`, `.cpp`, `.java`, `.kt`, `.cs`

```swift
// Swift
let value = optional!  // phaser:ignore no-force-unwrap

// Next line
// phaser:ignore-next-line no-force-unwrap
let another = thing!
```

```typescript
// TypeScript
const x = obj!.value;  // phaser:ignore no-force-unwrap
```

```go
// Go
result := dangerousFunc()  // phaser:ignore unsafe-call
```

### 3.3 HTML Comments (`<!-- -->`)

**Extensions:** `.html`, `.xml`, `.vue`, `.svelte`

```html
<!-- HTML -->
<div onclick="alert()">  <!-- phaser:ignore no-inline-handlers -->
  Content
</div>

<!-- Next line -->
<!-- phaser:ignore-next-line no-inline-styles -->
<p style="color: red;">Text</p>
```

```vue
<!-- Vue -->
<template>
  <div v-html="raw">  <!-- phaser:ignore no-v-html -->
  </div>
</template>
```

### 3.4 CSS Block Comments (`/* */`)

**Extensions:** `.css`, `.scss`, `.less`

```css
/* CSS */
.class {
  color: red !important;  /* phaser:ignore no-important */
}

/* Next line */
/* phaser:ignore-next-line no-important */
.another {
  margin: 0 !important;
}
```

---

## 4. Rule ID Specification

### 4.1 Single Rule

```python
code()  # phaser:ignore specific-rule-id
```

### 4.2 Multiple Rules

Comma-separated, whitespace allowed:

```python
code()  # phaser:ignore rule-a, rule-b, rule-c
code()  # phaser:ignore rule-a,rule-b,rule-c
```

### 4.3 All Rules

Empty rule list or explicit `ignore-all`:

```python
code()  # phaser:ignore
code()  # phaser:ignore-all
```

Both suppress ALL contract violations on that line.

---

## 5. Scope Behavior

### 5.1 Same-Line (`ignore`)

```python
# Line 10
dangerous()  # phaser:ignore rule-a
```

Suppresses `rule-a` violations on **line 10 only**.

### 5.2 Next-Line (`ignore-next-line`)

```python
# Line 10
# phaser:ignore-next-line rule-a
# Line 11
dangerous()
```

Suppresses `rule-a` violations on **line 11** (the line after the directive).

### 5.3 Line Number Matching

| Directive Location | Suppresses Line |
|--------------------|-----------------|
| `ignore` on line N | N |
| `ignore-next-line` on line N | N + 1 |

---

## 6. Data Structures

### 6.1 IgnoreDirective

```python
@dataclass
class IgnoreDirective:
    rule_ids: list[str]  # Empty = all rules
    line_number: int     # 1-indexed
    scope: str           # "line" or "next-line"
```

### 6.2 Pattern Registry

```python
COMMENT_PATTERNS: dict[tuple[str, ...], str] = {
    # Hash comments
    (".py", ".rb", ".sh", ".yaml", ".yml", ".toml"): 
        r"#\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)",
    
    # Double-slash comments
    (".js", ".ts", ".jsx", ".tsx", ".swift", ".go", ".rs", 
     ".c", ".cpp", ".java", ".kt", ".cs"): 
        r"//\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)",
    
    # HTML comments
    (".html", ".xml", ".vue", ".svelte"): 
        r"<!--\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)\s*-->",
    
    # CSS comments
    (".css", ".scss", ".less"): 
        r"/\*\s*phaser:(ignore(?:-next-line|-all)?)\s*([\w,\s-]*)\s*\*/",
}
```

---

## 7. API Reference

### 7.1 Parse Ignores

```python
def parse_ignores(content: str, file_path: str) -> list[IgnoreDirective]
```

Extract all ignore directives from file content.

**Parameters:**
- `content`: File content as string
- `file_path`: Path used to determine comment style

**Returns:** List of `IgnoreDirective` objects

### 7.2 Should Ignore

```python
def should_ignore(
    violation_rule_id: str,
    violation_line: int | None,
    directives: list[IgnoreDirective],
) -> bool
```

Check if a specific violation should be suppressed.

**Parameters:**
- `violation_rule_id`: The rule that triggered
- `violation_line`: Line number of violation (1-indexed)
- `directives`: Parsed directives from file

**Returns:** `True` if violation should be ignored

### 7.3 Filter Violations

```python
def filter_violations(
    violations: list[Violation], 
    file_path: str, 
    content: str
) -> tuple[list[Violation], list[Violation]]
```

Partition violations into remaining and ignored.

**Returns:** `(remaining_violations, ignored_violations)`

### 7.4 Get Comment Pattern

```python
def get_comment_pattern(file_path: str) -> re.Pattern | None
```

Get regex pattern for file's comment style.

**Returns:** Compiled regex or `None` for unsupported extensions

---

## 8. Examples

### 8.1 Suppress Specific Rule

```swift
// Contract: no-force-unwrap
// Violation without ignore:
let value = optional!  // ❌ Blocked

// With ignore directive:
let value = optional!  // phaser:ignore no-force-unwrap  // ✓ Allowed
```

### 8.2 Suppress Multiple Rules

```python
# Multiple violations on one line
eval(user_input)  # phaser:ignore no-eval, no-user-input  # ✓ Both suppressed
```

### 8.3 Document Intentional Violations

```python
# Security exception: admin-only endpoint, input pre-validated
# phaser:ignore-next-line no-eval
result = eval(sanitized_expression)  # ✓ Allowed with documented reason
```

### 8.4 Temporary Bypass During Development

```typescript
// TODO: Remove before merge
// phaser:ignore-next-line no-any
const data: any = response;  // ✓ Temporarily allowed
```

---

## 9. Best Practices

### 9.1 Do

- ✓ Use specific rule IDs, not `ignore-all`
- ✓ Add explanatory comment on line above
- ✓ Review ignore directives in code review
- ✓ Track ignore usage via `phaser insights`

### 9.2 Don't

- ✗ Use `ignore-all` as default
- ✗ Add ignores without understanding the rule
- ✗ Leave temporary ignores in production code
- ✗ Ignore security-critical rules without review

---

## 10. Unsupported Files

Files with extensions not in `COMMENT_PATTERNS` have no ignore support. Violations in these files cannot be suppressed inline.

**Workarounds:**
1. Disable the rule at contract level (`enabled: false`)
2. Adjust `file_glob` to exclude specific paths
3. Request extension support via issue

---

## 11. Integration with Enforce

The ignore parser is invoked during contract enforcement:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ enforce.py      │────▶│ ignore_parser.py │────▶│ Filtered        │
│ (violations)    │     │ (parse + filter) │     │ Violations      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

Only remaining violations (after filtering) affect hook decisions.

---

## 12. Testing

Test fixtures in `tests/fixtures/` cover:

- All comment styles
- Single and multiple rule IDs
- `ignore` vs `ignore-next-line` scope
- Edge cases (empty rules, whitespace variations)

See `tests/test_ignore_parser.py` for comprehensive test coverage.

---

*Specification for tools/ignore_parser.py — Phaser v1.7.0*
