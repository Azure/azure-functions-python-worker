# `_vendored/` — private third-party copies

This directory is **populated at build time** by
[`eng/scripts/vendor_deps.py`](../../../../eng/scripts/vendor_deps.py).
Only `__init__.py`, `README.md`, and `.gitignore` are committed.

## Why

Customer Azure Functions apps on Linux Dedicated have their
`.python_packages` directory placed **before** the worker's dependency
directory on `sys.path`. When a customer pins an older `protobuf` (e.g.
`protobuf==4.25.3`) and the worker ships with a newer `protobuf` (e.g.
`5.29.x` required for CVE remediation), the worker's generated
`*_pb2.py` files load the customer's older `google.protobuf` and fail
with errors such as:

```
ImportError: cannot import name 'runtime_version' from 'google.protobuf'
```

Vendoring `google.protobuf` under a private namespace
(`azure_functions_worker._vendored.google.protobuf`) makes the worker's
proto stubs resolve **only** to the worker's own copy, regardless of
what the customer has installed. The customer's `google.protobuf`
continues to work unchanged for their code.

## How it's wired

* Build pipeline runs `python eng/scripts/vendor_deps.py --target
  workers/azure_functions_worker/_vendored` after `pip install`.
* The script copies `google.protobuf` (pure-Python files only) into
  `_vendored/google/protobuf/` and rewrites every internal
  `from google.protobuf` / `import google.protobuf` reference to point
  at `azure_functions_worker._vendored.google.protobuf`.
* `workers/tests/test_setup.py::make_absolute_imports` rewrites the
  worker's generated `*_pb2.py` / `*_pb2_grpc.py` files to import
  protobuf from `_vendored` as well.
* `_vendored/__init__.py` forces the pure-Python protobuf
  implementation (`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`) so
  the C extension does not need to be vendored.

## Adding more vendored packages

The script accepts repeated `--package` arguments. To vendor an
additional pure-Python package, extend `vendor_deps.py`'s default list
or pass `--package <name>` from the build pipeline. The rewriter is
generic over top-level package names.
