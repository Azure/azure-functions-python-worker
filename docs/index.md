# Azure Functions Python Runtime — Engineering & Architecture

Welcome to the engineering documentation for the **Azure Functions Python Worker & Runtime**.

While preserving the exact same `FunctionRpc.proto` Host contract and customer-facing `azure-functions` programming models (V1 `function.json` and V2 `@app` decorators), the Python worker architecture has evolved across three distinct generations:

| Generation | Python Versions | Worker Shell | Execution Engine | Architecture Guide |
| --- | --- | --- | --- | --- |
| **Generation 1 — Monolith** | `3.7 – 3.12` | `workers/azure_functions_worker` (`prodV4/worker.py`) | Bundled inside monolith | [Python ≤ 3.12 Architecture](architecture/python-312.md) |
| **Generation 2 — Proxy Split** | `3.13 – 3.14` | `workers/proxy_worker` (`proxyV4/worker.py`) | `runtimes/v2`, `runtimes/v1`, or Custom Agent Runtime | [Python 3.13 – 3.14 Architecture](architecture/python-313-314.md) |
| **Generation 3 — R2P2 (Rust)** | `3.15+` (GIL) | `workers/r2p2` (`tonic` + `prost` + `PyO3`) | Embedded CPython + `runtimes/v2` / `v1` (`native_invocation.py`) | [Python 3.15+ (R2P2) Architecture](architecture/python-315-r2p2.md) |

---

## Interactive R2P2 Architecture Preview (Python 3.15+)

Use the interactive explorer below to step through all **7 lifecycle phases** (`Worker Init`, `Specialization`, `Metadata`, `Functions Load`, `Invocation`, `Worker Status`, and `Worker Logs`), inspect extracted AST/Rust symbols, or click **⛶ Expand** for fullscreen mode. Every page in this site also preserves full static Markdown narratives and native `mermaid` diagrams in Git.

<div class="arch-atlas-mount" data-era="py315_r2p2" data-phase="invocation"></div>

---

## Documentation Map

- **[Evolution Overview](architecture/overview.md)** — Side-by-side architectural matrix, performance benchmarks, and design trade-offs across `≤ 3.12`, `3.13–3.14`, and `3.15+`.
- **[5-Repository Ecosystem](architecture/ecosystem.md)** — How `azure-functions-host`, `azure-functions-language-worker-protobuf`, `azure-functions-python-worker`, `azure-functions-python-library`, and `azure-functions-python-extensions` fit together.
- **[Python ≤ 3.12 (Monolith)](architecture/python-312.md)** — Single-package `grpcio` + `google.protobuf` worker and its 7 lifecycle flows.
- **[Python 3.13 – 3.14 (Proxy Split)](architecture/python-313-314.md)** — Decoupled `proxy_worker` transport shell, `WorkerRequest` seam, `protos` injection, and pluggable PyPI runtimes.
- **[Python 3.15+ (R2P2 Rust Worker)](architecture/python-315-r2p2.md)** — Native Rust `tonic`/`prost` transport, `PyO3` embedded CPython (GIL), hot `Datum` tuple FFI, and zero-protobuf `protos_adapter.py`.
- **[Dependency Isolation](architecture/dependency-isolation.md)** — Placeholder specialization, `sys.path` ordering, and PEP 420 namespace-safe module eviction.
