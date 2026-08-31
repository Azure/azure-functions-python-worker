# R2P2 (Rust to Python Proxy)

R2P2 is the Rust transport shell for the Azure Functions Python worker. It owns
the gRPC `EventStream` (tonic) and embeds CPython (PyO3), delegating actual
function execution to the existing **v2 Python runtime** (`azure_functions_runtime`)
via a thin Python bridge.

See `docs/r2p2/design.md` for the full architecture, ROI analysis, and
file-by-file reference.

## Layout

```
r2p2/
├── Cargo.toml
├── Cargo.lock
├── build.rs           # compiles the vendored .proto set (prost + tonic client)
├── .gitignore
├── README.md
├── proto/             # vendored FunctionRpc.proto + deps (no system protoc needed)
├── src/
│   ├── main.rs        # entrypoint: args, embed CPython, dial Host, EventStream pump
│   ├── codec.rs       # raw-bytes tonic Codec for the control path
│   ├── pb.rs          # includes the generated prost types
│   ├── control.rs     # prost <-> Python control-plane + invocation-control codec
│   ├── convert.rs     # prost <-> Python "datum tuple" conversion (native path)
│   ├── log.rs         # console logging matching the Python proxy worker format
│   └── bridge.rs      # PyO3 FFI: configure / start_stream / handle / invoke / shutdown
├── bridge/
│   ├── bridge.py         # prost-driven control routing (protobuf-free) -> v2/v1 runtime
│   └── protos_adapter.py # pure-Python, protobuf-free `protos` stand-in for the runtime
```

End-to-end tests reuse the shared `WebHostTestCase` harness and the **whole
`workers/tests/endtoend` suite** (the same function apps that validate the
classic Python worker) run against the real Host. There is no bespoke Rust test
app: the harness selects the R2P2 via `PYAZURE_WORKER_DIR`, and on Python
3.15+ it defaults to the staged R2P2 automatically.

## Build & run

Create a local Python 3.15 virtual environment first; do not assume a repo-level
venv already exists.

```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\Activate.ps1
$py = '.venv\Scripts\python.exe'

# install the v2 runtime into the interpreter (one-time). The bridge is
# protobuf-free -- Rust/prost owns the wire -- so no grpcio/protobuf needed.
& $py -m pip install -e ..\..\runtimes\v2

# build against that interpreter
$env:PYO3_PYTHON = $py
cargo build
```

On Linux/macOS, use `python3.15 -m venv .venv`, activate with
`source .venv/bin/activate`, then use `python` in place of `$py`.

The compiled binary is named `r2p2` (for example,
`target\release\r2p2` after `cargo build --release`).

## End-to-end tests

The R2P2 is validated end-to-end through the real Azure Functions Host,
reusing the shared `WebHostTestCase` harness and the full endtoend function-app
suite in `workers/tests/endtoend`. The harness stages the R2P2 (in place
of the Python `worker.py`) and selects it via `PYAZURE_WORKER_DIR`; on Python
3.15+ it is the default worker. Suites that need external services (e.g. SQL,
Event Grid) or app-specific third-party wheels skip or require configured
connection strings (`.testconfig`); the runner passes
`--continue-on-collection-errors` so they do not abort the run.

This flow runs in CI via `eng/ci/r2p2-e2e.yml`.

## Notes

- Build-time: `PYO3_PYTHON` must point at the target interpreter.
- Runtime: the embedded interpreter needs `python3xx.dll` on `PATH` and the
  runtime/SDK packages on `PYTHONPATH` (the stub host wires both up). Editable
  installs must expose their **source dir** on `PYTHONPATH` (`.pth` hooks are not
  honored for `PYTHONPATH` entries).
- Docker image assets and k6 perf scripts moved out of this folder to
  `_r2p2_extras/docker` and `_r2p2_extras/perf`.
