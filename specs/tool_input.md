# Specification: Tool Input Parser

**Module:** `tools/tool_input.py`  
**Version:** 1.7.0  
**Status:** Stable  
**Related:** `specs/enforce.md` Section 11.2

---

## 1. Purpose

Parses Claude Code hook input JSON and reconstructs the proposed file state after a Write or Edit operation. This enables contract checking against the file content *before* it's written to disk.

---

## 2. Data Structures

### 2.1 ProposedFile

```python
@dataclass
class ProposedFile:
    path: str      # Absolute file path
    content: str   # Proposed file content
    is_new: bool   # True if file doesn't exist yet
```

### 2.2 ReconstructionResult

```python
@dataclass
class ReconstructionResult:
    files: list[ProposedFile]    # Reconstructed file states
    skipped: bool                # True if reconstruction was skipped
    skip_reason: str | None      # Why reconstruction was skipped
```

---

## 3. Hook Input Schema

### 3.1 Write Tool

```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/Users/dev/project/src/app.py",
    "content": "print('hello')\n"
  }
}
```

### 3.2 Edit Tool

```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/Users/dev/project/src/app.py",
    "old_str": "print('hello')",
    "new_str": "print('world')"
  }
}
```

---

## 4. Reconstruction Logic

### 4.1 Write Operations

1. Extract `file_path` and `content` from `tool_input`
2. Validate content is text (not binary)
3. Return proposed content as-is
4. Set `is_new = True` if file doesn't exist

```python
def reconstruct_write(tool_input: dict) -> ReconstructionResult
```

### 4.2 Edit Operations

1. Extract `file_path`, `old_str`, `new_str` from `tool_input`
2. Read current file content from disk
3. Verify `old_str` exists in current content
4. Apply replacement (first occurrence only)
5. Return modified content

```python
def reconstruct_edit(tool_input: dict) -> ReconstructionResult
```

### 4.3 Dispatcher

```python
def reconstruct(hook_input: dict) -> ReconstructionResult
```

Routes to `reconstruct_write` or `reconstruct_edit` based on `tool_name`.

---

## 5. Skip Conditions

Reconstruction is skipped (returns empty files list) when:

| Condition | Skip Reason |
|-----------|-------------|
| Missing `file_path` | `"Missing file_path"` |
| Binary content in Write | `"Binary content detected"` |
| Binary file in Edit | `"Binary file detected"` |
| File not found (Edit) | `"File not found: {path}"` |
| Read error | `"Cannot read file: {error}"` |
| `old_str` not found | `"old_str not found in file"` |
| Unknown tool name | `"Unknown tool: {name}"` |

When skipped, enforcement allows the operation (no contracts checked).

---

## 6. Binary Detection

```python
def is_valid_text(content: str) -> bool
```

Content is considered binary if:
- Contains null bytes (`\x00`)
- More than 10% non-printable characters (excluding `\n`, `\r`, `\t`)

Binary files bypass contract checking.

---

## 7. Edit Replacement Behavior

The Edit tool replacement uses **first occurrence only**:

```python
proposed = current.replace(old_str, new_str, 1)
```

This matches Claude Code's Edit tool behavior where only the first matching occurrence is replaced.

---

## 8. Usage in Enforcement

```python
from tools.tool_input import reconstruct

# Parse hook input
result = reconstruct(hook_input)

if result.skipped:
    # Allow operation, skip contract checking
    return allow_response(result.skip_reason)

# Check contracts against proposed content
for proposed_file in result.files:
    violations = check_contracts(proposed_file.path, proposed_file.content)
```

---

## 9. Error Handling

All errors during reconstruction result in skipped enforcement (operation allowed):

- File read errors → skip
- Encoding errors → skip  
- Missing fields → skip

This fail-open design ensures enforcement issues don't block legitimate operations.

---

## 10. Testing

Test coverage in `tests/test_tool_input.py`:

- Write reconstruction with new file
- Write reconstruction with existing file
- Edit reconstruction with valid old_str
- Edit reconstruction with missing old_str
- Binary file detection
- Missing file handling
- Malformed input handling

---

*Specification for tools/tool_input.py — Phaser v1.7.0*
