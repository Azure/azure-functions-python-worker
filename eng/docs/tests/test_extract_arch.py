# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for the multi-repo architecture graph extractor (`eng/docs/extract_arch.py`)."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXTRACTOR_PATH = REPO_ROOT / "eng" / "docs" / "extract_arch.py"

SPEC = importlib.util.spec_from_file_location("extract_arch", EXTRACTOR_PATH)
extract_arch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(extract_arch)


class TestExtractArch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = extract_arch.build_graph()

    def test_four_linked_repositories_present(self) -> None:
        self.assertEqual(
            set(self.graph["repos"].keys()),
            {
                "python-worker",
                "python-library",
                "python-extensions",
                "language-worker-protobuf",
            },
        )

    def test_three_worker_eras_each_have_all_seven_phases(self) -> None:
        expected_phases = [
            "init",
            "specialization",
            "metadata",
            "function_load",
            "invocation",
            "worker_status",
            "worker_logs",
        ]
        eras_by_id = {e["id"]: e for e in self.graph["eras"]}
        for era_id in ("py312", "py313_314", "py315_r2p2"):
            self.assertIn(era_id, eras_by_id)
            era = eras_by_id[era_id]
            self.assertEqual([p["id"] for p in era["phases"]], expected_phases)
            for phase in era["phases"]:
                self.assertTrue(phase["topologyEdges"])
                self.assertTrue(phase["steps"])
                self.assertIn("flowchart LR", phase["topologyMermaid"])
                self.assertIn("sequenceDiagram", phase["sequenceMermaid"])

    def test_live_rust_and_proto_extraction(self) -> None:
        self.assertGreaterEqual(len(self.graph["protoStreamingMessages"]), 20)
        eras_by_id = {e["id"]: e for e in self.graph["eras"]}
        r2p2_nodes = {n["id"]: n for n in eras_by_id["py315_r2p2"]["nodes"]}
        router_syms = {s["name"] for s in r2p2_nodes["n315-router"]["extractedSymbols"]}
        self.assertIn("process_message", router_syms)

    def test_structural_fingerprint_is_deterministic(self) -> None:
        second = extract_arch.build_graph()
        self.assertEqual(
            self.graph["structuralFingerprint"], second["structuralFingerprint"]
        )

    def test_sibling_root_extracts_external_python_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib_dir = Path(tmp) / "python-library" / "azure" / "functions"
            lib_dir.mkdir(parents=True)
            (lib_dir / "meta.py").write_text(
                "class Datum:\n    def value(self):\n        return None\n",
                encoding="utf-8",
            )
            graph = extract_arch.build_graph(sibling_root=Path(tmp))
            eco = next(e for e in graph["eras"] if e["id"] == "ecosystem")
            datum_node = next(n for n in eco["nodes"] if n["id"] == "ne-lib-datum")
            sym_names = [s["name"] for s in datum_node["extractedSymbols"]]
            self.assertIn("Datum", sym_names)

    def test_class_method_line_lookup_avoids_fallback(self) -> None:
        proxy_meta = extract_arch.extract_python_file(
            "workers/proxy_worker/dispatcher.py"
        )
        mono_meta = extract_arch.extract_python_file(
            "workers/azure_functions_worker/dispatcher.py"
        )
        self.assertGreater(extract_arch.sym_line(proxy_meta, "__poll_grpc", -1), 1)
        self.assertGreater(
            extract_arch.sym_line(proxy_meta, "_dispatch_grpc_request", -1), 1
        )
        self.assertGreater(extract_arch.sym_line(mono_meta, "connect", -1), 1)

    def test_validate_graph_rejects_dangling_phase_edge(self) -> None:
        broken = copy.deepcopy(self.graph)
        py315 = next(e for e in broken["eras"] if e["id"] == "py315_r2p2")
        py315["phases"][0]["topologyEdges"][0]["target"] = "non-existent-node"
        with self.assertRaises(ValueError):
            extract_arch.validate_graph(broken)


if __name__ == "__main__":
    unittest.main()
