# rust_worker

Rust transport shell for the Azure Functions Python worker. It owns
the gRPC `EventStream` (tonic) and embeds CPython (PyO3), delegating actual
function execution to the existing **v2 Python runtime** (`azure_functions_runtime`)
via a thin Python bridge.

See `docs/rustworker/design.md` for the full architecture, ROI analysis, and
file-by-file reference.

## Layout

```
rust_worker/
├── Cargo.toml
├── Cargo.lock
├── build.rs           # compiles the vendored .proto set (prost + tonic client)
├── gen_protos.py      # materializes bridge/protos from version-correct *_pb2 stubs
├── .gitignore
├── README.md
├── proto/             # vendored FunctionRpc.proto + deps (no system protoc needed)
├── src/
│   ├── main.rs        # entrypoint: args, embed CPython, dial Host, EventStream pump
│   ├── codec.rs       # raw-bytes tonic Codec for the control path
│   ├── pb.rs          # includes the generated prost types
│   ├── convert.rs     # prost <-> Python "datum tuple" conversion (native path)
│   ├── log.rs         # console logging matching the Python proxy worker format
│   └── bridge.rs      # PyO3 FFI: configure / start_stream / handle / invoke / shutdown
├── bridge/
│   ├── bridge.py      # protobuf + routing + persistent asyncio loop -> v2 runtime
│   └── protos/        # private gRPC-free protobuf messages (stubs populated at build)
└── gen_protos.py      # materializes bridge/protos from version-correct stubs
```

End-to-end tests reuse the shared `WebHostTestCase` harness and the **whole
`workers/tests/endtoend` suite** (the same function apps that validate the
classic Python worker) run against the real Host. There is no bespoke Rust test
app: the harness selects the Rust worker via `PYAZURE_WORKER_DIR`, and on Python
3.15+ it defaults to the staged Rust worker automatically.

## Build & run

Create a local Python 3.14 virtual environment first; do not assume a repo-level
venv already exists.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
$py = '.venv\Scripts\python.exe'

# install runtime + transport deps into the interpreter (one-time)
& $py -m pip install --only-binary=:all: 'grpcio>=1.75.1' 'protobuf>=5.29,<7'
& $py -m pip install -e ..\..\runtimes\v2

# build against that interpreter
$env:PYO3_PYTHON = $py
cargo build
```

On Linux/macOS, use `python3.14 -m venv .venv`, activate with
`source .venv/bin/activate`, then use `python` in place of `$py`.

The compiled binary is named `rust_worker` (for example,
`target\release\rust_worker` after `cargo build --release`).

## End-to-end tests

The Rust worker is validated end-to-end through the real Azure Functions Host,
reusing the shared `WebHostTestCase` harness and the full endtoend function-app
suite in `workers/tests/endtoend`. The harness stages the Rust worker (in place
of the Python `worker.py`) and selects it via `PYAZURE_WORKER_DIR`; on Python
3.15+ it is the default worker. Suites that need external services (e.g. SQL,
Event Grid) or app-specific third-party wheels skip or require configured
connection strings (`.testconfig`); the runner passes
`--continue-on-collection-errors` so they do not abort the run.

This flow runs in CI via `eng/ci/rust-worker-e2e.yml`.

## Notes

- Build-time: `PYO3_PYTHON` must point at the target interpreter.
- Runtime: the embedded interpreter needs `python3xx.dll` on `PATH` and the
  runtime/SDK packages on `PYTHONPATH` (the stub host wires both up). Editable
  installs must expose their **source dir** on `PYTHONPATH` (`.pth` hooks are not
  honored for `PYTHONPATH` entries).
- Docker image assets and k6 perf scripts moved out of this folder to
  `_rust_worker_extras/docker` and `_rust_worker_extras/perf`.
