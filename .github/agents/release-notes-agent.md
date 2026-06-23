# Release Notes Generator Agent

This agent automatically generates organized release notes from a list of Pull Requests for Azure Functions Python Worker components.

## Purpose

Streamline the release notes creation process by:
1. Analyzing PR file changes to determine component relevance
2. Filtering PRs by component (worker, runtime v1, or runtime v2)
3. Grouping PRs by category based on conventional commit prefixes
4. Generating clean, human-readable release notes in Markdown format

## How to Use

### Basic Usage

Invoke the agent with a list of PRs and specify the component:

```
@workspace /release-notes

Component: worker

## What's Changed
* fix: fix protobuf import for V2 by @hallvictoria in https://github.com/Azure/azure-functions-python-worker/pull/1736
* feat: allow event loop to be uvloop by @EvanR-Dev in https://github.com/Azure/azure-functions-python-worker/pull/1697
* build: update version to 4.40.0 by @hallvictoria in https://github.com/Azure/azure-functions-python-worker/pull/1771
```

### Supported Components

- **`worker`** - Azure Functions Python Worker
- **`runtime v1`** - Python Runtime V1
- **`runtime v2`** - Python Runtime V2

### Input Format

The agent accepts PR lists in the following format:
```
* <prefix>: <description> by @<author> in <github-url>
```

Example:
```
* fix: improve error handling by @johndoe in https://github.com/Azure/azure-functions-python-worker/pull/1234
```

You can also use shorthand:
```
* feat: new feature by @janedoe in #1235
```

## Component Detection Logic

The agent analyzes changed files in each PR to determine relevance:

| Path | Affects Component |
|------|------------------|
| `runtimes/v1/**` | Runtime V1 |
| `runtimes/v2/**` | Runtime V2 |
| `workers/**` | Worker |
| Other paths | All components |

**Examples:**
- PR changes only `workers/dispatcher.py` → Only relevant to **worker**
- PR changes only `runtimes/v1/setup.py` → Only relevant to **runtime v1**
- PR changes `setup.cfg` (root level) → Relevant to **all components**
- PR changes both `workers/loader.py` and `runtimes/v2/handler.py` → Relevant to **worker** and **runtime v2**

### Worker-Specific Version Updates

**Important:** Some PRs are worker-specific and will ONLY appear in worker releases:

1. **Azure Functions SDK updates** - PRs that update the `azure-functions` package in `workers/pyproject.toml`
   - Example: "Update Python SDK Version to 1.24.0"
   - These are **excluded** from runtime v1 and runtime v2 releases

2. **Worker version updates** - PRs that update version in `workers/*/version.py`
   - Example: "Update version to 4.40.1"
   - These are **excluded** from runtime v1 and runtime v2 releases

**Why?** These PRs only bump version numbers in the worker component and don't affect the runtime components, so they shouldn't appear in runtime release notes.

### Version Update Deduplication

**Important:** If multiple PRs update the same package to different versions, only the **latest version** is included.

**Example:** If PRs update `azure-functions` from 1.24.0b4 → 1.25.0b2 → 1.25.0b3, only the final update to 1.25.0b3 appears in release notes.

**Applies to:**
- `azure-functions` (Python SDK)
- `azure-functions-runtime` (Runtime V2)
- `azure-functions-runtime-v1` (Runtime V1)
- `azurefunctions-extensions-*` (Extension packages)

**Why?** Only the final version matters. Intermediate version bumps add noise without value.

## Category Classification

PRs are grouped by their title prefix:

| Prefix | Category | Example |
|--------|----------|---------|
| `feat:` | Features | New capabilities |
| `fix:` | Bug Fixes | Bug fixes and corrections |
| `build:` | Build & Dependencies | Version updates, dependencies |
| `refactor:` | Refactoring | Code restructuring |
| `test:` | Tests | Test changes |
| `chore:` | Chores | Maintenance, cleanup |
| `docs:` | Documentation | Doc updates |
| `perf:` | Performance | Performance improvements |
| `ci:` | CI/CD | Pipeline changes |

## Output Format

The agent generates release notes in this structure:

**For Worker Releases:**

```markdown
# Release Notes

## General

### Build & Dependencies
* Update pyproject for azure-functions 2.x structure ([#1840](https://github.com/Azure/azure-functions-python-worker/pull/1840)) - @hallvictoria

## Worker Version
* Update version to 4.43.0 ([#1831](https://github.com/Azure/azure-functions-python-worker/pull/1831)) - @hallvictoria

## Python <= 3.12

### Features
* Allow event loop to be uvloop ([#1697](https://github.com/Azure/azure-functions-python-worker/pull/1697)) - @EvanR-Dev

### Bug Fixes
* Fix protobuf import for V2 ([#1736](https://github.com/Azure/azure-functions-python-worker/pull/1736)) - @hallvictoria

### Build & Dependencies
* Update Python SDK Version to 1.25.0b4 ([#1832](https://github.com/Azure/azure-functions-python-worker/pull/1832)) - @hallvictoria

## Python 3.13+

### Features
* Support Python 3.14 ([#1766](https://github.com/Azure/azure-functions-python-worker/pull/1766)) - @hallvictoria

### Bug Fixes
* Fix default cx deps path for 3.13 ([#1833](https://github.com/Azure/azure-functions-python-worker/pull/1833)) - @hallvictoria

### Build & Dependencies
* Update Python SDK Version to 2.0.0 ([#1841](https://github.com/Azure/azure-functions-python-worker/pull/1841)) - @hallvictoria

## Runtime and SDK Versions
azure-functions-runtime==1.1.0
azure-functions-runtime-v1==1.1.0
azure-functions==1.24.0 (Python < 3.10)
azure-functions==1.25.0b4 (Python 3.10-3.12)
azure-functions==2.0.0 (Python 3.13+)
```

**For Runtime V1/V2 Releases:**

```markdown
# Release Notes

## Features
* Allow event loop to be uvloop ([#1697](https://github.com/Azure/azure-functions-python-worker/pull/1697)) - @EvanR-Dev

## Bug Fixes
* Fix protobuf import for V2 ([#1736](https://github.com/Azure/azure-functions-python-worker/pull/1736)) - @hallvictoria
```

**Note:** Worker releases are organized into multiple sections:

**Section order:**
1. **General** (optional): PRs that don't touch `workers/` directory (e.g., CI/CD, root configs)
2. **Worker Version**: Worker component version updates (e.g., "Update version to 4.43.0")
3. **Python <= 3.12**: Changes to `workers/azure_functions_worker/`
4. **Python 3.13+**: Changes to `workers/proxy_worker/`
5. **Runtime and SDK Versions**: Dependency versions at the END

**Python version classification:**
- **General section**: PRs NOT touching any files under `workers/`
- **Worker Version section**: PRs with title "Update version to 4.X.X"
- **Python <= 3.12**: PRs affecting ONLY `workers/azure_functions_worker/`
- **Python 3.13+**: PRs affecting ONLY `workers/proxy_worker/`
- **Both Python sections**: PRs affecting files in both worker directories, or `workers/` general files (e.g., `workers/pyproject.toml`, `workers/README.md`)

**Special handling for SDK updates:**
- "Update Python SDK Version" PRs are classified based on which Python version range uses that version in `workers/pyproject.toml`
- Example: Update to 2.0.0 (used by Python 3.13+) appears ONLY in Python 3.13+ section
- Example: Update to 1.25.0b4 (used by Python 3.10-3.12) appears ONLY in Python <= 3.12 section

The `azure-functions` SDK shows different versions for different Python version ranges.

Runtime releases do not include these sections or Python version splits.

## Prerequisites

- GitHub CLI installed and authenticated (`gh auth login`)
- Access to the Azure Functions Python Worker repository
- PRs must include full GitHub URLs or PR numbers if in the current repo

## Output

The agent will:
1. Display the formatted release notes in the chat
2. **Save the release notes to a temporary file** for easy copying:
   - **Windows**: `%TEMP%\release-notes-<component>.md`
   - **Linux/Mac**: `/tmp/release-notes-<component>.md`

You can open the file directly or copy its contents to your clipboard.

## Advanced Usage

### Multiple Components

Generate release notes for multiple components in one session:

```
@workspace /release-notes worker
[paste PR list]

@workspace /release-notes runtime v1
[paste PR list]

@workspace /release-notes runtime v2
[paste PR list]
```

### Handling Large PR Lists

For releases with many PRs (30+), the agent will:
- Process in batches to avoid rate limits
- Show progress updates
- Report any PRs that couldn't be fetched

### Cross-Component Changes

PRs that affect multiple components will appear in the release notes for all relevant components. The agent will note when a PR appears in multiple component releases.

## Troubleshooting

### "Authentication failed"
Run `gh auth login` to authenticate with GitHub.

### "PR not found"
Ensure you have access to the repository and the PR number is correct.

### "No PRs match this component"
Verify:
- The component name is exactly `worker`, `runtime v1`, or `runtime v2`
- The PRs actually touch files in that component's directory
- You're analyzing the correct repository

## Skill Details

This agent uses the `generate-release-notes` skill located at:
`.agents/skills/generate-release-notes/SKILL.md`

For detailed workflow and technical implementation, refer to the skill documentation.
