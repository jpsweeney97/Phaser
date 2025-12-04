# Creating Audits with Phaser

Guide for Claude (in claude.ai) to generate Phaser-compatible audits.

---

## When User Requests an Audit

User might say:
- "Audit my project"
- "Review this codebase and suggest improvements"
- "What's wrong with my code?"
- "Give me a refactoring plan"

---

## Step 1: Gather Information

Ask for or obtain:

1. **Codebase access** (one of):
   - Manifest file (file listing with contents)
   - Uploaded source files
   - Project description + key file contents

2. **Tech stack** (or infer from code):
   - Language, framework, platform
   - Build system, dependencies
   - Architecture patterns used

3. **Priorities** (optional):
   - "Focus on performance"
   - "Testing is most important"
   - "Just quick wins for now"

---

## Step 2: Analyze the Codebase

Examine code for issues in these categories:

| Category | Look For |
|----------|----------|
| Architecture | God objects, tight coupling, wrong patterns |
| Code Quality | Long files, duplication, magic numbers |
| Testing | Missing tests, flaky tests, no mocks |
| Performance | N+1 queries, blocking I/O, no caching |
| Reliability | Poor error handling, race conditions |
| Security | Exposed secrets, injection risks |
| DevEx | No linting, missing docs, complex setup |
| Documentation | Missing READMEs, outdated docs |

Rate each finding:
- **Major**: Significant impact, should fix
- **Minor**: Nice-to-have, low impact

---

## Step 3: Design Phases

Convert findings into executable phases:

### Ordering (Critical)
1. **Low risk first**: Linting, constants, docs
2. **Medium risk next**: Refactors, new patterns
3. **High risk last**: Architectural changes

### Phase Design
Each phase should:
- Be completable in 30-60 minutes
- Have clear acceptance criteria
- Include verification steps
- Be independently valuable

### Dependencies
If Phase B depends on Phase A:
- Phase A comes first
- Note dependency in Phase B's context
- Keep dependencies minimal

---

## Step 4: Generate Setup Block

Use the templates in `templates/`:

1. **CONTEXT.md** from `CONTEXT.template.md`
   - Fill in metadata
   - Set Test Command appropriately if project doesn't use `make test`
   - List all phases in status section
   - Add project-specific context

2. **Phase files** from `phase.template.md`
   - One file per phase
   - Name as `NN-slug.md`
   - Include all sections

3. **CURRENT.md** from `CURRENT.template.md`
   - Comprehensive findings
   - Deep dives for complex issues
   - Phase summary table

4. **Wrap in setup block** from `setup-block.template.md`
   - Standard instructions at top
   - All files with delimiters
   - No markdown code fences inside

---

## Step 5: Deliver to User

Provide:
1. Brief summary of findings
2. Phase overview (what will be done)
3. The complete setup block

Example delivery:

> I've analyzed your codebase and found 12 issues (5 major, 7 minor). Here's a 10-phase improvement plan:
>
> **Phases:**
> 1. Fix singleton pattern (Low risk)
> 2. Add linting config (Low risk)
> ...
>
> **Setup block:**
> \`\`\`
> === AUDIT SETUP START ===
> ...
> === AUDIT SETUP END ===
> \`\`\`
>
> To run: Open Claude Code in your project, paste "Set up this audit:" followed by the block above, then say "next" repeatedly.

---

## Common Patterns

### Swift/iOS Projects
- Check for @Observable vs ObservableObject
- Look for @Environment vs @EnvironmentObject
- Verify SwiftUI patterns match iOS version
- Check for Sendable conformance

### Node/TypeScript Projects
- Check for proper async/await usage
- Look for unhandled promise rejections
- Verify TypeScript strict mode
- Check for dependency vulnerabilities

### Python Projects
- Check for type hints
- Look for proper exception handling
- Verify virtual environment usage
- Check for requirements.txt vs pyproject.toml

---

## Quality Checklist

Before delivering:

- [ ] All phases have clear acceptance criteria
- [ ] Phases are ordered by risk (low → high)
- [ ] Each phase has rollback commands
- [ ] Build/test verification in each phase
- [ ] No phase takes more than 60 minutes
- [ ] Setup block has no markdown fences inside
- [ ] CONTEXT.md has correct phase count
- [ ] Metadata is accurate

---

*Phaser v1*
