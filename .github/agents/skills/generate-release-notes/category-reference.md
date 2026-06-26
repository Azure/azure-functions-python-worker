# Release Notes Category Reference

This document provides the category classification rules for PR prefixes when generating release notes.

## Standard Categories

### Features (`feat:`)
**Description:** New features, capabilities, or enhancements that add functionality.

**Examples:**
- `feat: allow event loop to be uvloop`
- `feat: support python 3.14`
- `feat: support sb settlement client`

**Keywords:** add, support, implement, introduce, enable

---

### Bug Fixes (`fix:`)
**Description:** Bug fixes, error corrections, and issue resolutions.

**Examples:**
- `fix: fix protobuf import for V2`
- `fix: improve function error messages`
- `fix: 3.13 AppInsights logging`

**Keywords:** fix, correct, resolve, repair, patch

---

### Build & Dependencies (`build:`)
**Description:** Version updates, dependency changes, build configuration, and release preparation.

**Examples:**
- `build: update version to 4.40.0`
- `build: update Python SDK Version to 1.24.0`
- `build: use official grpc for python 3.14`

**Keywords:** update, upgrade, bump, version, dependency

**Special Note:** Some build PRs are worker-specific:
- PRs updating `azure-functions` package in `workers/pyproject.toml` (e.g., "Update Python SDK Version")
- PRs updating worker version in `workers/*/version.py` (e.g., "Update version to X.Y.Z")
- These PRs should ONLY appear in worker releases, not runtime v1 or runtime v2 releases

**Deduplication:** When multiple PRs update the same package (e.g., multiple `azure-functions` version updates), only the latest version (highest PR number) is included in the release notes. Older version updates for the same package are automatically excluded.

---

### Refactoring (`refactor:`)
**Description:** Code restructuring, reorganization, or improvements without changing behavior.

**Examples:**
- `refactor: Library worker renaming`
- `refactor: Moving threadpool configs to the library worker`

**Keywords:** refactor, rename, move, restructure, reorganize

---

### Tests (`test:`)
**Description:** Test additions, modifications, or test infrastructure changes.

**Examples:**
- `test: add ServiceBus SDK tests`
- `test: add 3.14 to tests`
- `test: add test only using worker dependencies`

**Keywords:** test, spec, e2e, integration test, unit test

---

### Chores (`chore:`)
**Description:** Maintenance tasks, cleanup, tooling, or non-functional changes.

**Examples:**
- `chore: add EOL log`
- `chore: validate artifact`
- `chore: remove 3.7 & 3.8 from worker nuget`

**Keywords:** chore, cleanup, remove, deprecate, housekeeping

---

### Documentation (`docs:`)
**Description:** Documentation updates, README changes, or comment improvements.

**Examples:**
- `docs: update API documentation`
- `docs: fix typo in README`
- `docs: add migration guide`

**Keywords:** docs, documentation, readme, guide

---

### Performance (`perf:`)
**Description:** Performance improvements and optimizations.

**Examples:**
- `perf: optimize function loading`
- `perf: reduce memory allocation`

**Keywords:** perf, optimize, performance, speed, faster

---

### CI/CD (`ci:`)
**Description:** Continuous integration, deployment pipeline, or workflow changes.

**Examples:**
- `ci: add 3.14 to tests`
- `ci: allow downloading artifact from partially successful pipelines`

**Keywords:** ci, pipeline, workflow, action, deploy

---

## Category Priority Order

When outputting release notes, use this order:

1. **Features** - Most visible to users
2. **Bug Fixes** - Important for stability
3. **Build & Dependencies** - Affects compatibility
4. **Refactoring** - Code quality improvements
5. **Tests** - Quality assurance
6. **Chores** - Maintenance
7. **Documentation** - Information updates
8. **Performance** - Optimization
9. **CI/CD** - Process improvements
10. **Other** - Anything that doesn't fit above

## Handling Edge Cases

### No Prefix
If a PR title has no recognizable prefix:
- Classify as "Other"
- Keep the original title intact
- Example: `Update documentation` → Other category

### Multiple Prefixes
If a PR title contains multiple prefixes (rare):
- Use the first prefix
- Example: `build: fix: update grpc` → Build & Dependencies

### Custom Prefixes
For project-specific prefixes not in the standard list:
- Create a new category using the prefix name
- Capitalize the first letter
- Place alphabetically after standard categories
- Example: `security: add vulnerability scan` → Security category

### Alternative Prefix Styles
Some teams use different styles:
- **Emoji prefixes:** `✨ add new feature` → Features
- **[Type] format:** `[FEATURE] add support` → Features
- **JIRA references:** `PROJ-123: fix bug` → Extract after the colon

When in doubt, look for keywords in the title to infer the category.

## Consolidation Rules

Some categories can be merged for cleaner output:

### Build & Dependencies
Combine these into one category:
- `build:`
- `deps:`
- `dependency:`
- Version updates

### Bug Fixes
Combine these into one category:
- `fix:`
- `bugfix:`
- `hotfix:`

### Documentation
Combine these into one category:
- `docs:`
- `doc:`
- `documentation:`

## Title Formatting

When displaying in release notes:
1. **Remove the prefix:** `fix: improve error messages` → `improve error messages`
2. **Capitalize first letter:** `improve error messages` → `Improve error messages`
3. **Keep original casing for proper nouns:** `python 3.14` → `Python 3.14`
4. **Preserve technical terms:** `gRPC`, `AppInsights`, `ServiceBus`

## Real-World Examples

From actual Azure Functions Python Worker releases:

```markdown
## Features
* Allow event loop to be uvloop ([#1697](link)) - @EvanR-Dev
* Support Python 3.14 ([#1766](link)) - @hallvictoria
* Support ServiceBus settlement client ([#1763](link)) - @hallvictoria

## Bug Fixes
* Fix protobuf import for V2 ([#1736](link)) - @hallvictoria
* Logging fix for Python 3.13 ([#1745](link)) - @gavin-aguiar
* Improve function error messages ([#1743](link)) - @hallvictoria

## Build & Dependencies
* Update version to 4.40.0 ([#1771](link)) - @hallvictoria
* Update Python SDK Version to 1.24.0 ([#1755](link)) - @hallvictoria
* Update azurefunctions-extensions-base to 1.1.0 ([#1765](link)) - @hallvictoria
```

## Deduplication Rules

### Version Update Deduplication

When generating release notes, if multiple PRs update the same package to different versions, only the **latest version** (highest PR number) is included.

**Packages that are deduplicated:**
- `azure-functions` (Python SDK)
- `azure-functions-runtime` (Runtime V2)
- `azure-functions-runtime-v1` (Runtime V1)
- `azurefunctions-extensions-*` (Extension packages like blob, servicebus, etc.)

**Example:**

**Input PRs:**
```markdown
* Update Python SDK Version to 1.24.0b4 ([#1755](link)) - @hallvictoria
* Update Python SDK Version to 1.25.0b2 ([#1798](link)) - @hallvictoria
* Update Python SDK Version to 1.25.0b3 ([#1822](link)) - @hallvictoria
* Update azurefunctions-extensions-blob version to 1.1.1 ([#1762](link)) - @hallvictoria
* Update azurefunctions-extensions-blob version to 1.1.2 ([#1821](link)) - @hallvictoria
```

**Output (after deduplication):**
```markdown
* Update Python SDK Version to 1.25.0b3 ([#1822](link)) - @hallvictoria
* Update azurefunctions-extensions-blob version to 1.1.2 ([#1821](link)) - @hallvictoria
```

**Excluded PRs:**
- #1755 and #1798 (older `azure-functions` versions)
- #1762 (older `azurefunctions-extensions-blob` version)

**Why?** Only the final version matters in release notes. Including all intermediate version bumps creates noise without adding value.

**Important:** Deduplication only applies to version updates. Other build PRs (e.g., "Use official grpc for python 3.14") are kept regardless of duplicates.
