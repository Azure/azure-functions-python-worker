# Quick Start: Release Notes Generator

Generate organized release notes from PR lists in seconds.

## Usage

```
@workspace Can you generate release notes for [component]?

Component: [worker | runtime v1 | runtime v2]

[Paste your PR list here]
```

## Example

```
@workspace Can you generate release notes for the worker?

Component: worker

## What's Changed
* fix: fix protobuf import for V2 by @hallvictoria in https://github.com/Azure/azure-functions-python-worker/pull/1736
* feat: allow event loop to be uvloop by @EvanR-Dev in https://github.com/Azure/azure-functions-python-worker/pull/1697
* build: update version to 4.40.0 by @hallvictoria in https://github.com/Azure/azure-functions-python-worker/pull/1771
* refactor: Library worker renaming by @gavin-aguiar in https://github.com/Azure/azure-functions-python-worker/pull/1733
* test: add ServiceBus SDK tests by @hallvictoria in https://github.com/Azure/azure-functions-python-worker/pull/1678
```

## Component Detection

The agent automatically determines which PRs are relevant by analyzing file changes:

- **`workers/`** → Worker component
- **`runtimes/v1/`** → Runtime V1 component  
- **`runtimes/v2/`** → Runtime V2 component
- **Other paths** → All components

## Output

You'll get formatted release notes like:

**For Worker Releases:**

```markdown
# Release Notes

## General

### Build & Dependencies
* Update pyproject structure ([#1840](link)) - @hallvictoria

## Worker Version
* Update version to 4.43.0 ([#1831](link)) - @hallvictoria

## Python <= 3.12

### Features
* Allow event loop to be uvloop ([#1697](link)) - @EvanR-Dev

### Bug Fixes
* Fix protobuf import for V2 ([#1736](link)) - @hallvictoria

### Build & Dependencies
* Update Python SDK Version to 1.25.0b4 ([#1832](link)) - @hallvictoria

### Refactoring
* Library worker renaming ([#1733](link)) - @gavin-aguiar

### Tests
* Add ServiceBus SDK tests ([#1678](link)) - @hallvictoria

## Python 3.13+

### Features
* Support Python 3.14 ([#1766](link)) - @hallvictoria

### Bug Fixes
* Fix default cx deps path for 3.13 ([#1833](link)) - @hallvictoria

### Build & Dependencies
* Update Python SDK Version to 2.0.0 ([#1841](link)) - @hallvictoria

## Runtime and SDK Versions
azure-functions-runtime==1.1.0
azure-functions-runtime-v1==1.1.0
azure-functions==1.24.0 (Python < 3.10)
azure-functions==1.25.0b4 (Python 3.10-3.12)
azure-functions==2.0.0 (Python 3.13+)
```

**For Runtime Releases:**

```markdown
# Release Notes

## Features
* Allow event loop to be uvloop ([#1697](link)) - @EvanR-Dev

## Bug Fixes
* Fix protobuf import for V2 ([#1736](link)) - @hallvictoria
```

## Prerequisites

- GitHub CLI installed: `gh auth status`
- Repository access
- PRs include GitHub URLs or PR numbers

## Output File

Release notes are automatically saved to a temporary file:
- **Windows**: `%TEMP%\release-notes-<component>.md`
- **Linux/Mac**: `/tmp/release-notes-<component>.md`

You can easily open and copy from this file!

## Tips

✅ **DO:**
- Use conventional commit prefixes (`feat:`, `fix:`, `build:`, etc.)
- Specify exact component name
- Paste full PR list at once
- Include GitHub URLs

❌ **DON'T:**
- Mix different formats
- Forget the component name
- Use abbreviated PR info

## Need Help?

See full documentation: [release-notes-agent.md](../release-notes-agent.md)

Or ask: `@workspace How do I use the release notes generator?`
