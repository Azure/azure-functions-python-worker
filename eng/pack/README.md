# Python BYOC packaging

Package existing **Python 3.13, 3.14, or 3.15 Linux x64** worker staging trees
into separate archives. The standard-library helper runs cross-platform; the
payload must still be built for the selected Linux x64 target. All targets use
`worker.py` as the entrypoint and the existing worker version without a version
bump.

The shared space-separated `BYOCPythonVersions` variable in
`eng\templates\utils\byoc-variables.yml`, imported by
`eng\ci\official-build.yml` and `eng\ci\worker-release.yml`, defines the pipeline
targets. Its current value is `3.13 3.14 3.15`; it controls staged artifact
downloads, packaging, and expected release assets.

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

The helper accepts numeric `major.minor` versions without a fixed allowlist.
It selects the native R2P2 layout for version tuples greater than or equal to
`(3, 15)`, and the proxy layout otherwise, while still requiring matching
staged files, extension ABI names, and Linux x64 ELF headers. Accepting a
version is not evidence that its worker can be built or run. In particular,
this does not establish support for real Python 3.11/3.12 classic-worker
artifacts or verify future runtime builds; other versions require a matching
staged layout and separate runtime validation.

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
output directory because their Python-qualified filenames differ. Use separate
output directories for different worker release versions: packaging the same
Python target into the same directory produces colliding filenames.

The version comes from `workers\proxy_worker\version.py` for **all**
targets, not from a separate BYOC version; packaging does not bump it. A proxy
stage's version must match that source file. The native R2P2 payload has no proxy
version file; its source and build provenance must be checked separately.

Outputs retain the Python ABI and platform qualifiers, but not the worker
release version:

```text
azure-functions-python-worker-py313-linux-x64.tar.gz
azure-functions-python-worker-py314-linux-x64.tar.gz
azure-functions-python-worker-py315-linux-x64.tar.gz
```

Each archive has a same-name `.sha256` sidecar. Verify it before extraction,
running checksum verification from the directory containing the archives and
sidecars so the filenames recorded in the sidecars resolve directly. SHA-256
checksums validate integrity, not publisher authenticity. Extract different
targets to separate directories. The worker release version remains in
`worker-manifest.json` and the GitHub release tag.

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

`python_version` records the selected target, currently `3.13`, `3.14`, or `3.15`
in the pipelines.
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

## Proxy worker startup contract

This contract applies only to `proxy_worker`, not to every Python worker generation.
The host can supply these startup arguments:

```text
--functions-uri http://127.0.0.1:5001
--functions-worker-id worker-id
--functions-request-id request-id
--functions-grpc-max-message-length 4194304
```

Each provided `--functions-*` field takes precedence over its legacy equivalent.
An invalid explicitly provided `--functions-uri` is rejected, not replaced by
legacy host and port values. Omitted fields fall back independently:

| Argument | Legacy fallback |
|----------|-----------------|
| `--functions-uri` | `--host` and `--port` |
| `--functions-worker-id` | `--workerId` |
| `--functions-request-id` | `--requestId` |
| `--functions-grpc-max-message-length` | `--grpcMaxMessageLength` |

The URI is normalized to a host and port for the gRPC connection. It must use
`http` with a nonempty hostname and an explicit port.
Bracketed IPv6 addresses such as `http://[::1]:5001` are supported. An optional
root slash is allowed, but credentials, other paths, queries, and fragments are
not. The connection uses insecure gRPC; `https` and TLS are not supported by this
contract. Legacy-only startup remains supported.

The maximum message length is in bytes; `-1` means unlimited.
If neither argument supplies it, the default is `-1`. The limit applies to both
gRPC send and receive messages.

## Official CI packaging

The official `PackageBYOC` job, defined in
`eng\templates\official\jobs\package-byoc.yml`, depends on `Build_LINUX_X64` and
`Build_R2P2_LINUX_X64`. For each target in `BYOCPythonVersions`, it downloads the
matching staged artifact, currently `3.13_LINUX_X64`, `3.14_LINUX_X64`, and
`3.15_LINUX_X64` into separate `byoc-worker/<version>` staging directories,
then invokes the helper in **Package Python BYOC workers** with a shared output
directory. The single `PythonWorkerBYOC` artifact contains all configured
Python-qualified archives and their SHA-256 sidecars. Existing NuGet outputs
are unchanged. This packaging job adds no unit-test CI step.

## Worker release assets

For each worker NuGet release (`WorkerRelease=true`), `PublishBYOCAssets` runs
after `PublishNuget` succeeds. It downloads `PythonWorkerBYOC` from the
exact same official source build used for the NuGet packages, without rebuilding
or independently selecting a latest build. Before continuing the release,
verify that both `PackageWorkers` and `PackageBYOC` have completed.

The **Attach Python archives and checksums** step validates the expected files
for every target in `BYOCPythonVersions`: currently these six Python-qualified
files, without the worker release version in their names:

```text
azure-functions-python-worker-py313-linux-x64.tar.gz
azure-functions-python-worker-py313-linux-x64.tar.gz.sha256
azure-functions-python-worker-py314-linux-x64.tar.gz
azure-functions-python-worker-py314-linux-x64.tar.gz.sha256
azure-functions-python-worker-py315-linux-x64.tar.gz
azure-functions-python-worker-py315-linux-x64.tar.gz.sha256
```

It uploads them to the existing GitHub release for
`NewWorkerVersion`, reusing `GithubPat`, which needs repository contents write
permission. It does not create a tag or release, change draft status, or bypass manual release-note
approval and GitHub publishing. Existing NuGet and Host PR steps are unchanged.
BYOC packaging still runs on other official builds, but GitHub asset upload is
limited to worker NuGet releases, not runtime v1/v2 PyPI releases.

Missing artifacts, a missing GitHub release, or upload failures fail the job.
Existing assets are not overwritten. After a partial upload, retrying may
require manually removing only conflicting BYOC assets; do not delete the
release or unrelated assets. This naming change applies to future packaging;
historical release assets and their existing download links are unchanged.
This describes the release workflow, not evidence
of a completed live CI run or publication.

## Validation limits

Structural checks alone **do not prove loading, ABI compatibility,
Host/WorkerProxy integration, or invocation**. Verify the extracted payload in
the intended Linux x64 environment with matching native dependencies, including
the Python shared library required by R2P2. Compatibility with other base
images, libc implementations, architectures, or Python versions is not implied.
This guide describes the packaging contract, not evidence of a completed CI run
or deployment, and provides no production support or servicing guarantees.
