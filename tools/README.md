# Phaser Tools

Standalone utilities for Phaser audit automation.

## serialize.py

Generates YAML manifests of a workspace for post-audit validation.

### Usage

```bash
python serialize.py --root /path/to/project --output manifest.yaml
```

### Options

| Option          | Description                                 |
| --------------- | ------------------------------------------- |
| `--root PATH`   | Workspace root (default: current directory) |
| `--output PATH` | Output YAML file (required)                 |
| `--quiet`       | Suppress progress messages                  |

### Features

- Zero external dependencies (stdlib only)
- Gitignore-aware file collection
- Binary file handling (base64 encoded)
- SHA256 checksums for integrity
- 10MB per-file limit, 100MB total limit
- Deterministic output (sorted files)

### Output Format

```yaml
root: /absolute/path/to/project
timestamp: '2025-12-04T22:30:00Z'
file_count: 42
total_size_bytes: 123456
files:
  - path: relative/path/file.py
    type: text
    size: 1234
    sha256: abc123...
    content: |
      file contents here
    is_executable: false
```

### Excluded by Default

- `.git`, `node_modules`, `__pycache__`, `.venv`, etc.
- Hidden files/directories (except `.github`, `.gitignore`, etc.)
- Files over 10MB
- Paths matching `.gitignore` patterns
