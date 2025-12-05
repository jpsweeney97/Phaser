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
