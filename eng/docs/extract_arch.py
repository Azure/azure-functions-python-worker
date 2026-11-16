#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Multi-Repository Code-to-Architecture Graph Extractor for Azure Functions Python.

Synthesizes live AST/Rust/Proto facts from `Azure/azure-functions-python-worker`
and cross-links the 4-repository Python Functions runtime ecosystem:
  1. Azure/azure-functions-python-worker           (workers + runtimes v1/v2)
  2. Azure/azure-functions-python-library          (azure-functions PyPI SDK)
  3. Azure/azure-functions-python-extensions       (HTTP v2, SdkType deferred bindings, Agent runtimes)
  4. Azure/azure-functions-language-worker-protobuf (FunctionRpc.proto + settlement.proto)

Outputs:
  - site/assets/architecture-graph.json (machine-readable graph + drift fingerprint)
  - site/assets/architecture-data.js    (zero-fetch bundle for local preview & GitHub Pages)
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from phases_spec import (
    PHASE_CATALOG,
    get_py312_phases,
    get_py313_phases,
    get_py315_phases,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_OUT = REPO_ROOT / "docs" / "site" / "assets" / "architecture-graph.json"
JS_OUT = REPO_ROOT / "docs" / "site" / "assets" / "architecture-data.js"

REPOS: dict[str, dict[str, Any]] = {
    "python-worker": {
        "id": "python-worker",
        "fullName": "Azure/azure-functions-python-worker",
        "shortName": "python-worker",
        "url": "https://github.com/Azure/azure-functions-python-worker",
        "defaultBranch": "dev",
        "color": "#38bdf8",
        "pypi": ["azure-functions-runtime", "azure-functions-runtime-v1"],
        "role": "Worker transports (monolith, proxy_worker, R2P2 Rust) and v1/v2 execution runtimes.",
    },
    "python-library": {
        "id": "python-library",
        "fullName": "Azure/azure-functions-python-library",
        "shortName": "python-library",
        "url": "https://github.com/Azure/azure-functions-python-library",
        "defaultBranch": "dev",
        "color": "#34d399",
        "pypi": ["azure-functions"],
        "role": "Customer-facing Python SDK: V2 @app decorators, Blueprints, Datum converters, Trigger/Binding types, Out[T], Context.",
    },
    "python-extensions": {
        "id": "python-extensions",
        "fullName": "Azure/azure-functions-python-extensions",
        "shortName": "python-extensions",
        "url": "https://github.com/Azure/azure-functions-python-extensions",
        "defaultBranch": "dev",
        "color": "#c084fc",
        "pypi": [
            "azurefunctions-extensions-base",
            "azurefunctions-extensions-http-fastapi",
            "azurefunctions-extensions-bindings-blob",
            "azurefunctions-extensions-bindings-servicebus",
            "azurefunctions-agents-extensions-*",
        ],
        "role": "Extension contracts: WebApp HTTP v2 streaming, SdkType deferred bindings, Settlement gRPC client, and Custom/Agent Runtime hooks.",
    },
    "language-worker-protobuf": {
        "id": "language-worker-protobuf",
        "fullName": "Azure/azure-functions-language-worker-protobuf",
        "shortName": "worker-protobuf",
        "url": "https://github.com/Azure/azure-functions-language-worker-protobuf",
        "defaultBranch": "dev",
        "color": "#fbbf24",
        "pypi": [],
        "role": "Canonical gRPC wire schema (`FunctionRpc.proto`, `settlement.proto`, `ClaimsIdentityRpc.proto`) shared by Host and all language workers.",
    },
}


def git_info(repo_dir: Path = REPO_ROOT) -> dict[str, str]:
    def run(args: list[str], default: str = "") -> str:
        try:
            return subprocess.check_output(
                ["git", *args], cwd=repo_dir, stderr=subprocess.DEVNULL, text=True
            ).strip()
        except Exception:
            return default

    return {
        "sha": run(["rev-parse", "HEAD"], "dev"),
        "shortSha": run(["rev-parse", "--short", "HEAD"], "dev"),
        "branch": run(["rev-parse", "--abbrev-ref", "HEAD"], "dev"),
        "subject": run(["log", "-1", "--pretty=%s"], ""),
        "committedAt": run(["log", "-1", "--pretty=%cI"], ""),
    }


def extract_python_file(rel_path: str, base_dir: Path = REPO_ROOT) -> dict[str, Any]:
    full = base_dir / rel_path
    if not full.exists():
        return {
            "path": rel_path,
            "exists": False,
            "lines": 0,
            "symbols": [],
            "symbolLines": {},
            "routerCases": [],
        }

    src = full.read_text(encoding="utf-8", errors="replace")
    lines = src.count("\n") + 1
    symbols: list[dict[str, Any]] = []
    symbol_lines: dict[str, int] = {}
    match_cases: list[str] = []

    try:
        tree = ast.parse(src, filename=rel_path)
        doc = ast.get_docstring(tree) or ""
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol_lines.setdefault(node.name, node.lineno)
                args = [a.arg for a in node.args.args if a.arg != "self"]
                symbols.append({
                    "name": node.name,
                    "kind": "async def" if isinstance(node, ast.AsyncFunctionDef) else "def",
                    "line": node.lineno,
                    "signature": f"{node.name}({', '.join(args[:4])}{', ...' if len(args) > 4 else ''})",
                })
            elif isinstance(node, ast.ClassDef):
                symbol_lines.setdefault(node.name, node.lineno)
                methods: list[str] = []
                for n in node.body:
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbol_lines[f"{node.name}.{n.name}"] = n.lineno
                        symbol_lines.setdefault(n.name, n.lineno)
                        if not n.name.startswith("__"):
                            methods.append(n.name)
                symbols.append({
                    "name": node.name,
                    "kind": "class",
                    "line": node.lineno,
                    "signature": f"class {node.name}",
                    "methods": methods[:6],
                })
        for node in ast.walk(tree):
            if isinstance(node, ast.Match):
                for case in node.cases:
                    if isinstance(case.pattern, ast.MatchValue) and isinstance(case.pattern.value, ast.Constant):
                        val = str(case.pattern.value.value)
                        if val.endswith("_request") or val.endswith("_response"):
                            match_cases.append(val)
    except SyntaxError:
        doc = ""

    return {
        "path": rel_path,
        "exists": True,
        "lines": lines,
        "docSummary": doc.strip().splitlines()[0] if doc.strip() else "",
        "symbols": symbols,
        "symbolLines": symbol_lines,
        "routerCases": sorted(set(match_cases)),
    }


def extract_rust_file(rel_path: str) -> dict[str, Any]:
    full = REPO_ROOT / rel_path
    if not full.exists():
        return {
            "path": rel_path,
            "exists": False,
            "lines": 0,
            "symbols": [],
            "symbolLines": {},
            "pyo3Calls": [],
        }

    src = full.read_text(encoding="utf-8", errors="replace")
    src_lines = src.splitlines()
    symbols: list[dict[str, Any]] = []
    symbol_lines: dict[str, int] = {}
    pyo3_calls: list[str] = []

    fn_re = re.compile(r"^\s*(pub(?:\(crate\))?\s+)?(async\s+)?fn\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)")
    struct_re = re.compile(r"^\s*(pub\s+)?(struct|enum)\s+([A-Za-z0-9_]+)")
    call_method_re = re.compile(r'call_method1\(\s*"([A-Za-z0-9_]+)"')

    for idx, line in enumerate(src_lines, start=1):
        m_fn = fn_re.match(line)
        if m_fn:
            is_pub, is_async, name, params = m_fn.groups()
            if name.startswith("test_"):
                continue
            symbol_lines.setdefault(name, idx)
            kind = f"{'pub ' if is_pub else ''}{'async ' if is_async else ''}fn".strip()
            short_params = ", ".join(
                p.strip().split(":")[0].strip() for p in params.split(",") if p.strip()
            )
            symbols.append({
                "name": name,
                "kind": kind,
                "line": idx,
                "signature": f"{name}({short_params})",
            })
            continue
        m_st = struct_re.match(line)
        if m_st:
            _, kw, name = m_st.groups()
            symbol_lines.setdefault(name, idx)
            symbols.append({"name": name, "kind": kw, "line": idx, "signature": name})

    for m in call_method_re.finditer(src):
        pyo3_calls.append(m.group(1))

    return {
        "path": rel_path,
        "exists": True,
        "lines": len(src_lines),
        "symbols": symbols,
        "symbolLines": symbol_lines,
        "pyo3Calls": sorted(set(pyo3_calls)),
    }


def extract_proto_messages(rel_path: str) -> list[dict[str, Any]]:
    full = REPO_ROOT / rel_path
    if not full.exists():
        return []
    src = full.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"message\s+StreamingMessage\s*\{(.*?)\n\}", src, flags=re.S)
    if not m:
        return []
    oneof = re.search(r"oneof\s+content\s*\{(.*?)\}", m.group(1), flags=re.S)
    if not oneof:
        return []
    fields = []
    for fm in re.finditer(r"^\s*([A-Za-z0-9_]+)\s+([a-z0-9_]+)\s*=\s*(\d+)\s*;", oneof.group(1), flags=re.M):
        msg_type, field_name, tag = fm.groups()
        fields.append({"type": msg_type, "field": field_name, "tag": int(tag)})
    return fields


def scan_package_files(rel_dir: str, suffixes: tuple[str, ...]) -> list[dict[str, Any]]:
    base = REPO_ROOT / rel_dir
    if not base.exists():
        return []
    out = []
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.suffix not in suffixes:
            continue
        rel = p.relative_to(REPO_ROOT).as_posix()
        if any(seg in rel for seg in ("/_thirdparty/", "/_vendored/", "/protos/", "__pycache__", "/target/")):
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        out.append({"path": rel, "lines": lines})
    return out


def sym_line(meta: dict[str, Any], name: str, fallback: int = 1) -> int:
    sym_map = meta.get("symbolLines", {})
    if name in sym_map:
        return sym_map[name]
    for s in meta.get("symbols", []):
        if s["name"] == name:
            return s["line"]
    return fallback


def compile_topology_mermaid(era: dict[str, Any], edges_override: list[dict[str, Any]] | None = None) -> str:
    lines = ["flowchart LR"]
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for c in era["containers"]:
        by_parent.setdefault(c.get("parentId"), []).append(c)
    nodes_by_c: dict[str, list[dict[str, Any]]] = {}
    for n in era["nodes"]:
        nodes_by_c.setdefault(n["containerId"], []).append(n)

    def emit(c: dict[str, Any], ind: str) -> None:
        cid = c["id"].replace("-", "_")
        lines.append(f'{ind}subgraph {cid}["{c["label"]}"]')
        for sub in by_parent.get(c["id"], []):
            emit(sub, ind + "  ")
        for n in nodes_by_c.get(c["id"], []):
            nid = n["id"].replace("-", "_")
            repo_short = REPOS.get(n["repo"], {}).get("shortName", n["repo"])
            lines.append(f'{ind}  {nid}["{n["label"]}<br/>({repo_short})"]')
        lines.append(f"{ind}end")

    for rc in by_parent.get(None, []):
        emit(rc, "  ")
    for e in (edges_override if edges_override is not None else era["edges"]):
        s = e["source"].replace("-", "_")
        t = e["target"].replace("-", "_")
        arr = "-.->" if e.get("dashed") else "-->"
        lines.append(f'  {s} {arr}|"{e["label"]}"| {t}')
    return "\n".join(lines)


def compile_sequence_mermaid(flow: dict[str, Any]) -> str:
    lines = ["sequenceDiagram"]
    for a in flow["actors"]:
        lines.append(f'  participant {a["id"].replace("-", "_")} as {a["label"]}')
    for st in flow["steps"]:
        fr = st["from"].replace("-", "_")
        to = st["to"].replace("-", "_")
        arr = "-->>" if st.get("isReturn") else "->>"
        lines.append(f'  {fr}{arr}{to}: {st["message"]}')
    return "\n".join(lines)


def resolve_github_url(node: dict[str, Any], repo_refs: dict[str, str]) -> str:
    repo_id = node["repo"]
    repo = REPOS[repo_id]
    ref = repo_refs.get(repo_id) or repo["defaultBranch"]
    line_sfx = f"#L{node['line']}" if node.get("line", 0) > 1 else ""
    return f"{repo['url']}/blob/{ref}/{node['file']}{line_sfx}"


def build_graph(sibling_root: Path | None = None) -> dict[str, Any]:
    git = git_info(REPO_ROOT)
    repo_dirs: dict[str, Path] = {"python-worker": REPO_ROOT}
    repo_refs: dict[str, str] = {
        "python-worker": git["sha"] if len(git["sha"]) >= 7 else "dev"
    }
    if sibling_root and sibling_root.exists():
        for rid in ("python-library", "python-extensions", "language-worker-protobuf"):
            cand = sibling_root / rid
            if cand.exists():
                repo_dirs[rid] = cand
                s_git = git_info(cand)
                if len(s_git["sha"]) >= 7:
                    repo_refs[rid] = s_git["sha"]

    py_paths = [
        "workers/python/prodV4/worker.py",
        "workers/python/proxyV4/worker.py",
        "workers/azure_functions_worker/main.py",
        "workers/azure_functions_worker/dispatcher.py",
        "workers/azure_functions_worker/loader.py",
        "workers/azure_functions_worker/http_v2.py",
        "workers/azure_functions_worker/extension.py",
        "workers/azure_functions_worker/utils/dependency.py",
        "workers/proxy_worker/start_worker.py",
        "workers/proxy_worker/dispatcher.py",
        "workers/proxy_worker/logging.py",
        "workers/proxy_worker/utils/dependency.py",
        "workers/r2p2/bridge/bridge.py",
        "workers/r2p2/bridge/protos_adapter.py",
        "runtimes/v2/azure_functions_runtime/handle_event.py",
        "runtimes/v2/azure_functions_runtime/native_invocation.py",
        "runtimes/v2/azure_functions_runtime/loader.py",
        "runtimes/v2/azure_functions_runtime/http_v2.py",
        "runtimes/v2/azure_functions_runtime/otel.py",
        "runtimes/v1/azure_functions_runtime_v1/handle_event.py",
        "runtimes/v1/azure_functions_runtime_v1/native_invocation.py",
    ]
    rs_paths = [
        "workers/r2p2/src/main.rs",
        "workers/r2p2/src/bridge.rs",
        "workers/r2p2/src/control.rs",
        "workers/r2p2/src/convert.rs",
        "workers/r2p2/src/codec.rs",
        "workers/r2p2/src/log.rs",
        "workers/r2p2/src/pb.rs",
    ]

    extracted: dict[str, dict[str, Any]] = {p: extract_python_file(p) for p in py_paths}
    for p in rs_paths:
        extracted[p] = extract_rust_file(p)

    proto_messages = extract_proto_messages("workers/r2p2/proto/FunctionRpc.proto")
    inventories = {
        "azure_functions_worker": scan_package_files("workers/azure_functions_worker", (".py",)),
        "proxy_worker": scan_package_files("workers/proxy_worker", (".py",)),
        "r2p2_rust": scan_package_files("workers/r2p2/src", (".rs",)),
        "r2p2_bridge": scan_package_files("workers/r2p2/bridge", (".py",)),
        "runtime_v2": scan_package_files("runtimes/v2/azure_functions_runtime", (".py",)),
        "runtime_v1": scan_package_files("runtimes/v1/azure_functions_runtime_v1", (".py",)),
    }

    mono_disp = extracted["workers/azure_functions_worker/dispatcher.py"]
    proxy_disp = extracted["workers/proxy_worker/dispatcher.py"]
    r2p2_main = extracted["workers/r2p2/src/main.rs"]
    r2p2_bridge_rs = extracted["workers/r2p2/src/bridge.rs"]
    r2p2_bridge_py = extracted["workers/r2p2/bridge/bridge.py"]
    rt_v2_event = extracted["runtimes/v2/azure_functions_runtime/handle_event.py"]
    rt_v2_native = extracted["runtimes/v2/azure_functions_runtime/native_invocation.py"]

    eras = [
        # =====================================================================
        # VIEW 0: 4-Repository Ecosystem Topology
        # =====================================================================
        {
            "id": "ecosystem",
            "shortTitle": "4-Repo Ecosystem",
            "title": "Cross-Repository Architecture (Wire, Worker, SDK & Extensions)",
            "pythonVersions": "All Supported Versions (3.7 → 3.15+)",
            "packagePath": "4 Linked GitHub Repositories",
            "launcherPath": "Host <-> Protobuf <-> Worker <-> Library & Extensions",
            "status": "Canonical Multi-Repo Map",
            "tagline": "How language-worker-protobuf, python-worker, python-library, and python-extensions compose the Python Functions runtime.",
            "summary": (
                "The Azure Functions Python stack spans four specialized repositories: "
                "`language-worker-protobuf` defines the cross-language gRPC wire contract; "
                "`python-worker` implements the transport shells (monolith, proxy_worker, R2P2) and "
                "execution runtimes (v1/v2); `python-library` provides the `azure-functions` decorator "
                "model and `Datum` type converters; and `python-extensions` powers HTTP v2 ASGI streaming, "
                "SDK-type deferred bindings, Settlement gRPC, and pluggable Agent Runtimes."
            ),
            "tradeoffs": [
                {"kind": "strength", "text": "Wire contract (`FunctionRpc.proto`) stays identical while worker transport evolves from Python `grpcio` to Rust `tonic`."},
                {"kind": "strength", "text": "`python-library` and `python-extensions` ship on PyPI independently of Azure Host images."},
                {"kind": "strength", "text": "Clean extension hooks (`WebApp`, `SdkType`, `RuntimeTrackerMeta`) let FastAPI, Blob SDK types, and Agent Frameworks plug in without forking the worker."},
            ],
            "erasDiff": {
                "transport": "Defined in language-worker-protobuf; implemented in python-worker",
                "boundary": "Datum & Decorator metadata (python-library) + Base metaclasses (python-extensions)",
                "runtimeLoading": "python-worker runtimes/v1,v2 or python-extensions RuntimeTrackerMeta",
                "hotPathOverhead": "Datum bindings take R2P2 Hot Path; Extensions (HTTP-v2 / SdkType) take Control Path",
            },
            "containers": [
                {"id": "ce-proto", "label": "Azure/azure-functions-language-worker-protobuf", "parentId": None, "tone": "proto"},
                {"id": "ce-worker", "label": "Azure/azure-functions-python-worker", "parentId": None, "tone": "rust-proc"},
                {"id": "ce-w-shell", "label": "Worker Transport Shells (workers/)", "parentId": "ce-worker", "tone": "transport"},
                {"id": "ce-w-rt", "label": "Execution Runtimes (runtimes/v1 & v2)", "parentId": "ce-worker", "tone": "runtime"},
                {"id": "ce-lib", "label": "Azure/azure-functions-python-library", "parentId": None, "tone": "lib"},
                {"id": "ce-ext", "label": "Azure/azure-functions-python-extensions", "parentId": None, "tone": "ext"},
            ],
            "nodes": [
                {
                    "id": "ne-funcrpc",
                    "repo": "language-worker-protobuf",
                    "containerId": "ce-proto",
                    "label": "FunctionRpc.proto",
                    "badge": "EventStream + StreamingMessage",
                    "role": "Canonical bidirectional gRPC protocol between the .NET Script Host and all Python workers.",
                    "file": "src/proto/FunctionRpc.proto",
                    "line": 1,
                    "details": [
                        "Compiled via `grpcio-tools` for ≤3.14 workers and via `prost-build`/`tonic` (`workers/r2p2/build.rs`) for 3.15+.",
                        "Defines `WorkerInit`, `FunctionsMetadata`, `FunctionLoad`, `InvocationRequest`, `RpcLog`, `WorkerStatus`.",
                    ],
                },
                {
                    "id": "ne-settle",
                    "repo": "language-worker-protobuf",
                    "containerId": "ce-proto",
                    "label": "settlement.proto & ClaimsIdentity",
                    "badge": "ServiceBus Settlement",
                    "role": "gRPC settlement service allowing Python functions to complete/abandon/dead-letter ServiceBus messages.",
                    "file": "src/proto/servicebus/settlement.proto",
                    "line": 1,
                    "details": [
                        "Consumed by `grpcClientType.py` in `python-extensions` and `get_settlement_client()` in `python-worker`.",
                    ],
                },
                {
                    "id": "ne-shells",
                    "repo": "python-worker",
                    "containerId": "ce-w-shell",
                    "label": "Transports: Monolith / Proxy / R2P2",
                    "badge": "≤3.12 | 3.13-14 | 3.15+",
                    "role": "Version-selected worker shell managing Host gRPC stream, logging, and sys.path dependency isolation.",
                    "file": "workers/r2p2/src/main.rs",
                    "line": sym_line(r2p2_main, "main", 230),
                    "details": [
                        "≤3.12: `workers/azure_functions_worker` (monolith).",
                        "3.13–3.14: `workers/proxy_worker` (Python transport shell).",
                        "3.15+: `workers/r2p2` (Rust `tonic`+`prost` + `PyO3` embedded CPython).",
                    ],
                },
                {
                    "id": "ne-runtimes",
                    "repo": "python-worker",
                    "containerId": "ce-w-rt",
                    "label": "azure-functions-runtime (v2 & v1)",
                    "badge": "handle_event + native_invocation",
                    "role": "PyPI-published execution engines that index apps, decode/encode bindings, and run sync/async handlers.",
                    "file": "runtimes/v2/azure_functions_runtime/handle_event.py",
                    "line": sym_line(rt_v2_event, "worker_init_request", 58),
                    "details": [
                        "`runtimes/v2`: V2 decorator model, HTTP v2 coordinator, OpenTelemetry.",
                        "`runtimes/v1`: V1 `function.json` folder model.",
                        "Exposes both `handle_event.py` (5-verb contract) and `native_invocation.py` (R2P2 zero-protobuf seam).",
                    ],
                },
                {
                    "id": "ne-lib-dec",
                    "repo": "python-library",
                    "containerId": "ce-lib",
                    "label": "Decorators & Blueprints",
                    "badge": "FunctionApp / @app.*",
                    "role": "Defines V2 Python programming model (`@app.route`, `@app.queue_trigger`, `Blueprint`, MCP & Connector triggers).",
                    "file": "azure/functions/__init__.py",
                    "line": 1,
                    "details": [
                        "Inspected by `runtimes/v2/azure_functions_runtime/loader.py` (`index_function_app`) during WorkerInit/Metadata.",
                        "Includes `azure/functions/mcp.py`, `connectors.py`, `warmup.py`, `decorators/`.",
                    ],
                },
                {
                    "id": "ne-lib-datum",
                    "repo": "python-library",
                    "containerId": "ce-lib",
                    "label": "meta.py Datum & Converters",
                    "badge": "Datum / InConverter / Out[T]",
                    "role": "Protobuf-agnostic `Datum` value container and trigger/binding converters (`HttpRequest`, `QueueMessage`, `Blob`).",
                    "file": "azure/functions/meta.py",
                    "line": 1,
                    "details": [
                        "`Datum` is the exact currency constructed by R2P2's `native_invocation.py` — enabling zero-protobuf execution!",
                        "`azure/functions/extension/` also defines `AppExtensionBase` & `FuncExtensionBase`.",
                    ],
                },
                {
                    "id": "ne-ext-base",
                    "repo": "python-extensions",
                    "containerId": "ce-ext",
                    "label": "extensions-base (WebApp, SdkType, Runtime)",
                    "badge": "web.py | sdkType.py | runtime.py",
                    "role": "Metaclass registries bridging HTTP v2 ASGI servers, SDK-type deferred bindings, and custom Agent Runtimes.",
                    "file": "azurefunctions-extensions-base/azurefunctions/extensions/base/runtime.py",
                    "line": 1,
                    "details": [
                        "`runtime.py` (`RuntimeTrackerMeta`): discovered when `PYTHON_ENABLE_AGENT_RUNTIME=1`.",
                        "`web.py` (`WebApp`): drives `http_v2.py` loopback streaming for FastAPI/ASGI.",
                        "`sdkType.py` (`SdkType`): drives deferred bindings (`requires_control_path() == true` in R2P2).",
                    ],
                },
                {
                    "id": "ne-ext-pkgs",
                    "repo": "python-extensions",
                    "containerId": "ce-ext",
                    "label": "FastAPI, SDK Bindings & Agent Runtimes",
                    "badge": "http-fastapi | bindings-* | agents-*",
                    "role": "Concrete extension packages for FastAPI HTTP streaming, Blob/Cosmos/EventHub/ServiceBus SDK types, and Agents.",
                    "file": "azurefunctions-extensions-http-fastapi/README.md",
                    "line": 1,
                    "details": [
                        "`azurefunctions-extensions-http-fastapi`: Request/Response streaming (`StreamingResponse`, SSE).",
                        "`azurefunctions-extensions-bindings-{blob,cosmosdb,eventhub,servicebus}`: rich Azure SDK client bindings.",
                        "`azurefunctions-agents-extensions-{agent-framework,copilot-sdk}`: hosted agent runtimes.",
                    ],
                },
            ],
            "edges": [
                {"id": "ee-1", "source": "ne-funcrpc", "target": "ne-shells", "kind": "grpc-wire", "label": "prost / grpcio codegen"},
                {"id": "ee-2", "source": "ne-shells", "target": "ne-runtimes", "kind": "pyo3-hot", "label": "WorkerRequest / PyO3 FFI"},
                {"id": "ee-3", "source": "ne-runtimes", "target": "ne-lib-dec", "kind": "inproc-contract", "label": "index_function_app()"},
                {"id": "ee-4", "source": "ne-runtimes", "target": "ne-lib-datum", "kind": "inproc-contract", "label": "Datum <-> Binding decode"},
                {"id": "ee-5", "source": "ne-runtimes", "target": "ne-ext-base", "kind": "pyo3-control", "label": "http_v2 / deferred SdkType"},
                {"id": "ee-6", "source": "ne-shells", "target": "ne-ext-base", "kind": "syspath-mutation", "label": "entry_points(azurefunctions.runtimes)", "dashed": True},
                {"id": "ee-7", "source": "ne-settle", "target": "ne-ext-base", "kind": "grpc-wire", "label": "grpcClientType settlement", "dashed": True},
                {"id": "ee-8", "source": "ne-ext-base", "target": "ne-ext-pkgs", "kind": "exec-dispatch", "label": "metaclass registration"},
            ],
            "flows": [
                {
                    "id": "eco_flow",
                    "title": "End-to-End Cross-Repo Request Lifecycle",
                    "summary": "How a single HTTP/SDK request traverses contracts defined across all 4 repositories.",
                    "actors": [
                        {"id": "proto", "label": "worker-protobuf"},
                        {"id": "shell", "label": "python-worker (Shell)"},
                        {"id": "rt", "label": "python-worker (Runtime)"},
                        {"id": "lib", "label": "python-library"},
                        {"id": "ext", "label": "python-extensions"},
                    ],
                    "steps": [
                        {"from": "proto", "to": "shell", "message": "FunctionRpc.proto StreamingMessage frame", "activeNodes": ["ne-funcrpc", "ne-shells"], "activeEdges": ["ee-1"], "payload": "Shared wire contract across 3.7 -> 3.15+"},
                        {"from": "shell", "to": "rt", "message": "Dispatch WorkerInit / Invocation across seam", "activeNodes": ["ne-shells", "ne-runtimes"], "activeEdges": ["ee-2"], "payload": "WorkerRequest (3.13) or PyO3 Tuple/Dict (3.15)"},
                        {"from": "rt", "to": "lib", "message": "Index @app decorators & decode Datum inputs", "activeNodes": ["ne-runtimes", "ne-lib-dec", "ne-lib-datum"], "activeEdges": ["ee-3", "ee-4"], "payload": "azure.functions.FunctionApp + meta.Datum"},
                        {"from": "rt", "to": "ext", "message": "Hydrate SdkType (BlobClient) or stream WebApp (FastAPI)", "activeNodes": ["ne-runtimes", "ne-ext-base", "ne-ext-pkgs"], "activeEdges": ["ee-5", "ee-8"], "payload": "azurefunctions.extensions.base"},
                        {"from": "ext", "to": "proto", "message": "Optional ServiceBus Settlement gRPC call to Host", "isReturn": True, "activeNodes": ["ne-ext-base", "ne-settle"], "activeEdges": ["ee-7"], "payload": "settlement.proto Complete/Abandon"},
                    ],
                },
            ],
        },
        # =====================================================================
        # ERA 1: Python <= 3.12 (Monolithic Worker)
        # =====================================================================
        {
            "id": "py312",
            "shortTitle": "Python ≤ 3.12",
            "title": "Monolithic Python Worker (≤ 3.12)",
            "pythonVersions": "3.7 – 3.12",
            "packagePath": "workers/azure_functions_worker",
            "launcherPath": "workers/python/prodV4/worker.py",
            "status": "Maintenance (Legacy Monolith)",
            "tagline": "Single-package CPython worker owning gRPC transport, protobuf, indexing, bindings, and invocation.",
            "summary": (
                "For Python 3.12 and below, `azure_functions_worker` is a single monolithic package. "
                "Transport (`grpcio` + `google.protobuf` compiled from `language-worker-protobuf`), "
                "dependency isolation, V1/V2 function indexing (`python-library`), HTTP v2 streaming "
                "(`python-extensions`), and execution all live in one coupled tree."
            ),
            "tradeoffs": [
                {"kind": "strength", "text": "Direct single-package Python calls; simplest mental model."},
                {"kind": "pain", "text": "Coupled releases: any binding/HTTP/OTel fix requires shipping a new Host worker bundle for every Python version."},
                {"kind": "pain", "text": "Worker `grpcio` and `google.protobuf` C-extensions live in the same interpreter as customer code."},
            ],
            "erasDiff": {
                "transport": "Python grpcio + google.protobuf (compiled from FunctionRpc.proto)",
                "boundary": "Monolithic internal imports inside azure_functions_worker",
                "runtimeLoading": "Bundled directly inside worker (no PyPI runtime split)",
                "hotPathOverhead": "grpcio thread -> asyncio -> Python protobuf -> Datum -> handler",
            },
            "containers": [
                {"id": "c312-host", "label": "Host & Wire Contract", "parentId": None, "tone": "proto"},
                {"id": "c312-worker", "label": "Monolithic Worker Process (workers/azure_functions_worker)", "parentId": None, "tone": "python"},
                {"id": "c312-trans", "label": "gRPC Transport & Isolation", "parentId": "c312-worker", "tone": "transport"},
                {"id": "c312-eng", "label": "In-Tree Indexing, Bindings & Executor", "parentId": "c312-worker", "tone": "runtime"},
                {"id": "c312-eco", "label": "SDK, Extensions & Customer App", "parentId": None, "tone": "lib"},
            ],
            "nodes": [
                {
                    "id": "n312-proto",
                    "repo": "language-worker-protobuf",
                    "containerId": "c312-host",
                    "label": "Host + FunctionRpc.proto",
                    "badge": "EventStream Server",
                    "role": "Functions Host spawns `prodV4/worker.py` and streams `StreamingMessage` frames over HTTP/2.",
                    "file": "src/proto/FunctionRpc.proto",
                    "line": 1,
                    "details": [
                        "Compiled into `workers/azure_functions_worker/protos/` via `grpcio-tools`.",
                    ],
                },
                {
                    "id": "n312-boot",
                    "repo": "python-worker",
                    "containerId": "c312-trans",
                    "label": "prodV4/worker.py & main.py",
                    "badge": "Boot + DependencyManager",
                    "role": "Sets worker-first sys.path so bundled `grpcio`/`protobuf` import cleanly, then starts asyncio loop.",
                    "file": "workers/azure_functions_worker/main.py",
                    "line": sym_line(extracted["workers/azure_functions_worker/main.py"], "start_async", 1),
                    "details": [
                        "`DependencyManager.initialize()` isolates worker deps during placeholder cold boot.",
                    ],
                },
                {
                    "id": "n312-grpc",
                    "repo": "python-worker",
                    "containerId": "c312-trans",
                    "label": "gRPC Pump (__poll_grpc)",
                    "badge": "grpcio + _grpc_resp_queue",
                    "role": "Background OS thread reading `stub.EventStream` and posting tasks via `call_soon_threadsafe`.",
                    "file": "workers/azure_functions_worker/dispatcher.py",
                    "line": sym_line(mono_disp, "connect", 180),
                    "details": [
                        "Outbound responses and `AsyncLoggingHandler` `RpcLog` records drain from `_grpc_resp_queue`.",
                    ],
                },
                {
                    "id": "n312-disp",
                    "repo": "python-worker",
                    "containerId": "c312-trans",
                    "label": "Monolithic Dispatcher",
                    "badge": "dispatcher.py",
                    "role": "Central class owning message routing, logging switch, OTel/AppInsights setup, and `_sync_call_tp`.",
                    "file": "workers/azure_functions_worker/dispatcher.py",
                    "line": sym_line(mono_disp, "Dispatcher", 76),
                    "details": [
                        "Directly imports `loader`, `bindings`, `http_v2`, `SharedMemoryManager`, and `ExtensionManager`.",
                    ],
                },
                {
                    "id": "n312-dep",
                    "repo": "python-worker",
                    "containerId": "c312-trans",
                    "label": "DependencyManager",
                    "badge": "utils/dependency.py",
                    "role": "Manages worker-first placeholder boot vs customer `.python_packages` promotion on Init/Specialization.",
                    "file": "workers/azure_functions_worker/utils/dependency.py",
                    "line": sym_line(extracted["workers/azure_functions_worker/utils/dependency.py"], "DependencyManager", 1),
                    "details": [
                        "Controls `use_worker_dependencies()` and `prioritize_customer_dependencies()`.",
                    ],
                },
                {
                    "id": "n312-load",
                    "repo": "python-worker",
                    "containerId": "c312-eng",
                    "label": "Loader & ExtensionManager",
                    "badge": "loader.py + extension.py",
                    "role": "Indexes V2 `@app` decorators or V1 `function.json` files and invokes `AppExtensionBase` hooks.",
                    "file": "workers/azure_functions_worker/loader.py",
                    "line": sym_line(extracted["workers/azure_functions_worker/loader.py"], "index_function_app", 1),
                    "details": [
                        "Populates `functions.Registry` with parameter binding metadata.",
                    ],
                },
                {
                    "id": "n312-bind",
                    "repo": "python-worker",
                    "containerId": "c312-eng",
                    "label": "Bindings, SharedMem & http_v2",
                    "badge": "bindings/ + mmap + ASGI",
                    "role": "Converts `protos.TypedData` <-> `Datum`, manages shared-memory rings, and coordinates HTTP v2 streaming.",
                    "file": "workers/azure_functions_worker/http_v2.py",
                    "line": sym_line(extracted["workers/azure_functions_worker/http_v2.py"], "HttpV2Registry", 1),
                    "details": [
                        "Calls into `python-library` converters and `python-extensions` `SdkType`/`WebApp`.",
                    ],
                },
                {
                    "id": "n312-sdk",
                    "repo": "python-library",
                    "containerId": "c312-eco",
                    "label": "azure-functions SDK",
                    "badge": "FunctionApp + Datum + Out",
                    "role": "Customer decorators, trigger/binding models (`HttpRequest`, `QueueMessage`), and `Datum` converters.",
                    "file": "azure/functions/meta.py",
                    "line": 1,
                    "details": [
                        "Shared by worker `bindings/meta.py` and customer `function_app.py`.",
                    ],
                },
                {
                    "id": "n312-ext",
                    "repo": "python-extensions",
                    "containerId": "c312-eco",
                    "label": "azurefunctions-extensions-*",
                    "badge": "http-fastapi + bindings-*",
                    "role": "Optional HTTP v2 ASGI streaming (`WebApp`) and deferred SDK bindings (`BlobClient`, etc.).",
                    "file": "azurefunctions-extensions-base/azurefunctions/extensions/base/sdkType.py",
                    "line": 1,
                    "details": [
                        "Hooks into `loader.py` and `http_v2.py` via base metaclasses.",
                    ],
                },
            ],
            "edges": [
                {"id": "e312-1", "source": "n312-proto", "target": "n312-grpc", "kind": "grpc-wire", "label": "EventStream (grpcio)"},
                {"id": "e312-2", "source": "n312-boot", "target": "n312-disp", "kind": "syspath-mutation", "label": "boot + DependencyManager"},
                {"id": "e312-3", "source": "n312-grpc", "target": "n312-disp", "kind": "thread-queue", "label": "call_soon_threadsafe / Queue"},
                {"id": "e312-4", "source": "n312-disp", "target": "n312-load", "kind": "inproc-contract", "label": "index & load"},
                {"id": "e312-5", "source": "n312-disp", "target": "n312-bind", "kind": "inproc-contract", "label": "TypedData <-> args"},
                {"id": "e312-6", "source": "n312-load", "target": "n312-sdk", "kind": "exec-dispatch", "label": "inspect @app / function.json"},
                {"id": "e312-7", "source": "n312-bind", "target": "n312-sdk", "kind": "exec-dispatch", "label": "Datum decode + invoke"},
                {"id": "e312-8", "source": "n312-bind", "target": "n312-ext", "kind": "pyo3-control", "label": "WebApp / SdkType", "dashed": True},
            ],
            "flows": [
                {
                    "id": "init",
                    "title": "Cold Start & Monolithic Init",
                    "summary": "prodV4 boots monolith, opens grpcio EventStream, switches sys.path to customer packages, and indexes decorators.",
                    "actors": [
                        {"id": "host", "label": "Host (FunctionRpc)"},
                        {"id": "grpc", "label": "gRPC Thread"},
                        {"id": "disp", "label": "Dispatcher"},
                        {"id": "load", "label": "Loader"},
                        {"id": "sdk", "label": "python-library"},
                    ],
                    "steps": [
                        {"from": "host", "to": "grpc", "message": "Spawn prodV4/worker.py + StartStream", "activeNodes": ["n312-proto", "n312-boot", "n312-grpc"], "activeEdges": ["e312-1", "e312-2"], "payload": "Worker grpcio/protobuf loaded first"},
                        {"from": "host", "to": "disp", "message": "WorkerInitRequest(app_dir, capabilities)", "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"], "activeEdges": ["e312-1", "e312-3"], "payload": "StreamingMessage.worker_init_request"},
                        {"from": "disp", "to": "load", "message": "prioritize_customer_deps + index_function_app()", "activeNodes": ["n312-disp", "n312-load"], "activeEdges": ["e312-4"], "payload": "Customer .python_packages promoted"},
                        {"from": "load", "to": "sdk", "message": "Read FunctionApp / Blueprints", "activeNodes": ["n312-load", "n312-sdk"], "activeEdges": ["e312-6"], "payload": "azure.functions decorators"},
                        {"from": "disp", "to": "host", "message": "WorkerInitResponse(capabilities)", "isReturn": True, "activeNodes": ["n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["e312-3", "e312-1"], "payload": "SHARED_MEMORY + RAW_HTTP_BODY_BYTES"},
                    ],
                },
                {
                    "id": "invoke",
                    "title": "Invocation Lifecycle",
                    "summary": "Dispatcher decodes protobuf TypedData via bindings, runs sync threadpool or async coroutine, and encodes response.",
                    "actors": [
                        {"id": "host", "label": "Host (FunctionRpc)"},
                        {"id": "disp", "label": "Dispatcher"},
                        {"id": "bind", "label": "Bindings / http_v2"},
                        {"id": "sdk", "label": "SDK & User App"},
                    ],
                    "steps": [
                        {"from": "host", "to": "disp", "message": "InvocationRequest(function_id, input_data)", "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"], "activeEdges": ["e312-1", "e312-3"], "payload": "google.protobuf InvocationRequest"},
                        {"from": "disp", "to": "bind", "message": "from_incoming_proto() / SharedMemory", "activeNodes": ["n312-disp", "n312-bind"], "activeEdges": ["e312-5"], "payload": "TypedData -> Datum"},
                        {"from": "bind", "to": "sdk", "message": "Decode SDK types + run handler (_sync_call_tp / await)", "activeNodes": ["n312-bind", "n312-sdk", "n312-ext"], "activeEdges": ["e312-7", "e312-8"], "payload": "HttpRequest / SdkType -> User fn"},
                        {"from": "sdk", "to": "host", "message": "to_outgoing_proto() -> InvocationResponse", "isReturn": True, "activeNodes": ["n312-sdk", "n312-bind", "n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["e312-7", "e312-5", "e312-3", "e312-1"], "payload": "Queued onto _grpc_resp_queue"},
                    ],
                },
            ],
        },
        # =====================================================================
        # ERA 2: Python 3.13 - 3.14 (Split Proxy Worker + Pluggable Runtimes)
        # =====================================================================
        {
            "id": "py313_314",
            "shortTitle": "Python 3.13 – 3.14",
            "title": "Split Proxy Worker + PyPI Runtimes (3.13 – 3.14)",
            "pythonVersions": "3.13 – 3.14",
            "packagePath": "workers/proxy_worker + runtimes/{v1,v2}",
            "launcherPath": "workers/python/proxyV4/worker.py",
            "status": "Production (Python 3.13 / 3.14)",
            "tagline": "Thin transport shell (`proxy_worker`) calling decoupled PyPI engines (`azure-functions-runtime` v2/v1 or Agent Runtimes).",
            "summary": (
                "Python 3.13 split the worker into two independently versioned layers. "
                "`workers/proxy_worker` is a thin, stable transport shell owning `grpcio`, "
                "`DependencyManager`, logging switch, and 4-tier `invocation_id` tracking. "
                "It delegates execution across a 5-verb `WorkerRequest` seam (injecting `protos` at init) "
                "to `runtimes/v2`, `runtimes/v1`, or a custom `python-extensions` Agent Runtime."
            ),
            "tradeoffs": [
                {"kind": "strength", "text": "Decoupled cadence: `azure-functions-runtime` updates ship via PyPI without waiting for Host worker deployments."},
                {"kind": "strength", "text": "Injected `protos` decouples runtime code from specific protobuf wheel builds; unlocks pluggable Agent Runtimes."},
                {"kind": "pain", "text": "`proxy_worker` still links CPython `grpcio` + `protobuf` wheels (delaying day-1 support for new Python releases) and contends on the GIL."},
            ],
            "erasDiff": {
                "transport": "Python proxy_worker (grpcio + worker protobuf + uvloop)",
                "boundary": "In-process async WorkerRequest(name, request, properties={protos, host})",
                "runtimeLoading": "reload_library_worker(): Agent EntryPoint -> V2 (function_app.py) -> V1",
                "hotPathOverhead": "grpcio thread -> asyncio -> WorkerRequest -> runtime cached protos",
            },
            "containers": [
                {"id": "c313-host", "label": "Host & Wire Contract", "parentId": None, "tone": "proto"},
                {"id": "c313-worker", "label": "Python Worker Process (proxyV4/worker.py)", "parentId": None, "tone": "python"},
                {"id": "c313-proxy", "label": "Layer 1: proxy_worker (Transport Shell)", "parentId": "c313-worker", "tone": "transport"},
                {"id": "c313-rt", "label": "Layer 2: Pluggable Runtime Engine (runtimes/)", "parentId": "c313-worker", "tone": "runtime"},
                {"id": "c313-eco", "label": "PyPI SDK, Extensions & Custom Runtimes", "parentId": None, "tone": "lib"},
            ],
            "nodes": [
                {
                    "id": "n313-proto",
                    "repo": "language-worker-protobuf",
                    "containerId": "c313-host",
                    "label": "Host + FunctionRpc.proto",
                    "badge": "EventStream Server",
                    "role": "Host spawns `proxyV4/worker.py` (`python -m proxy_worker`) for Python 3.13/3.14.",
                    "file": "src/proto/FunctionRpc.proto",
                    "line": 1,
                    "details": [
                        "Identical wire contract; `worker_status_request` answered directly by `proxy_worker`.",
                    ],
                },
                {
                    "id": "n313-grpc",
                    "repo": "python-worker",
                    "containerId": "c313-proxy",
                    "label": "start_worker + gRPC Pump",
                    "badge": "uvloop + grpc_local-thread",
                    "role": "Locks worker deps first, enables `uvloop`, opens `grpcio` stream, and switches console -> `RpcLog`.",
                    "file": "workers/proxy_worker/dispatcher.py",
                    "line": sym_line(proxy_disp, "__poll_grpc", 279),
                    "details": [
                        "4-tier `invocation_id` tracking: global -> `ContextEnabledTask` -> `invocation_id_cv` -> thread-local.",
                    ],
                },
                {
                    "id": "n313-router",
                    "repo": "python-worker",
                    "containerId": "c313-proxy",
                    "label": "Proxy Router & WorkerRequest",
                    "badge": "reload_library_worker()",
                    "role": "Promotes customer deps, dynamically selects V2 / V1 / Agent runtime, and passes `WorkerRequest` + `protos`.",
                    "file": "workers/proxy_worker/dispatcher.py",
                    "line": sym_line(proxy_disp, "_dispatch_grpc_request", 329),
                    "details": [
                        "Injects `properties={'protos': protos, 'host': host}` on Init & EnvironmentReload so runtimes stay protobuf-version agnostic.",
                    ],
                },
                {
                    "id": "n313-rtv2",
                    "repo": "python-worker",
                    "containerId": "c313-rt",
                    "label": "Runtime V2 (azure_functions_runtime)",
                    "badge": "runtimes/v2/handle_event.py",
                    "role": "PyPI V2 engine: decorator indexing, `Datum` bindings, HTTP v2 streaming, OpenTelemetry, threadpool.",
                    "file": "runtimes/v2/azure_functions_runtime/handle_event.py",
                    "line": sym_line(rt_v2_event, "worker_init_request", 58),
                    "details": [
                        "Selected when `function_app.py` (or configured script file) exists in app directory.",
                    ],
                },
                {
                    "id": "n313-rtv1",
                    "repo": "python-worker",
                    "containerId": "c313-rt",
                    "label": "Runtime V1 (azure_functions_runtime_v1)",
                    "badge": "runtimes/v1/handle_event.py",
                    "role": "PyPI V1 engine supporting classic `function.json` apps across the exact same 5-verb contract.",
                    "file": "runtimes/v1/azure_functions_runtime_v1/handle_event.py",
                    "line": sym_line(extracted["runtimes/v1/azure_functions_runtime_v1/handle_event.py"], "worker_init_request", 45),
                    "details": [
                        "Selected automatically when `function_app.py` is not present.",
                    ],
                },
                {
                    "id": "n313-ext",
                    "repo": "python-extensions",
                    "containerId": "c313-eco",
                    "label": "Agent Runtimes, WebApp & SdkType",
                    "badge": "runtime.py | web.py | sdkType.py",
                    "role": "Custom `azurefunctions.runtimes` entry points (`PYTHON_ENABLE_AGENT_RUNTIME`), FastAPI HTTP v2, and SDK bindings.",
                    "file": "azurefunctions-extensions-base/azurefunctions/extensions/base/runtime.py",
                    "line": 1,
                    "details": [
                        "`RuntimeTrackerMeta` + `entry_points(group='azurefunctions.runtimes')` can replace V1/V2 engine entirely!",
                    ],
                },
                {
                    "id": "n313-lib",
                    "repo": "python-library",
                    "containerId": "c313-eco",
                    "label": "azure-functions SDK & User App",
                    "badge": "Decorators + Datum + Handler",
                    "role": "Customer `function_app.py` + `azure-functions` SDK types invoked on asyncio loop or threadpool.",
                    "file": "azure/functions/__init__.py",
                    "line": 1,
                    "details": [
                        "Customer can pin newer `azure-functions` and `azure-functions-runtime` in `requirements.txt`.",
                    ],
                },
            ],
            "edges": [
                {"id": "e313-1", "source": "n313-proto", "target": "n313-grpc", "kind": "grpc-wire", "label": "EventStream (grpcio)"},
                {"id": "e313-2", "source": "n313-grpc", "target": "n313-router", "kind": "thread-queue", "label": "ContextEnabledTask / Queue"},
                {"id": "e313-3", "source": "n313-router", "target": "n313-rtv2", "kind": "inproc-contract", "label": "WorkerRequest (V2)"},
                {"id": "e313-4", "source": "n313-router", "target": "n313-rtv1", "kind": "inproc-contract", "label": "WorkerRequest (V1)", "dashed": True},
                {"id": "e313-5", "source": "n313-router", "target": "n313-ext", "kind": "syspath-mutation", "label": "Agent Runtime EntryPoint", "dashed": True},
                {"id": "e313-6", "source": "n313-rtv2", "target": "n313-ext", "kind": "pyo3-control", "label": "WebApp HTTP-v2 / SdkType"},
                {"id": "e313-7", "source": "n313-rtv2", "target": "n313-lib", "kind": "exec-dispatch", "label": "Datum decode + invoke"},
                {"id": "e313-8", "source": "n313-rtv1", "target": "n313-lib", "kind": "exec-dispatch", "label": "Datum decode + invoke", "dashed": True},
            ],
            "flows": [
                {
                    "id": "init",
                    "title": "Cold Start, Runtime Discovery & protos Injection",
                    "summary": "Proxy switches to customer deps, resolves Agent Runtime vs V2 vs V1, and injects its `protos` module once.",
                    "actors": [
                        {"id": "host", "label": "Host (FunctionRpc)"},
                        {"id": "router", "label": "proxy_worker"},
                        {"id": "ext", "label": "python-extensions"},
                        {"id": "rt", "label": "Runtime v2/v1"},
                    ],
                    "steps": [
                        {"from": "host", "to": "router", "message": "StartStream + WorkerInitRequest(dir)", "activeNodes": ["n313-proto", "n313-grpc", "n313-router"], "activeEdges": ["e313-1", "e313-2"], "payload": "uvloop + grpc_local-thread active"},
                        {"from": "router", "to": "ext", "message": "Check PYTHON_ENABLE_AGENT_RUNTIME entry_points", "activeNodes": ["n313-router", "n313-ext"], "activeEdges": ["e313-5"], "payload": "group='azurefunctions.runtimes'"},
                        {"from": "router", "to": "rt", "message": "Import V2/V1 + await worker_init_request(WorkerRequest)", "activeNodes": ["n313-router", "n313-rtv2"], "activeEdges": ["e313-3"], "payload": "properties={'protos': protos, 'host': host}"},
                        {"from": "rt", "to": "host", "message": "Cache protos, index app, return WorkerInitResponse", "isReturn": True, "activeNodes": ["n313-rtv2", "n313-lib", "n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["e313-7", "e313-3", "e313-2", "e313-1"], "payload": "Capabilities negotiated"},
                    ],
                },
                {
                    "id": "invoke",
                    "title": "Standard & HTTP-v2 Invocation",
                    "summary": "Proxy stamps invocation_id and delegates `WorkerRequest` to runtime v2 (`python-library` + `python-extensions`).",
                    "actors": [
                        {"id": "host", "label": "Host (FunctionRpc)"},
                        {"id": "router", "label": "proxy_worker"},
                        {"id": "rt", "label": "Runtime v2"},
                        {"id": "lib", "label": "SDK / Extensions / App"},
                    ],
                    "steps": [
                        {"from": "host", "to": "router", "message": "InvocationRequest(invocation_id, function_id)", "activeNodes": ["n313-proto", "n313-grpc", "n313-router"], "activeEdges": ["e313-1", "e313-2"], "payload": "ContextEnabledTask stamps invocation_id"},
                        {"from": "router", "to": "rt", "message": "await _library_worker.invocation_request(req)", "activeNodes": ["n313-router", "n313-rtv2"], "activeEdges": ["e313-3"], "payload": "Uses cached protos"},
                        {"from": "rt", "to": "lib", "message": "Decode Datum / SdkType / WebApp + invoke user fn", "activeNodes": ["n313-rtv2", "n313-ext", "n313-lib"], "activeEdges": ["e313-6", "e313-7"], "payload": "Sync threadpool or async loop"},
                        {"from": "lib", "to": "host", "message": "InvocationResponse -> _grpc_resp_queue", "isReturn": True, "activeNodes": ["n313-lib", "n313-rtv2", "n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["e313-7", "e313-3", "e313-2", "e313-1"], "payload": "StreamingMessage sent over grpcio"},
                    ],
                },
            ],
        },
        # =====================================================================
        # ERA 3: Python 3.15+ (R2P2 — Rust to Python Proxy)
        # =====================================================================
        {
            "id": "py315_r2p2",
            "shortTitle": "Python 3.15+ (R2P2)",
            "title": "R2P2 — Rust Transport + Embedded CPython via PyO3 (3.15+)",
            "pythonVersions": "3.15+ (GIL Build)",
            "packagePath": "workers/r2p2 + runtimes/{v1,v2}",
            "launcherPath": "workers/r2p2 (compiled native Rust binary)",
            "status": "Next-Gen Architecture (Python 3.15+)",
            "tagline": "Native Rust (`tonic` + `prost` + `tokio`) embedding CPython via `PyO3` — zero Python `grpcio`/`protobuf`, +122% req/s.",
            "summary": (
                "R2P2 replaces the Python proxy worker with a native Rust binary that compiles "
                "`FunctionRpc.proto` via `prost`/`tonic` and embeds `libpython` (GIL) via `PyO3`. "
                "Standard `python-library` `Datum` invocations take a **Zero-Protobuf Hot Path** "
                "(`convert.rs` tuples -> `native_invocation.py`), while control-plane and "
                "`python-extensions` (`SdkType` deferred / `WebApp` HTTP-v2) calls route through "
                "`control.rs` + `protos_adapter.py`."
            ),
            "tradeoffs": [
                {"kind": "strength", "text": "Day-1 Python 3.15+ support: zero wait on `grpcio` or `google.protobuf` C-extension wheels."},
                {"kind": "strength", "text": "+122% throughput (754 vs 339 req/s, p50 64ms vs 145ms) on GIL build via native `tonic`/`prost` + PyO3 datum tuples."},
                {"kind": "strength", "text": "Complete transport isolation: zero `google.protobuf` or `grpcio` loaded in `sys.modules`."},
                {"kind": "pain", "text": "Dual FFI paths (`invoke_native` hot path vs `handle_invocation_control` for HTTP-v2 / `SdkType` extensions)."},
            ],
            "erasDiff": {
                "transport": "Native Rust: tonic + prost + tokio multi-thread + BytesCodec",
                "boundary": "PyO3 FFI (GIL): Hot `(name, Datum)` tuples + Control `PyDict` + `LogSink`",
                "runtimeLoading": "Unchanged `runtimes/v2,v1` fed `protos_adapter.py` + `native_invocation.py`",
                "hotPathOverhead": "Rust prost -> PyO3 tuple -> native_invocation.py -> python-library Datum (0 protobuf)",
            },
            "containers": [
                {"id": "c315-host", "label": "Host & Wire Contract", "parentId": None, "tone": "proto"},
                {"id": "c315-proc", "label": "R2P2 Worker Process (Rust Binary + Embedded CPython 3.15)", "parentId": None, "tone": "rust-proc"},
                {"id": "c315-rust", "label": "Layer 1: Native Rust Shell (workers/r2p2/src)", "parentId": "c315-proc", "tone": "rust"},
                {"id": "c315-ffi", "label": "PyO3 FFI Thin Waist (GIL)", "parentId": "c315-proc", "tone": "bridge"},
                {"id": "c315-py", "label": "Layer 2: Embedded Python Bridge & Runtime", "parentId": "c315-proc", "tone": "runtime"},
                {"id": "c315-eco", "label": "SDK, Extensions & Customer Function App", "parentId": None, "tone": "lib"},
            ],
            "nodes": [
                {
                    "id": "n315-proto",
                    "repo": "language-worker-protobuf",
                    "containerId": "c315-host",
                    "label": "Host + FunctionRpc.proto",
                    "badge": "prost-build (build.rs)",
                    "role": "Exact same Host gRPC contract, compiled at Rust build time into native `prost` structs (`pb.rs`).",
                    "file": "src/proto/FunctionRpc.proto",
                    "line": 1,
                    "details": [
                        "Vendored in `workers/r2p2/proto/` and compiled by `build.rs` with zero system `protoc` dependency.",
                    ],
                },
                {
                    "id": "n315-tonic",
                    "repo": "python-worker",
                    "containerId": "c315-rust",
                    "label": "Tokio + Tonic EventStream",
                    "badge": "main.rs + BytesCodec",
                    "role": "Multi-thread tokio pump dialing Host (`TCP_NODELAY`), spawning concurrent tasks, and draining `mpsc<Bytes>`.",
                    "file": "workers/r2p2/src/main.rs",
                    "line": sym_line(r2p2_main, "main", 230),
                    "details": [
                        "Shared lock-free `mpsc::unbounded_channel<Bytes>` carries both responses and Python `LogSink` frames.",
                    ],
                },
                {
                    "id": "n315-router",
                    "repo": "python-worker",
                    "containerId": "c315-rust",
                    "label": "Prost Router & Status Fast-Path",
                    "badge": "process_message()",
                    "role": "Answers `WorkerStatus` in pure Rust (0 GIL) and splits Hot vs Control invocations via `control_path_cache`.",
                    "file": "workers/r2p2/src/main.rs",
                    "line": sym_line(r2p2_main, "process_message", 193),
                    "details": [
                        "Memoizes `needs_control_path(function_id)` once per function after `FunctionLoad`.",
                    ],
                },
                {
                    "id": "n315-hot-ffi",
                    "repo": "python-worker",
                    "containerId": "c315-ffi",
                    "label": "Hot FFI: bridge::invoke + convert.rs",
                    "badge": "PyO3 Datum Tuples",
                    "role": "Translates prost `TypedData` directly into `(tag, value)` Python tuples across `Python::attach`.",
                    "file": "workers/r2p2/src/bridge.rs",
                    "line": sym_line(r2p2_bridge_rs, "invoke", 261),
                    "details": [
                        "Eliminates all Python protobuf object allocation on standard HTTP/Queue/Timer/Blob invocations.",
                    ],
                },
                {
                    "id": "n315-ctrl-ffi",
                    "repo": "python-worker",
                    "containerId": "c315-ffi",
                    "label": "Control FFI: bridge::handle + LogSink",
                    "badge": "control.rs + #[pyclass] LogSink",
                    "role": "Converts Init/Load/Reload & HTTP-v2/deferred requests to `PyDict`s; exposes non-blocking Rust `LogSink`.",
                    "file": "workers/r2p2/src/bridge.rs",
                    "line": sym_line(r2p2_bridge_rs, "handle", 107),
                    "details": [
                        "`LogSink.emit_log(dict)` encodes `RpcLog` in Rust so Python logging never touches protobuf or blocks.",
                    ],
                },
                {
                    "id": "n315-bridge-py",
                    "repo": "python-worker",
                    "containerId": "c315-py",
                    "label": "bridge.py & protos_adapter.py",
                    "badge": "Protobuf-Free + Namespace Dep Iso",
                    "role": "Pure-Python `protos` stand-in + `_clear_modules_from_path` namespace-safe customer dependency promotion.",
                    "file": "workers/r2p2/bridge/bridge.py",
                    "line": sym_line(r2p2_bridge_py, "_clear_modules_from_path", 328),
                    "details": [
                        "Preserves shared namespace parents while evicting worker-backed packages and stale parent attributes.",
                    ],
                },
                {
                    "id": "n315-native-py",
                    "repo": "python-worker",
                    "containerId": "c315-py",
                    "label": "native_invocation.py (v2 & v1)",
                    "badge": "Hot Datum Execution Seam",
                    "role": "Decodes Rust datum tuples directly into `python-library` bindings using `_InvocShim` and runs user code.",
                    "file": "runtimes/v2/azure_functions_runtime/native_invocation.py",
                    "line": sym_line(rt_v2_native, "_decode_inputs", 82),
                    "details": [
                        "Supports sync (`ThreadPoolExecutor`) & async (`asyncio`), `Context`, `Out[T]`, and W3C OpenTelemetry.",
                    ],
                },
                {
                    "id": "n315-rt",
                    "repo": "python-worker",
                    "containerId": "c315-py",
                    "label": "Runtime handle_event + http_v2",
                    "badge": "Control & Streaming Seam",
                    "role": "Handles `WorkerInit`, `FunctionLoad`, `EnvironmentReload`, and fallback invocations for Extensions.",
                    "file": "runtimes/v2/azure_functions_runtime/handle_event.py",
                    "line": sym_line(rt_v2_event, "worker_init_request", 58),
                    "details": [
                        "Operates seamlessly against `protos_adapter.py` without code duplication.",
                    ],
                },
                {
                    "id": "n315-lib",
                    "repo": "python-library",
                    "containerId": "c315-eco",
                    "label": "azure-functions (Datum + Decorators)",
                    "badge": "Hot-Path Compatible",
                    "role": "Standard V2/V1 triggers & bindings (`HttpRequest`, `QueueMessage`, `TimerRequest`, `Out[T]`) + User App.",
                    "file": "azure/functions/meta.py",
                    "line": 1,
                    "details": [
                        "Runs at full native speed via `native_invocation.py` with zero protobuf dependency!",
                    ],
                },
                {
                    "id": "n315-ext",
                    "repo": "python-extensions",
                    "containerId": "c315-eco",
                    "label": "extensions (HTTP-v2 FastAPI & SdkType)",
                    "badge": "requires_control_path = true",
                    "role": "`WebApp` ASGI streaming (`http-fastapi`) and `SdkType` deferred bindings (`BlobClient`, `ServiceBus`).",
                    "file": "azurefunctions-extensions-base/azurefunctions/extensions/base/web.py",
                    "line": 1,
                    "details": [
                        "Detected by `bridge.requires_control_path(fn_id)` and routed cleanly via `handle_invocation_control`.",
                    ],
                },
            ],
            "edges": [
                {"id": "e315-1", "source": "n315-proto", "target": "n315-tonic", "kind": "grpc-wire", "label": "EventStream (tonic + BytesCodec)"},
                {"id": "e315-2", "source": "n315-tonic", "target": "n315-router", "kind": "thread-queue", "label": "tokio::spawn + mpsc<Bytes>"},
                {"id": "e315-3", "source": "n315-router", "target": "n315-hot-ffi", "kind": "pyo3-hot", "label": "Hot Path: bridge::invoke()"},
                {"id": "e315-4", "source": "n315-router", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "Control / Extensions Path"},
                {"id": "e315-5", "source": "n315-hot-ffi", "target": "n315-native-py", "kind": "pyo3-hot", "label": "invoke_native(datum tuples)"},
                {"id": "e315-6", "source": "n315-ctrl-ffi", "target": "n315-bridge-py", "kind": "pyo3-control", "label": "handle_control(PyDict)"},
                {"id": "e315-7", "source": "n315-bridge-py", "target": "n315-rt", "kind": "inproc-contract", "label": "WorkerRequest + protos_adapter"},
                {"id": "e315-8", "source": "n315-native-py", "target": "n315-lib", "kind": "exec-dispatch", "label": "Datum decode + invoke"},
                {"id": "e315-9", "source": "n315-rt", "target": "n315-ext", "kind": "pyo3-control", "label": "WebApp stream / SdkType", "dashed": True},
                {"id": "e315-10", "source": "n315-rt", "target": "n315-lib", "kind": "inproc-contract", "label": "index @app decorators", "dashed": True},
            ],
            "flows": [
                {
                    "id": "hot_invoke",
                    "title": "Hot Native Invocation (prost -> PyO3 Tuple -> python-library Datum)",
                    "summary": "Standard triggers bypass Python protobuf completely: prost decodes TypedData into PyO3 datum tuples for native_invocation.py.",
                    "actors": [
                        {"id": "host", "label": "Host (FunctionRpc)"},
                        {"id": "rust", "label": "R2P2 (tonic+prost)"},
                        {"id": "ffi", "label": "bridge::invoke"},
                        {"id": "native", "label": "native_invocation.py"},
                        {"id": "lib", "label": "python-library + App"},
                    ],
                    "steps": [
                        {"from": "host", "to": "rust", "message": "StreamingMessage(InvocationRequest) bytes", "activeNodes": ["n315-proto", "n315-tonic", "n315-router"], "activeEdges": ["e315-1", "e315-2"], "payload": "needs_control_path(fn_id) == false (cached)"},
                        {"from": "rust", "to": "ffi", "message": "prost decode -> convert::typed_data_to_tuple", "activeNodes": ["n315-router", "n315-hot-ffi"], "activeEdges": ["e315-3"], "payload": "Rust TypedData -> compact PyTuple"},
                        {"from": "ffi", "to": "native", "message": "Python::attach -> invoke_native(fn_id, inputs, meta)", "activeNodes": ["n315-hot-ffi", "n315-native-py"], "activeEdges": ["e315-5"], "payload": "Zero Python protobuf objects created"},
                        {"from": "native", "to": "lib", "message": "Decode azure.functions Datum + execute handler", "activeNodes": ["n315-native-py", "n315-lib"], "activeEdges": ["e315-8"], "payload": "HttpRequest / QueueMessage -> User fn"},
                        {"from": "lib", "to": "host", "message": "Return tuple -> prost encode -> mpsc tx", "isReturn": True, "activeNodes": ["n315-lib", "n315-native-py", "n315-hot-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["e315-8", "e315-5", "e315-3", "e315-2", "e315-1"], "payload": "+122% throughput vs Python proxy"},
                    ],
                },
                {
                    "id": "ext_invoke",
                    "title": "Extensions Path (HTTP-v2 FastAPI Streaming & SdkType Bindings)",
                    "summary": "Functions using `python-extensions` (`WebApp` HTTP streaming or `SdkType` BlobClient) route through `handle_invocation_control`.",
                    "actors": [
                        {"id": "host", "label": "Host (FunctionRpc)"},
                        {"id": "rust", "label": "R2P2 Router"},
                        {"id": "ctrl", "label": "bridge::handle + bridge.py"},
                        {"id": "rt", "label": "Runtime + http_v2"},
                        {"id": "ext", "label": "python-extensions"},
                    ],
                    "steps": [
                        {"from": "host", "to": "rust", "message": "InvocationRequest(function_id)", "activeNodes": ["n315-proto", "n315-tonic", "n315-router"], "activeEdges": ["e315-1", "e315-2"], "payload": "needs_control_path(fn_id) == true"},
                        {"from": "rust", "to": "ctrl", "message": "control::invocation_request_to_py(PyDict)", "activeNodes": ["n315-router", "n315-ctrl-ffi", "n315-bridge-py"], "activeEdges": ["e315-4", "e315-6"], "payload": "protos_adapter wraps dict (still 0 google.protobuf)"},
                        {"from": "ctrl", "to": "rt", "message": "await handle_event.invocation_request()", "activeNodes": ["n315-bridge-py", "n315-rt"], "activeEdges": ["e315-7"], "payload": "Standard runtime invocation path"},
                        {"from": "rt", "to": "ext", "message": "Stream ASGI FastAPI chunks / hydrate SdkType", "activeNodes": ["n315-rt", "n315-ext"], "activeEdges": ["e315-9"], "payload": "azurefunctions.extensions.base"},
                        {"from": "ext", "to": "host", "message": "Dict -> py_to_invocation_response -> prost bytes", "isReturn": True, "activeNodes": ["n315-ext", "n315-rt", "n315-ctrl-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["e315-9", "e315-7", "e315-6", "e315-4", "e315-1"], "payload": "StreamingMessage(InvocationResponse)"},
                    ],
                },
                {
                    "id": "env_reload",
                    "title": "Placeholder Specialization & Namespace-Safe Dep Promotion",
                    "summary": "Evicts worker-backed modules while keeping shared `azure.*` / `azurefunctions.*` namespace parents attached.",
                    "actors": [
                        {"id": "host", "label": "Host (FunctionRpc)"},
                        {"id": "ctrl", "label": "bridge::handle"},
                        {"id": "bpy", "label": "bridge.py Dep Engine"},
                        {"id": "rt", "label": "Runtime + SDK"},
                    ],
                    "steps": [
                        {"from": "host", "to": "ctrl", "message": "FunctionEnvironmentReloadRequest(app_dir)", "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi"], "activeEdges": ["e315-1", "e315-2", "e315-4"], "payload": "Warm placeholder specializes to customer app"},
                        {"from": "ctrl", "to": "bpy", "message": "_clear_modules_from_path + _prioritize_customer_deps", "activeNodes": ["n315-ctrl-ffi", "n315-bridge-py"], "activeEdges": ["e315-6"], "payload": "Retains namespace parents (`azure`, `azurefunctions`); evicts stale worker children"},
                        {"from": "bpy", "to": "rt", "message": "Import customer-pinned SDK/runtime & index app", "activeNodes": ["n315-bridge-py", "n315-rt", "n315-lib"], "activeEdges": ["e315-7", "e315-10"], "payload": "sys.path: [customer_pkgs, worker_deps, app_dir]"},
                        {"from": "rt", "to": "host", "message": "FunctionEnvironmentReloadResponse", "isReturn": True, "activeNodes": ["n315-rt", "n315-ctrl-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["e315-7", "e315-6", "e315-4", "e315-1"], "payload": "Specialized & ready"},
                    ],
                },
            ],
        },
    ]

    phases_by_era = {
        "py312": get_py312_phases(),
        "py313_314": get_py313_phases(),
        "py315_r2p2": get_py315_phases(),
    }

    for era in eras:
        for node in era["nodes"]:
            fmeta: dict[str, Any] = {}
            if node["repo"] == "python-worker":
                fmeta = extracted.get(node["file"], {})
            elif node["repo"] in repo_dirs and node["file"].endswith(".py"):
                fmeta = extract_python_file(node["file"], repo_dirs[node["repo"]])
            node["fileLines"] = fmeta.get("lines", 0)
            node["extractedSymbols"] = fmeta.get("symbols", [])[:10]
            node["routerCases"] = fmeta.get("routerCases", [])
            node["pyo3Calls"] = fmeta.get("pyo3Calls", [])
            node["githubUrl"] = resolve_github_url(node, repo_refs)
        era["topologyMermaid"] = compile_topology_mermaid(era)
        for flow in era["flows"]:
            flow["sequenceMermaid"] = compile_sequence_mermaid(flow)

        era_phases = phases_by_era.get(era["id"], [])
        for ph in era_phases:
            ph["topologyMermaid"] = compile_topology_mermaid(era, ph["topologyEdges"])
            ph["sequenceMermaid"] = compile_sequence_mermaid(ph)
        era["phases"] = era_phases

    structural_payload = json.dumps(
        {
            "repos": list(REPOS.keys()),
            "phases": [p["id"] for p in PHASE_CATALOG],
            "inventories": {k: [x["path"] for x in v] for k, v in inventories.items()},
            "protoMessages": proto_messages,
            "symbols": {k: [s["name"] for s in v.get("symbols", [])] for k, v in sorted(extracted.items())},
        },
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(structural_payload.encode("utf-8")).hexdigest()[:16]

    graph = {
        "schemaVersion": "1.2.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "structuralFingerprint": fingerprint,
        "git": git,
        "repoRefs": repo_refs,
        "repos": REPOS,
        "phaseCatalog": PHASE_CATALOG,
        "protoStreamingMessages": proto_messages,
        "packageInventories": inventories,
        "eras": eras,
    }
    validate_graph(graph)
    return graph


def validate_graph(graph: dict[str, Any]) -> None:
    expected_phase_ids = [p["id"] for p in PHASE_CATALOG]
    for era in graph["eras"]:
        node_ids = {n["id"] for n in era["nodes"]}
        container_ids = {c["id"] for c in era["containers"]}
        for n in era["nodes"]:
            if n["containerId"] not in container_ids:
                raise ValueError(f"Node {n['id']} references missing container {n['containerId']}")
            if n["repo"] not in REPOS:
                raise ValueError(f"Node {n['id']} references unknown repo {n['repo']}")
            if n["repo"] == "python-worker" and not (REPO_ROOT / n["file"]).exists():
                raise ValueError(f"Node {n['id']} points to missing python-worker file {n['file']}")
        for e in era["edges"]:
            if e["source"] not in node_ids or e["target"] not in node_ids:
                raise ValueError(f"Edge {e['id']} in {era['id']} has invalid endpoint")

        if era["id"] in ("py312", "py313_314", "py315_r2p2"):
            got_phases = [p["id"] for p in era.get("phases", [])]
            if got_phases != expected_phase_ids:
                raise ValueError(f"Era {era['id']} phases {got_phases} != {expected_phase_ids}")
            for ph in era["phases"]:
                ph_edge_ids = {e["id"] for e in ph["topologyEdges"]}
                for e in ph["topologyEdges"]:
                    if e["source"] not in node_ids or e["target"] not in node_ids:
                        raise ValueError(f"Phase edge {e['id']} in {era['id']}.{ph['id']} invalid")
                for nid in ph["activeNodes"]:
                    if nid not in node_ids:
                        raise ValueError(f"Phase {era['id']}.{ph['id']} activeNode {nid} missing")
                actor_ids = {a["id"] for a in ph["actors"]}
                for st in ph["steps"]:
                    if st["from"] not in actor_ids or st["to"] not in actor_ids:
                        raise ValueError(f"Step actor missing in {era['id']}.{ph['id']}")
                    for nid in st["activeNodes"]:
                        if nid not in node_ids:
                            raise ValueError(f"Step activeNode {nid} missing in {era['id']}.{ph['id']}")
                    for eid in st["activeEdges"]:
                        if eid not in ph_edge_ids:
                            raise ValueError(f"Step activeEdge {eid} missing in {era['id']}.{ph['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract multi-repo architecture graph.")
    parser.add_argument(
        "--sibling-root",
        type=Path,
        default=None,
        help="Optional directory containing python-library, python-extensions, language-worker-protobuf checkouts.",
    )
    args = parser.parse_args()

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    graph = build_graph(sibling_root=args.sibling_root)
    raw_json = json.dumps(graph, indent=2)
    JSON_OUT.write_text(raw_json + "\n", encoding="utf-8")
    JS_OUT.write_text(f"window.__ARCH_GRAPH__ = {raw_json};\n", encoding="utf-8")
    print(
        f"[extract_arch] Generated {JSON_OUT.relative_to(REPO_ROOT)} & {JS_OUT.relative_to(REPO_ROOT)} "
        f"(repos={len(graph['repos'])}, eras={len(graph['eras'])}, fingerprint={graph['structuralFingerprint']})"
    )


if __name__ == "__main__":
    main()
