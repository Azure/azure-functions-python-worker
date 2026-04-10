## Docs Freshness Review

This is an automated monthly review triggered by the scheduled workflow.

### Instructions

Please read `.github/copilot/skills/docs-freshness.md` and follow the workflow documented there. Open a **draft PR** with any necessary documentation updates.

### Known Source of Truth Files

These files are the source of truth for versioning and configuration:

- `workers/pyproject.toml`
- `eng/ci/public-build.yml`
- `workers/azure_functions_worker/version.py`

### Target Documentation Files

Review the following documentation files for freshness:

- `README.md`
- `workers/README.md`
- `runtimes/v1/README.md`
- `runtimes/v2/README.md`
- `docs/*.rst`
