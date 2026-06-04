# `_vendored`

This directory holds third-party Python packages that are vendored into the
Azure Functions Python worker so the worker is isolated from versions a
customer ships in their own `requirements.txt`.

## Why we vendor

The worker uses generated `*_pb2.py` protobuf stubs that, starting with
`protobuf >= 5.27`, import symbols such as `runtime_version` from
`google.protobuf`. If a customer pins an older `protobuf` (for example, 4.x),
the customer's copy of `google.protobuf` shadows the worker's expected
version and the worker fails to start with `ImportError`.

To prevent that, the worker imports protobuf from
`azure_functions_worker._vendored.google.protobuf` instead of the top-level
`google.protobuf`. The customer's `protobuf` package is still installed
alongside the worker but never used by worker code.

## How it is populated

This directory is **empty in source control** (only this `README.md` and
`.gitignore` are committed). The actual vendored packages are produced at
build time by:

```
python eng/scripts/vendor_deps.py --target workers/azure_functions_worker/_vendored
```

That script:

1. Copies the source of each vendored package (currently `google.protobuf`)
   from the active Python environment into this directory.
2. Rewrites every absolute import inside the copied files from
   `google.protobuf...` to `azure_functions_worker._vendored.google.protobuf...`
   so the vendored copy is fully self-contained.
3. Writes a top-level `google/__init__.py` so the `google` segment is a
   regular package (rather than a namespace package) under `_vendored`.

`invoke build-protos` calls this script automatically before regenerating the
`*_pb2.py` stubs, and the pack pipeline (`eng/pack/scripts/*`) copies the
result into the published artifact under
`deps/azure_functions_worker/_vendored/`.

## Do not edit by hand

Any file under `google/` is regenerated on every build. Edits made directly
to those files will be overwritten. Changes that affect vendoring belong in
`eng/scripts/vendor_deps.py`.

## Pure-Python protobuf

The worker forces the pure-Python protobuf implementation by setting
`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` in
`azure_functions_worker/__init__.py`. This avoids the need to vendor the
protobuf C extension across the full Python × OS × architecture matrix.
