# Impromptu Audit Setup Block

## Instructions

1. Copy everything from `=== AUDIT SETUP START ===` to `=== AUDIT SETUP END ===` (inclusive)
2. In Claude Code, say: "Set up this audit"
3. Paste the copied block
4. Claude Code will parse the `===FILE: path===` markers and create each file

---

=== AUDIT SETUP START ===

SETUP INSTRUCTIONS FOR CLAUDE CODE:

Parse this block and perform the following steps:

1. ARCHIVE EXISTING AUDIT (if .audit/ folder exists):
   - Read metadata from .audit/CONTEXT.md for project_name, audit_slug, audit_date
   - Create ~/Documents/Audits/{project_name}/ if it doesn't exist
   - Copy .audit/CURRENT.md to ~/Documents/Audits/{project_name}/{audit_date}-{audit_slug}-INCOMPLETE.md
   - Delete .audit/ folder

2. CREATE DIRECTORY STRUCTURE:
   - Create .audit/
   - Create .audit/phases/

3. CREATE FILES:
   - For each ===FILE: {path}=== section below, create the file at that path
   - Write all content between ===FILE: {path}=== and ===END FILE=== to that file

4. UPDATE .gitignore:
   - If .gitignore exists and doesn't contain ".audit/", append it
   - If .gitignore doesn't exist, create it with ".audit/" as content

5. UPDATE GLOBAL CLAUDE.md (first audit only):
   - Read ~/.claude/CLAUDE.md
   - Search for "<!-- AUDIT-SYSTEM -->"
   - If NOT found, append this to the "Project-Specific Context" section:
     
     <!-- AUDIT-SYSTEM -->
     **Active Audit System:**
     If `.audit/` exists in the current project, read `.audit/CONTEXT.md` immediately before starting any work. It contains:
     - Current audit context and scope
     - Phase status checklist  
     - Automation rules for executing, skipping, and archiving
     - Commands you should recognize (next, skip, status, etc.)
     
     Follow all instructions in CONTEXT.md precisely. Phase completion, archiving, and state management are handled automatically based on those rules.
     <!-- /AUDIT-SYSTEM -->

6. CONFIRM:
   - List all files created
   - Note any modifications to .gitignore or ~/.claude/CLAUDE.md
   - Say: "Audit ready. Say 'next' to begin Phase 1."

---

===FILE: .audit/CONTEXT.md===
# Audit Context: Impromptu

> **For Claude Code:** Read this file completely before starting any audit-related work.

---

## Metadata

| Field | Value |
|-------|-------|
| Project | Impromptu |
| Audit | architecture-refactor |
| Date | 2024-12-04 |
| Version | 1 |

---

## Summary

This audit addresses architectural issues in Impromptu, a macOS SwiftUI application for LLM prompt engineering. Primary focus areas: eliminating singleton patterns, decomposing large components, adding testability infrastructure, implementing caching, and improving developer experience with linting and build tooling.

---

## Phase Status

- [ ] Phase 1: Convert ExportService from Singleton to Dependency Injection
- [ ] Phase 2: Add SwiftLint Configuration and Makefile
- [ ] Phase 3: Extract DateFormatter Utilities and Constants
- [ ] Phase 4: Decompose ConversationView into Focused Components
- [ ] Phase 5: Create Shared RetryPolicy Utility
- [ ] Phase 6: Add StorageService Protocol for Testability
- [ ] Phase 7: Implement Prompt Library Caching
- [ ] Phase 8: Add Basic XCUITest for Clarification Flow
- [ ] Phase 9: Add CHANGELOG and Improve Documentation
- [ ] Phase 10: Refactor AppState to Reduce God Object Tendencies

**Legend:**
- [ ] = Incomplete (pending)
- [x] = Complete (verified)
- [SKIPPED] = Skipped by user

---

## Commands

Recognize these commands from the user (case-insensitive, flexible phrasing):

| User Says | Action |
|-----------|--------|
| "next", "continue", "proceed", "go" | Execute next incomplete phase |
| "skip", "skip this", "skip phase N" | Mark phase as SKIPPED |
| "redo N", "redo phase N", "re-run phase N" | Reset phase to incomplete and execute |
| "status", "audit status", "show status" | Display phase checklist |
| "abandon", "abandon audit" | Delete .audit/ without archiving |
| "show full audit", "full report" | Display contents of CURRENT.md |

---

## Automation Rules

### 1. Phase Execution

When executing a phase:

1. Identify the first phase marked [ ] (incomplete)
2. If no incomplete phases exist, trigger completion (see Rule 5)
3. Read the corresponding file: .audit/phases/{NN}-{slug}.md
4. Execute all instructions in the phase file
5. Run verification steps (build, test, lint as applicable)
6. On success:
   - Update this file: change [ ] to [x] for that phase
   - Report: "Phase N complete: {description}"
   - Check if all phases are now complete/skipped (trigger Rule 5 if yes)
7. On failure:
   - Attempt to fix the issue (up to 3 attempts)
   - If fixed, proceed to success
   - If still failing after 3 attempts, report what failed, what was attempted, and suggest alternatives
   - Leave phase as [ ]
   - Do NOT continue to next phase

### 2. Phase Skipping

When user requests skip:

1. If "skip" with no number: skip the next incomplete phase
2. If "skip phase N": skip phase N specifically
3. Update this file: change [ ] to [SKIPPED]
4. Report: "Phase N skipped: {description}"
5. Check if all phases are now complete/skipped (trigger Rule 5 if yes)

### 3. Phase Redo

When user requests redo:

1. Validate phase number exists (1-10 for this audit)
2. Update this file: change [x] or [SKIPPED] back to [ ]
3. Execute the phase (follow Rule 1)

### 4. Status Report

When user requests status:

1. Display the Phase Status section from this file
2. Summarize: "N complete, M skipped, P remaining"

### 5. Completion & Auto-Archive

Triggered when all phases are [x] or [SKIPPED]:

1. Run final verification:
   - Execute: make test (or xcodebuild -scheme Impromptu -configuration Debug test)
   - If tests fail: report failure, do NOT proceed with archive, leave .audit/ in place

2. Commit any uncommitted changes:
   - Check: git status --porcelain
   - If changes exist: git add -A && git commit -m "Complete architecture-refactor audit"

3. Create archive directory:
   - Create ~/Documents/Audits/Impromptu/ if it doesn't exist

4. Determine archive filename:
   - If ALL phases are [SKIPPED]: 2024-12-04-architecture-refactor-SKIPPED.md
   - Otherwise: 2024-12-04-architecture-refactor.md
   - If filename exists, append -2, -3, etc. until unique

5. Copy .audit/CURRENT.md to archive path

6. Create git tag:
   - Execute: git tag audit/2024-12-04-architecture-refactor
   - If tag exists, append -2, -3, etc.

7. Delete .audit/ folder entirely

8. Report summary:
   - "Audit complete."
   - "Phases: N completed, M skipped"
   - "Commits made: (list recent commits from this audit)"
   - "Tag created: audit/2024-12-04-architecture-refactor"
   - "Archived to: {full_path}"
   - "To push tag: git push --tags"

### 6. Abandon

When user requests abandon:

1. Delete .audit/ folder entirely
2. Do NOT archive anything
3. Report: "Audit abandoned. Removed .audit/ folder."

### 7. Error Handling

| Situation | Response |
|-----------|----------|
| "next" but no .audit/ exists | "No active audit found." |
| "skip phase 99" (invalid) | "Invalid phase number. This audit has 10 phases." |
| Phase file missing | "Phase file not found: {path}. Check .audit/phases/ directory." |
| Cannot create archive directory | Report error and suggest manual creation |
| Cannot delete .audit/ | Report error and suggest manual deletion |

---

## Critical Reminders

1. Always read this file first when user mentions audit, phases, or uses commands above
2. Update this file after every phase execution (success, skip, or redo)
3. State is persistent — this file on disk is the source of truth
4. Build and test after each phase before marking complete
5. 3 attempts max on failures, then stop and report

---

## Project-Specific Context

- Platform: macOS 14+ (Sonoma)
- Language: Swift 5.9+
- UI Framework: SwiftUI with @Observable (NOT ObservableObject)
- DI Pattern: @Environment (NOT @EnvironmentObject)
- Storage: Local JSON files + macOS Keychain
- Dependencies: None — pure Apple frameworks
- Build: xcodebuild -scheme Impromptu -configuration Debug build
- Test: xcodebuild -scheme Impromptu -configuration Debug test
===END FILE===

===FILE: .audit/phases/01-export-service-di.md===
# Phase 1: Convert ExportService from Singleton to Dependency Injection

## Context

The audit identified that ExportService uses a singleton pattern (ExportService.shared) while all other services in Impromptu use proper dependency injection via @Environment. This inconsistency makes testing difficult and violates the project's architectural patterns.

## Goal

Convert ExportService to a standard injectable service, add it to AppState, and update all consumers to use @Environment injection instead of .shared.

## Files

- Impromptu/Core/Services/ExportService.swift (modify)
- Impromptu/App/AppState.swift (modify)
- Impromptu/App/ImpromptuApp.swift (modify)
- Impromptu/Features/Export/ExportSheet.swift (modify)
- Impromptu/Features/Settings/BackupRestoreView.swift (modify)

## Plan

1. Explore current usage:
   rg "ExportService.shared" --type swift
   rg "ExportService" --type swift | head -30

2. Modify ExportService.swift:
   - Remove static let shared = ExportService()
   - Remove private init() to allow normal instantiation
   - Keep the class otherwise unchanged

3. Update AppState.swift:
   - Add let exportService = ExportService() alongside other service instantiations

4. Update ImpromptuApp.swift:
   - Add .environment(appState.exportService) to the view hierarchy

5. Update ExportSheet.swift:
   - Change from parameter injection to @Environment(ExportService.self) private var exportService
   - Update init if needed

6. Update BackupRestoreView.swift:
   - Change from ExportService.shared to @Environment(ExportService.self) private var exportService

7. Search for any remaining .shared references:
   rg "ExportService.shared" --type swift

8. Verify build:
   xcodebuild -scheme Impromptu -configuration Debug build 2>&1 | tail -20

9. Run tests:
   xcodebuild -scheme Impromptu -configuration Debug test 2>&1 | tail -30

## Acceptance Criteria

- No references to ExportService.shared remain in the codebase
- ExportService is instantiated in AppState
- ExportService is injected via .environment() in ImpromptuApp
- All views use @Environment(ExportService.self) to access the service
- Build succeeds with no warnings related to this change
- All existing tests pass

## Rollback

git checkout -- Impromptu/Core/Services/ExportService.swift Impromptu/App/AppState.swift Impromptu/App/ImpromptuApp.swift Impromptu/Features/Export/ExportSheet.swift Impromptu/Features/Settings/BackupRestoreView.swift
===END FILE===

===FILE: .audit/phases/02-swiftlint-makefile.md===
# Phase 2: Add SwiftLint Configuration and Makefile

## Context

The Impromptu codebase lacks automated linting enforcement and portable build scripts. The README references shell aliases that are user-specific. Adding SwiftLint and a Makefile will improve code consistency and developer onboarding.

## Goal

Create a .swiftlint.yml configuration file with sensible defaults, a Makefile with common development tasks, and a proper .gitignore.

## Files

- .swiftlint.yml (create)
- Makefile (create)
- .gitignore (create or update)

## Plan

1. Check if SwiftLint is available:
   which swiftlint || echo "SwiftLint not installed - Makefile will work, lint target will require installation"

2. Create .swiftlint.yml with these settings:
   - included: Impromptu directory only
   - excluded: xcodeproj, tests, DerivedData
   - disabled_rules: trailing_whitespace, todo
   - opt_in_rules: empty_count, empty_string, force_unwrapping, implicitly_unwrapped_optional
   - line_length: warning 150, error 200
   - file_length: warning 500, error 1000
   - function_body_length: warning 50, error 100

3. Create Makefile with targets:
   - help (default): show available commands
   - build: xcodebuild debug build
   - test: xcodebuild debug test
   - lint: swiftlint lint
   - lint-fix: swiftlint with --fix
   - clean: remove DerivedData and xcodebuild clean
   - open: open xcodeproj

4. Create or update .gitignore:
   - DerivedData/
   - *.xcuserstate
   - xcuserdata/
   - .DS_Store
   - .build/
   - .swiftpm/
   - .audit/

5. Verify Makefile works:
   make help
   make build

6. Run initial lint (warnings expected):
   make lint 2>&1 | head -30

## Acceptance Criteria

- .swiftlint.yml exists with configuration as specified
- Makefile exists with help, build, test, lint, lint-fix, clean, open targets
- .gitignore exists and includes Xcode artifacts, macOS files, and .audit/
- make build completes successfully
- make help displays usage information

## Rollback

rm -f .swiftlint.yml Makefile
git checkout -- .gitignore 2>/dev/null || rm -f .gitignore
===END FILE===

===FILE: .audit/phases/03-dateformatter-constants.md===
# Phase 3: Extract DateFormatter Utilities and Constants

## Context

The codebase creates DateFormatter instances inline in multiple locations. DateFormatters are expensive to create. Additionally, several magic numbers exist throughout the UI code (bubble widths, animation durations, etc.).

## Goal

Create shared DateFormatter extensions and extract magic numbers to a ViewConstants enum.

## Files

- Impromptu/Shared/Extensions/DateFormatter+Presets.swift (create)
- Impromptu/Shared/ViewConstants.swift (create)
- Impromptu/Features/Clarification/MessageBubble.swift (modify)
- Impromptu/Features/Clarification/ConversationView.swift (modify)
- Other files with inline DateFormatter or magic numbers (as discovered)

## Plan

1. Find all DateFormatter usage:
   rg "DateFormatter\(\)" --type swift -l
   rg "DateFormatter\(\)" --type swift

2. Find magic numbers in views:
   rg "Spacer\(minLength:" --type swift
   rg "\.frame\((width|height):" --type swift | rg "\d{2,3}" | head -20

3. Create DateFormatter+Presets.swift with static formatters:
   - shortTime: timeStyle .short
   - yearMonth: "yyyy-MM" format
   - mediumDate: dateStyle .medium
   - shortDateTime: dateStyle .short, timeStyle .short

4. Create ViewConstants.swift with enums:
   - Chat: maxBubbleWidth (400), minSpacerWidth (60), padding values, corner radius
   - Timing: defaultAnimation (0.2), autoDismissDelay (5.0), etc.
   - Layout: defaultPadding, compactPadding, spacing values
   - Window: sizes for main, library, templates, insights windows

5. Update MessageBubble.swift:
   - Replace DateFormatter() with DateFormatter.shortTime
   - Replace 400 with ViewConstants.Chat.maxBubbleWidth
   - Replace 60 with ViewConstants.Chat.minSpacerWidth

6. Update other files similarly based on grep findings

7. Verify no inline DateFormatter() in views:
   rg "DateFormatter\(\)" Impromptu/Features --type swift

8. Build and test:
   make build
   make test

## Acceptance Criteria

- DateFormatter+Presets.swift exists with static formatters
- ViewConstants.swift exists with organized constant enums
- No inline DateFormatter() instantiation in view code
- Magic numbers for dimensions/timing are replaced with constants
- Build succeeds
- All tests pass

## Rollback

rm -f Impromptu/Shared/Extensions/DateFormatter+Presets.swift Impromptu/Shared/ViewConstants.swift
git checkout -- Impromptu/Features/
===END FILE===

===FILE: .audit/phases/04-conversationview-decomposition.md===
# Phase 4: Decompose ConversationView into Focused Components

## Context

ConversationView.swift is approximately 500 lines and handles multiple distinct UI concerns: message rendering, input handling, error display, streaming, and completion celebration. This makes it difficult to maintain and test.

## Goal

Extract logical sections into separate view files while maintaining current functionality.

## Files

- Impromptu/Features/Clarification/ConversationView.swift (refactor to under 200 lines)
- Impromptu/Features/Clarification/MessageListView.swift (create)
- Impromptu/Features/Clarification/ChatInputView.swift (create)
- Impromptu/Features/Clarification/ErrorBannerView.swift (create)
- Impromptu/Features/Clarification/StreamingMessageView.swift (create)

## Plan

1. Read and understand current ConversationView.swift:
   wc -l Impromptu/Features/Clarification/ConversationView.swift
   head -100 Impromptu/Features/Clarification/ConversationView.swift

2. Identify extractable sections:
   - Message list with ScrollViewReader
   - Input field area
   - Error banner display
   - Streaming text indicator

3. Create MessageListView.swift:
   - Props: messages, streamingText, isStreaming, scrollTarget binding
   - Contains: ScrollViewReader, LazyVStack, ForEach over messages
   - Handles: scroll-to-bottom behavior

4. Create ChatInputView.swift:
   - Props: text binding, placeholder, isDisabled, onSubmit callback
   - Contains: TextField, submit button
   - Handles: focus state, submit validation

5. Create ErrorBannerView.swift:
   - Props: error (LLMError), onRetry callback, onDismiss callback
   - Contains: error display with icon, message, retry/dismiss buttons

6. Create StreamingMessageView.swift:
   - Props: text string
   - Contains: message bubble with blinking cursor animation

7. Refactor ConversationView.swift to compose these views (target under 200 lines)

8. Add #Preview to each new view

9. Verify build:
   make build

10. Manual UI test:
    - Start new session
    - Verify messages appear
    - Verify input works
    - Verify streaming display

11. Run tests:
    make test

## Acceptance Criteria

- ConversationView.swift is under 200 lines
- MessageListView.swift exists with message rendering logic
- ChatInputView.swift exists with input handling
- ErrorBannerView.swift exists with error display
- StreamingMessageView.swift exists with streaming indicator
- Each new view has a #Preview
- All existing functionality works identically
- Build succeeds
- All tests pass

## Rollback

git checkout -- Impromptu/Features/Clarification/ConversationView.swift
rm -f Impromptu/Features/Clarification/MessageListView.swift
rm -f Impromptu/Features/Clarification/ChatInputView.swift
rm -f Impromptu/Features/Clarification/ErrorBannerView.swift
rm -f Impromptu/Features/Clarification/StreamingMessageView.swift
===END FILE===

===FILE: .audit/phases/05-retry-policy.md===
# Phase 5: Create Shared RetryPolicy Utility

## Context

The three LLM providers (AnthropicProvider, OpenAIProvider, GoogleProvider) each implement their own retry logic with exponential backoff and jitter. This duplication (~50 lines each) violates DRY and risks inconsistent behavior.

## Goal

Create a shared RetryPolicy struct that encapsulates retry logic, then refactor all three providers to use it.

## Files

- Impromptu/Core/Networking/RetryPolicy.swift (create)
- Impromptu/Core/Networking/AnthropicProvider.swift (modify)
- Impromptu/Core/Networking/OpenAIProvider.swift (modify)
- Impromptu/Core/Networking/GoogleProvider.swift (modify)

## Plan

1. Examine current retry implementation:
   rg "withRetry|retry|Retry" Impromptu/Core/Networking --type swift -A 5
   rg "baseDelay|maxDelay|jitter" Impromptu/Core/Networking --type swift

2. Create RetryPolicy.swift:
   - Struct with: maxRetries (3), baseDelay (1.0), maxDelay (30.0), jitterFactor (0.1)
   - execute() method with operation closure, shouldRetry closure, retryAfter closure
   - Exponential backoff with jitter calculation
   - Task cancellation checking
   - Logging via os.Logger

3. Add preset configurations:
   - RetryPolicy.default: standard settings
   - RetryPolicy.aggressive: 5 retries, 0.5s base
   - RetryPolicy.patient: 3 retries, 2s base, 60s max

4. Add LLM-specific helpers:
   - RetryPolicy.forLLM(): configured for API calls
   - RetryPolicy.llmShouldRetry: checks LLMError.isRetryable
   - RetryPolicy.llmRetryAfter: extracts retry-after from rate limit errors

5. Update AnthropicProvider:
   - Remove private withRetry function
   - Use RetryPolicy.forLLM().execute(...)

6. Update OpenAIProvider similarly

7. Update GoogleProvider similarly

8. Verify no private retry implementations remain:
   rg "private.*withRetry|private func.*retry" Impromptu/Core/Networking --type swift

9. Build and test:
   make build
   make test

## Acceptance Criteria

- RetryPolicy.swift exists with reusable retry logic
- All three providers use RetryPolicy instead of inline implementations
- No private withRetry functions remain in providers
- Retry behavior parameters match original (3 retries, 1s base, 30s max, 0.1 jitter)
- Build succeeds
- All tests pass

## Rollback

rm -f Impromptu/Core/Networking/RetryPolicy.swift
git checkout -- Impromptu/Core/Networking/AnthropicProvider.swift
git checkout -- Impromptu/Core/Networking/OpenAIProvider.swift
git checkout -- Impromptu/Core/Networking/GoogleProvider.swift
===END FILE===

===FILE: .audit/phases/06-storage-protocol.md===
# Phase 6: Add StorageService and KeychainService Protocols for Testability

## Context

StorageService performs real file I/O and KeychainService accesses macOS Keychain, which makes testing slow, fragile, and causes Keychain password dialogs during automated test runs. Protocol-based approaches allow mock injection and eliminate these issues.

## Goal

Create protocols for StorageService and KeychainService, enabling mock implementations for tests. This eliminates Keychain dialogs during xcodebuild test runs.

## Files

- Impromptu/Core/Persistence/StorageServiceProtocol.swift (create)
- Impromptu/Core/Persistence/StorageService.swift (modify to conform)
- Impromptu/Core/Services/KeychainServiceProtocol.swift (create)
- Impromptu/Core/Services/KeychainService.swift (modify to conform)
- ImpromptuTests/Mocks/MockStorageService.swift (create)
- ImpromptuTests/Mocks/MockKeychainService.swift (create)
- Services that use these services (update type annotations)

## Plan

1. Identify StorageService's public interface:
   rg "func " Impromptu/Core/Persistence/StorageService.swift | head -30
   rg "var.*URL" Impromptu/Core/Persistence/StorageService.swift

2. Identify KeychainService's public interface:
   rg "func " Impromptu/Core/Services/KeychainService.swift

3. Create StorageServiceProtocol.swift:
   - Protocol with AnyObject, Sendable conformance
   - Directory URL properties (base, prompts, sessions, templates, sequences, testResults)
   - Prompt CRUD methods
   - Session CRUD methods (including current session)
   - Template CRUD methods
   - Sequence CRUD methods

4. Create KeychainServiceProtocol.swift:
   protocol KeychainServiceProtocol: AnyObject, Sendable {
       func save(key: String, value: String) -> Bool
       func retrieve(key: String) -> String?
       func delete(key: String) -> Bool
       func hasKey(_ key: String) -> Bool
   }

5. Update StorageService to conform:
   - Add : StorageServiceProtocol to class declaration

6. Update KeychainService to conform:
   - Add : KeychainServiceProtocol to class declaration

7. Create MockStorageService.swift in test target:
   - In-memory dictionaries for each entity type
   - Implement all protocol methods
   - Add reset() helper for test cleanup

8. Create MockKeychainService.swift in test target:
   final class MockKeychainService: KeychainServiceProtocol, @unchecked Sendable {
       private var storage: [String: String] = [:]
       
       func save(key: String, value: String) -> Bool {
           storage[key] = value
           return true
       }
       
       func retrieve(key: String) -> String? {
           storage[key]
       }
       
       func delete(key: String) -> Bool {
           storage.removeValue(forKey: key) != nil
       }
       
       func hasKey(_ key: String) -> Bool {
           storage[key] != nil
       }
       
       func reset() {
           storage.removeAll()
       }
       
       // Pre-populate with test API keys
       func setupTestKeys() {
           storage["anthropic_api_key"] = "test-key-anthropic"
           storage["openai_api_key"] = "test-key-openai"
           storage["google_api_key"] = "test-key-google"
       }
   }

9. Update LLM providers to accept KeychainServiceProtocol:
   - AnthropicProvider(keychainService: KeychainServiceProtocol, ...)
   - OpenAIProvider(keychainService: KeychainServiceProtocol, ...)
   - GoogleProvider(keychainService: KeychainServiceProtocol, ...)

10. Update test setup to use mocks:
    - Find tests that trigger keychain access
    - Inject MockKeychainService instead

11. Build and test (should complete without Keychain dialogs):
    make build
    make test

## Acceptance Criteria

- StorageServiceProtocol.swift exists with complete interface
- KeychainServiceProtocol.swift exists with complete interface
- StorageService conforms to StorageServiceProtocol
- KeychainService conforms to KeychainServiceProtocol
- MockStorageService.swift exists in test target
- MockKeychainService.swift exists in test target
- LLM providers accept protocol types
- Tests run WITHOUT triggering Keychain password dialogs
- Build succeeds
- All tests pass

## Rollback

rm -f Impromptu/Core/Persistence/StorageServiceProtocol.swift
rm -f Impromptu/Core/Services/KeychainServiceProtocol.swift
rm -f ImpromptuTests/Mocks/MockStorageService.swift
rm -f ImpromptuTests/Mocks/MockKeychainService.swift
git checkout -- Impromptu/Core/Persistence/StorageService.swift
git checkout -- Impromptu/Core/Services/KeychainService.swift
git checkout -- Impromptu/Core/Networking/
===END FILE===

===FILE: .audit/phases/07-library-caching.md===
# Phase 7: Implement Prompt Library Caching

## Context

PromptLibraryService.loadPrompts() reads all JSON files from disk synchronously every time it's called. This becomes slow with many prompts and blocks the main thread despite showing a loading indicator.

## Goal

Implement an in-memory cache with background loading and cache invalidation.

## Files

- Impromptu/Core/Services/PromptLibraryService.swift (major refactor)

## Plan

1. Read current implementation:
   rg "func loadPrompts" Impromptu/Core/Services/PromptLibraryService.swift -A 20

2. Add caching properties:
   - private var cache: [UUID: Prompt] = [:]
   - private var cacheValid: Bool = false
   - private var lastRefreshTime: Date?
   - private let cacheTTL: TimeInterval = 300 (5 minutes)
   - private var cacheExpired computed property

3. Implement async loading:
   - loadPrompts(forceRefresh: Bool = false) method
   - Return cached data if valid and not expired
   - Use Task.detached for background file I/O
   - Update cache and state on MainActor

4. Update save to update cache:
   - After saving to disk, update cache[prompt.id]
   - Re-sort prompts array

5. Update delete/archive/unarchive to update cache similarly

6. Add refreshFromDisk() method for force refresh

7. Update computed properties (activePrompts, archivedPrompts, deletedPrompts) to filter from prompts array

8. Build and test:
   make build
   make test

9. Manual testing:
   - Create several prompts
   - Navigate away and back to library
   - Verify quick load (no spinner on second view)
   - Edit a prompt, verify immediate update

## Acceptance Criteria

- Prompts are cached in memory after first load
- Subsequent calls to loadPrompts() return cached data instantly (no file I/O)
- Cache is updated on save, delete, archive, unarchive
- forceRefresh: true bypasses cache
- Loading happens on background thread
- Build succeeds
- All tests pass

## Rollback

git checkout -- Impromptu/Core/Services/PromptLibraryService.swift
===END FILE===

===FILE: .audit/phases/08-xcuitest.md===
# Phase 8: Add Basic XCUITest for Clarification Flow

## Context

The project has 110 unit/integration tests but no UI tests. A basic XCUITest covering the happy-path clarification flow would catch regressions in the core user journey.

## Goal

Create a UI test target and one test that covers: launch, new session, type request, receive question.

## Files

- ImpromptuUITests/ (create directory)
- ImpromptuUITests/ClarificationFlowUITests.swift (create)
- Impromptu.xcodeproj/project.pbxproj (modify to add UI test target - may require Xcode)
- Impromptu/App/ImpromptuApp.swift (add launch argument handling)

## Plan

1. Create UI test directory:
   mkdir -p ImpromptuUITests

2. Create ClarificationFlowUITests.swift:
   - XCTestCase subclass
   - setUp: create app, add --uitesting launch argument, launch
   - testNewSessionFlow: Cmd+N, type request, verify question appears
   - testLivingDocumentUpdates: verify task type detection

3. Add launch argument handling to ImpromptuApp.swift:
   - Check for --uitesting in CommandLine.arguments
   - If present, set hasCompletedOnboarding to true in UserDefaults

4. Add accessibility identifiers to key views (if not present):
   - Living document pane
   - Chat input field
   - Message list

5. Note: Adding the UI test target to the Xcode project may require manual steps in Xcode:
   - File > New > Target > UI Testing Bundle
   - Name: ImpromptuUITests
   - Move created file into target

6. Build and run tests:
   xcodebuild -scheme Impromptu -destination 'platform=macOS' test

## Acceptance Criteria

- ImpromptuUITests/ directory exists
- ClarificationFlowUITests.swift exists with at least one test
- Launch arguments handled in ImpromptuApp for test mode
- UI test runs and passes (or clear instructions for user to complete Xcode setup)

## Rollback

rm -rf ImpromptuUITests/
git checkout -- Impromptu/App/ImpromptuApp.swift

## Note

If adding the UI test target programmatically is not possible, inform the user:
"I've created the test files. To complete setup:
1. Open Impromptu.xcodeproj in Xcode
2. File > New > Target > UI Testing Bundle
3. Name it 'ImpromptuUITests'
4. Drag ClarificationFlowUITests.swift into the new target
5. Run tests with make test"
===END FILE===

===FILE: .audit/phases/09-changelog-docs.md===
# Phase 9: Add CHANGELOG and Improve Documentation

## Context

The project has excellent documentation but lacks a CHANGELOG for tracking changes. Some services lack header documentation, and there's a keyboard shortcut discrepancy between docs.

## Goal

Create a CHANGELOG, add missing file headers, and fix documentation inconsistencies.

## Files

- CHANGELOG.md (create)
- CLAUDE.md (verify/update keyboard shortcuts)
- docs/PRD.md (verify/update keyboard shortcuts)
- Impromptu/Core/Services/FeedbackService.swift (add header)
- Impromptu/Core/Services/RateLimitService.swift (add header)
- Impromptu/Core/Services/SequenceService.swift (add header)

## Plan

1. Check actual keyboard shortcut implementation:
   rg "keyboardShortcut|\.keyboard" Impromptu/App/ImpromptuApp.swift
   rg "library" CLAUDE.md docs/PRD.md

2. Create CHANGELOG.md following Keep a Changelog format:
   - [Unreleased] section with Added and Technical subsections
   - List all major features
   - Note technical stack details
   - Placeholder [1.0.0] - TBD section

3. Fix keyboard shortcut discrepancy:
   - Check ImpromptuApp.swift for actual implementation
   - Update CLAUDE.md to match
   - Update docs/PRD.md to match

4. Add header to FeedbackService.swift:
   - File purpose
   - Key responsibilities

5. Add header to RateLimitService.swift:
   - File purpose
   - Key responsibilities

6. Add header to SequenceService.swift:
   - File purpose
   - Key responsibilities

7. Verify test count in CLAUDE.md:
   rg "func test" ImpromptuTests --type swift | wc -l
   Update if differs from stated count

8. Build to verify no syntax errors:
   make build

## Acceptance Criteria

- CHANGELOG.md exists with comprehensive initial content
- Keyboard shortcuts are consistent across CLAUDE.md and docs/PRD.md
- FeedbackService.swift has descriptive file header
- RateLimitService.swift has descriptive file header
- SequenceService.swift has descriptive file header
- Test count in CLAUDE.md is accurate
- Build succeeds

## Rollback

rm -f CHANGELOG.md
git checkout -- CLAUDE.md docs/PRD.md
git checkout -- Impromptu/Core/Services/FeedbackService.swift
git checkout -- Impromptu/Core/Services/RateLimitService.swift
git checkout -- Impromptu/Core/Services/SequenceService.swift
===END FILE===

===FILE: .audit/phases/10-appstate-refactor.md===
# Phase 10: Refactor AppState to Reduce God Object Tendencies

## Context

AppState currently instantiates and holds 10+ services, manages provider selection, and coordinates application-level state. This audit identified it as approaching "God Object" status, creating tight coupling.

## Goal

Introduce lightweight coordinator objects to group related services, reducing AppState to a thin composition root.

## Files

- Impromptu/App/AppState.swift (major refactor)
- Impromptu/App/Coordinators/PersistenceCoordinator.swift (create)
- Impromptu/App/Coordinators/LLMCoordinator.swift (create)
- Impromptu/App/ImpromptuApp.swift (update environment injection)

## Plan

1. Analyze current AppState:
   rg "let |var " Impromptu/App/AppState.swift | head -30
   wc -l Impromptu/App/AppState.swift

2. Create Coordinators directory:
   mkdir -p Impromptu/App/Coordinators

3. Create PersistenceCoordinator.swift:
   - @Observable class
   - Properties: storage, libraryService, templateService, sequenceService
   - Init: create services, trigger initial loads

4. Create LLMCoordinator.swift:
   - @Observable class
   - Properties: keychainService, rateLimitService, currentProvider, currentProviderName
   - Init: create services, call refreshProvider()
   - refreshProvider(): read default from UserDefaults, create appropriate provider
   - provider(for:): create provider for specific model

5. Simplify AppState:
   - Properties: persistence (coordinator), llm (coordinator), onboardingService, insightsService, feedbackService, exportService
   - Init: create coordinators first, then standalone services
   - Convenience accessors if needed

6. Update ImpromptuApp.swift environment injection:
   - Inject coordinator properties individually
   - e.g., .environment(appState.persistence.storage)

7. Update direct references:
   rg "appState\.storage|appState\.keychainService" --type swift
   Replace with coordinator paths

8. Build and test:
   make build
   make test

9. Verify AppState line count:
   wc -l Impromptu/App/AppState.swift
   (Should be under 50 lines)

## Acceptance Criteria

- PersistenceCoordinator.swift exists with storage-related services
- LLMCoordinator.swift exists with LLM-related services
- AppState.swift is under 50 lines
- All functionality works identically
- Build succeeds
- All tests pass
- Each coordinator has single responsibility

## Rollback

rm -rf Impromptu/App/Coordinators/
git checkout -- Impromptu/App/AppState.swift
git checkout -- Impromptu/App/ImpromptuApp.swift
===END FILE===

===FILE: .audit/CURRENT.md===
# Impromptu Repository Audit

**Audit Date:** 2024-12-04
**Audit Slug:** architecture-refactor
**Files Analyzed:** 117
**Total Size:** ~632KB

---

## I. Overview

### Project Understanding

Impromptu is a macOS native application that transforms vague user requests into structured, optimized prompts for LLMs through an iterative clarification process. It features a dual-pane interface (chat + living document), prompt library with versioning, multi-provider LLM support (Anthropic, OpenAI, Google), templates, feedback/insights systems, and comprehensive testing capabilities.

### Tech Stack

- Platform: macOS 14+ (Sonoma)
- Language: Swift 5.9+
- UI Framework: SwiftUI with @Observable (Swift 5.9+)
- Architecture: SwiftUI-native patterns with Environment-based DI
- Storage: Local JSON files + macOS Keychain
- Dependencies: None (pure Apple frameworks)

### Key Entry Points

1. ImpromptuApp.swift — App entry, window definitions, menu commands
2. AppState.swift — Service container, @Observable app-wide state
3. ClarificationEngine.swift — Core state machine for clarification flow
4. MainView.swift — Primary HSplitView composition

---

## II. Findings Summary

### Architecture (3 Major, 2 Minor)

- AppState approaching God Object status
- ExportService uses singleton pattern
- ClarificationEngine has too many responsibilities
- Mixed navigation patterns
- Prompt model in wrong location

### Code Quality (1 Major, 3 Minor)

- ConversationView is 500+ lines
- Magic numbers scattered
- Inconsistent date formatting
- Some long initializers

### Testing (2 Major, 2 Minor)

- No UI tests
- Services lack mock protocols
- Test sleep patterns create flakiness
- No snapshot tests

### Performance (2 Major, 2 Minor)

- Full library scan on every load
- No caching for decoded prompts
- DateFormatter created in loops
- Search is O(n) string matching

### Reliability (1 Major, 2 Minor)

- Inconsistent error propagation
- Race condition potential in ClarificationEngine
- Retry logic duplicated across providers

### DevEx (2 Major, 1 Minor)

- No linting configuration
- No Makefile or scripts
- No .gitignore visible

### Documentation (3 Minor)

- No CHANGELOG
- Some services lack headers
- Keyboard shortcut mismatch

---

## III. Phases

| # | Description | Risk | Est. Effort |
|---|-------------|------|-------------|
| 1 | ExportService DI conversion | Low | 30 min |
| 2 | SwiftLint + Makefile | Low | 20 min |
| 3 | DateFormatter + ViewConstants | Low | 30 min |
| 4 | ConversationView decomposition | Medium | 60 min |
| 5 | RetryPolicy utility | Medium | 45 min |
| 6 | StorageServiceProtocol | Medium | 45 min |
| 7 | Library caching | Medium | 60 min |
| 8 | XCUITest setup | Medium | 45 min |
| 9 | CHANGELOG + docs | Low | 30 min |
| 10 | AppState refactor | High | 60 min |

Total estimated effort: ~7 hours across 10 focused sessions

---

## IV. Detailed Findings

### Architecture & Design

**Major: AppState God Object**
Location: App/AppState.swift
Issue: Instantiates 10+ services, coordinates provider selection, manages app state
Impact: Tight coupling, difficult isolated testing
Fix: Extract into PersistenceCoordinator and LLMCoordinator

**Major: ExportService Singleton**
Location: Core/Services/ExportService.swift
Issue: Uses ExportService.shared while all other services use DI
Impact: Testing friction, hidden dependencies
Fix: Convert to @Environment injection

**Major: ClarificationEngine Responsibilities**
Location: Core/Services/ClarificationEngine.swift
Issue: Manages session, LLM, streaming, navigation, templates, auto-save, errors (~600 lines)
Impact: High cognitive load, change risk
Fix: Extract focused collaborators (future phase)

### Code Quality

**Major: ConversationView Size**
Location: Features/Clarification/ConversationView.swift
Issue: ~500 lines handling messages, input, errors, streaming, celebration
Impact: Hard to maintain and test
Fix: Extract MessageListView, ChatInputView, ErrorBannerView, StreamingMessageView

### Testing

**Major: No UI Tests**
Location: ImpromptuTests/
Issue: 110 unit tests but no XCUITest coverage
Impact: Core user flows not regression-tested
Fix: Add basic clarification flow UI test

**Major: No Mock Protocols**
Location: Core/Persistence/StorageService.swift
Issue: Tests use real file I/O
Impact: Slow, fragile tests
Fix: Add StorageServiceProtocol with MockStorageService

### Performance

**Major: Library Loading**
Location: Core/Services/PromptLibraryService.swift
Issue: Synchronous file I/O on every loadPrompts() call
Impact: UI jank with 50+ prompts
Fix: In-memory cache with background loading

**Major: Retry Duplication**
Location: Core/Networking/*.swift
Issue: ~50 lines duplicated in 3 providers
Impact: DRY violation, inconsistency risk
Fix: Shared RetryPolicy utility

### DevEx

**Major: No Linting**
Location: Project root
Issue: No SwiftLint configuration
Impact: Style inconsistency, no enforcement
Fix: Add .swiftlint.yml

**Major: No Build Scripts**
Location: Project root
Issue: README references personal aliases
Impact: Onboarding friction
Fix: Add Makefile

---

## V. Metadata

| Field | Value |
|-------|-------|
| Audit Date | 2024-12-04 |
| Audit Slug | architecture-refactor |
| Files Analyzed | 117 |
| Total Size | ~632KB |
| Test Count | 110 |
| Phases | 10 |
===END FILE===

=== AUDIT SETUP END ===
