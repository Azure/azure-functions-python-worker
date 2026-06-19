# `_vendored`

This directory holds a private copy of `google.protobuf` that the worker
falls back to when the function app ships its own `google.protobuf`.

## Why we vendor

The worker uses generated `*_pb2.py` protobuf stubs that, starting with
`protobuf >= 5.27`, import symbols such as `runtime_version` from
`google.protobuf`. If a customer pins an older `protobuf` (for example,
4.x) in their `.python_packages`, the customer's copy of
`google.protobuf` shadows the worker's expected version on `sys.path`
and the worker fails to start with `ImportError`.

To prevent that, when the worker detects the customer ships
`google.protobuf`, it pre-imports this vendored copy and registers it
in `sys.modules` under the top-level `google.protobuf` names. The
worker's pb2 stubs (which use ordinary `from google.protobuf import X`
imports) then resolve to the vendored copy, and the customer's pinned
version doesn't interfere with the worker.

When the customer does **not** ship `google.protobuf`, this vendored
tree is not used at all — the worker's pb2 stubs resolve to the
protobuf install that ships with the worker runtime, which uses the
fast `upb` C extension natively. Most function apps fall in this
branch and pay no runtime cost for vendoring.

The selection happens once at worker startup in
`azure_functions_worker/__init__.py`. See `_should_use_vendored_protobuf()`
there.

## Local development always uses the vendored copy

When the worker runs locally (not in an Azure environment), the
launcher (`workers/python/prodV4/worker.py`,
`workers/python/test/worker.py`) sets
`_AZFUNC_USE_VENDORED_PROTOBUF=1` before importing
`azure_functions_worker`, which unconditionally activates the vendored
fallback. This keeps the local dev experience aligned with the
customer-ships-protobuf production path and isolates the worker from
whatever `protobuf` happens to be installed in the developer's venv.
The pure-Python perf cost only matters in production.

## Pure-Python only

The vendored copy is shipped as pure Python — no native extensions are
copied. When it is activated, the worker also sets
`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` so the vendored
`api_implementation` doesn't try to load a `_upb._message` C extension
(loading one alongside the customer's own `_upb` instance is unsafe).
This pure-Python mode is slower than `upb` on the gRPC hot path, but
the cost is only paid by function apps that actually ship protobuf.

## How it is populated

This directory is **empty in source control** (only this `README.md` and
`.gitignore` are committed). The actual vendored package is produced at
build time by:

```
python eng/scripts/vendor_deps.py --target workers/azure_functions_worker/_vendored
```

That script:

1. Copies the source of `google.protobuf` from the active Python
   environment into this directory. Native extensions are skipped.
2. Rewrites every absolute import inside the copied files from
   `google.protobuf...` to
   `azure_functions_worker._vendored.google.protobuf...` so the
   vendored copy is self-contained.
3. Writes a top-level `google/__init__.py` so the `google` segment is a
   regular package (rather than a namespace package) under `_vendored`.

`invoke build-protos` calls this script automatically before
regenerating the `*_pb2.py` stubs, and the pack pipeline
(`eng/pack/scripts/*`) copies the result into the published artifact
under `deps/azure_functions_worker/_vendored/`.

## Do not edit by hand

Any file under `google/` is regenerated on every build. Edits made
directly to those files will be overwritten. Changes that affect
vendoring belong in `eng/scripts/vendor_deps.py`.
