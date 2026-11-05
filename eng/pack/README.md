# Python BYOC packaging prototype

Package existing **Python 3.13, 3.14, or 3.15 Linux x64** worker staging trees
into separate archives. The standard-library helper runs cross-platform; the
payload must still be built for the selected Linux x64 target. Python 3.11 and
3.12 are not implemented by this prototype.

## Obtain the matching staged worker

Use the extracted flat staging directory containing `worker.py`, not its parent.
Do not substitute a different Python version's stage.

| Target | Source | Payload |
|--------|--------|---------|
| 3.13 | `3.13_LINUX_X64` from the worker build | Repository proxy worker and matching CPython 3.13 dependencies |
| 3.14 | `3.14_LINUX_X64` from the worker build | Repository proxy worker and matching CPython 3.14 dependencies |
| 3.15 | Official `3.15_LINUX_X64` R2P2 worker build artifact | Native `r2p2`, existing `worker.py`, bridge, and runtime packages |

The proxy staging process uses `eng\pack\templates\nix_env_gen.yml`. The 3.15
source must be the native R2P2 artifact, not a proxy-worker stage or a hand-made
launcher. It contains neither `proxy_worker`, `grpc`, nor `uvloop`.

## Package locally

Run from the repository root. The interpreter running the helper does not
select the payload version: `--python-version` does, defaulting to `3.14`.

```powershell
python eng\pack\scripts\package_byoc.py --help
python eng\pack\scripts\package_byoc.py --python-version 3.13 --source "C:\staging\3.13_LINUX_X64" --output "C:\artifacts\byoc"
python eng\pack\scripts\package_byoc.py --python-version 3.14 --source "C:\staging\3.14_LINUX_X64" --output "C:\artifacts\byoc"
python eng\pack\scripts\package_byoc.py --python-version 3.15 --source "C:\staging\3.15_LINUX_X64" --output "C:\artifacts\byoc"
```

These are placeholder paths and illustrative packaging commands, not evidence
of actual builds. Replace them with downloaded staging and output directories.
Output must be outside the source tree. All three invocations can share an
output directory because their filenames differ.

The version comes from `workers\proxy_worker\version.py` for **all three**
targets, not from a separate BYOC version; packaging does not bump it. A proxy
stage's version must match that source file. The native R2P2 payload has no proxy
version file; its source and build provenance must be checked separately.

For version `<VERSION>`, outputs are:

```text
azure-functions-python-worker-<VERSION>-py313-linux-x64.tar.gz
azure-functions-python-worker-<VERSION>-py314-linux-x64.tar.gz
azure-functions-python-worker-<VERSION>-py315-linux-x64.tar.gz
```

Each archive has a same-name `.sha256` sidecar. Verify it before extraction;
extract different targets to separate directories.

## Archive and launch contract

Extraction places the staged payload directly at the destination root, plus
`LICENSE` from the repository root and `worker-manifest.json`.

For 3.13 and 3.14, the payload includes `worker.py`, `proxy_worker`, both runtime
packages, and bundled dependencies including matching grpc and uvloop extensions.
For 3.15, it includes `worker.py`, executable `r2p2`, `bridge`, and both runtime
packages, without proxy-worker/grpc/uvloop components.

The public entrypoint remains **`worker.py` for every target**. For 3.15, the
repository's existing `workers\python\r2p2\worker.py` shim replaces itself with
the sibling `r2p2` executable and forwards arguments unchanged. Packaging adds
no custom startup wrapper.

The generated manifest has exactly these five fields:

```json
{
  "name": "azure-functions-python-worker",
  "version": "<VERSION>",
  "python_version": "3.15",
  "platform": "linux-x64",
  "entrypoint": "worker.py"
}
```

`python_version` is `3.13`, `3.14`, or `3.15` according to the selected target.
The native 3.15 binary embeds matching CPython; the matching runtime Python
shared library must also be available in the execution environment. Launching
the shim still requires a Python interpreter. Header checks do not establish
that these runtime requirements are satisfied.

The helper validates required files and directories, proxy version equality,
matching proxy extension ABI names, and Linux x64 ELF headers. For R2P2 it
checks the executable header, bridge/runtime layout, and absence of forbidden
proxy components. It rejects symlinks and output inside the source, excludes
`.artifactignore` and bytecode, and normalizes archive metadata and gzip time
for reproducible output.

## Official CI packaging

The official `PackageBYOCPrototype` job depends on `Build_LINUX_X64` and
`Build_R2P2_LINUX_X64`. It downloads `3.13_LINUX_X64`, `3.14_LINUX_X64`, and
`3.15_LINUX_X64` into separate `byoc-worker/<version>` staging directories,
then invokes the helper for each target with a shared output directory.
The single `PythonWorkerBYOCPrototype` artifact contains all three
version-qualified archives and their SHA-256 sidecars. Existing NuGet outputs
are unchanged. This packaging job adds no unit-test CI step.

## Worker release assets

For each worker NuGet release (`WorkerRelease=true`), `PublishBYOCAssets` runs
after `PublishNuget` succeeds. It downloads `PythonWorkerBYOCPrototype` from the
exact same official source build used for the NuGet packages, without rebuilding
or independently selecting a latest build. Before continuing the release,
verify that both `PackageWorkers` and `PackageBYOCPrototype` have completed.

The job validates all six expected files: the Python 3.13, 3.14, and 3.15 Linux
x64 archives and their SHA-256 sidecars, all named with the worker release
version. It uploads them to the existing GitHub release for `NewWorkerVersion`,
reusing `GithubPat`, which needs repository contents write permission. It does
not create a tag or release, change draft status, or bypass manual release-note
approval and GitHub publishing. Existing NuGet and Host PR steps are unchanged.
BYOC packaging still runs on other official builds, but GitHub asset upload is
limited to worker NuGet releases, not runtime v1/v2 PyPI releases.

Missing artifacts, a missing GitHub release, or upload failures fail the job.
Existing assets are not overwritten. After a partial upload, retrying may
require manually removing only conflicting BYOC assets; do not delete the
release or unrelated assets. This describes the release workflow, not evidence
of a completed live CI run or publication.

## Validation limits

Structural checks alone **do not prove loading, ABI compatibility,
Host/WorkerProxy integration, or invocation**. Verify the extracted payload in
the intended Linux x64 environment with matching native dependencies, including
the Python shared library required by R2P2. Compatibility with other base
images, libc implementations, architectures, or Python versions is not implied.
This guide describes the packaging contract, not evidence of a completed CI run
or deployment, and provides no production support or servicing guarantees.
