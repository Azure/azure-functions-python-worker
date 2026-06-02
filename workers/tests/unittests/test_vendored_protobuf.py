# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""End-to-end test for the protobuf vendoring fix.

The bug this test guards against: on Linux Dedicated, the customer's
``.python_packages`` directory is placed before the worker's dependency
directory on ``sys.path``. If the customer pins an older ``protobuf``
that lacks ``runtime_version`` (or any other newer symbol the worker's
generated stubs reference), the worker's protos fail to import and the
process exits with code 1.

The fix: ``azure_functions_worker.protos`` imports protobuf via the
vendored copy at ``azure_functions_worker._vendored.google.protobuf``,
which is unaffected by whatever the customer ships.

This test reproduces the failure by spawning a subprocess with a stub
``google.protobuf`` on ``sys.path`` ahead of everything else, then
importing the worker's protos. With the vendoring fix in place the
import must succeed.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = WORKER_ROOT.parent
VENDORED_DIR = WORKER_ROOT / "azure_functions_worker" / "_vendored"
VENDORED_PROTOBUF = VENDORED_DIR / "google" / "protobuf" / "__init__.py"


def _vendored_protobuf_present() -> bool:
    return VENDORED_PROTOBUF.is_file()


class TestVendoredProtobuf(unittest.TestCase):
    """Regression tests for the protobuf vendoring isolation."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="vendored_pb_test_")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def _write_hostile_protobuf(self, root: Path) -> Path:
        """Create a fake ``google.protobuf`` that mimics the customer's
        broken pin.

        Importing any submodule (or even the package itself, indirectly)
        will raise ``ImportError`` for ``runtime_version`` — the same
        symptom customers see in production.
        """
        pkg = root / "google" / "protobuf"
        pkg.mkdir(parents=True)
        (root / "google" / "__init__.py").write_text(
            "# Stub namespace package that mimics a customer's pinned\n"
            "# google.protobuf<5.27 install.\n",
            encoding="utf-8",
        )
        (pkg / "__init__.py").write_text(
            textwrap.dedent(
                """
                # Hostile stub: looks like a real google.protobuf
                # package but is missing every symbol the new protoc
                # output expects. Importing anything from this module
                # would crash the worker prior to the vendoring fix.
                __version__ = "4.25.3"
                """
            ).lstrip(),
            encoding="utf-8",
        )
        return root

    def _run_in_subprocess(
        self, code: str, extra_path: Path
    ) -> subprocess.CompletedProcess:
        """Run ``code`` in a fresh interpreter with ``extra_path`` first
        on ``PYTHONPATH``."""
        env = os.environ.copy()
        # Place the hostile google.protobuf first, then the worker's
        # source directory. This mirrors the Linux Dedicated sys.path
        # order where customer .python_packages precedes worker deps.
        path_parts = [str(extra_path), str(WORKER_ROOT)]
        existing = env.get("PYTHONPATH", "")
        if existing:
            path_parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(path_parts)
        # Belt-and-braces: also force the pure-Python implementation in
        # case the test environment has the C extension cached from the
        # parent process.
        env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
        return subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    @unittest.skipUnless(
        _vendored_protobuf_present(),
        "Vendored protobuf is not populated. Run "
        "`python eng/scripts/vendor_deps.py --target "
        "workers/azure_functions_worker/_vendored` first.",
    )
    def test_worker_protos_import_with_hostile_customer_protobuf(self):
        """The worker's protos must import even when a broken
        ``google.protobuf`` shadows the worker's own protobuf."""
        hostile_root = self._write_hostile_protobuf(Path(self.tmp_dir))

        # The subprocess imports the worker's protos AND constructs a
        # message that exercises the descriptor pool. If the vendoring
        # isn't in place the import line itself raises.
        code = textwrap.dedent(
            """
            import sys
            # Sanity check: the hostile google.protobuf must be the one
            # that resolves at the top level.
            import google.protobuf as _customer_pb
            assert getattr(_customer_pb, "__version__", None) == "4.25.3", (
                "test setup error: the hostile google.protobuf is not "
                "first on sys.path"
            )

            # This is the operation that crashes today.
            from azure_functions_worker import protos
            msg = protos.StreamingMessage(request_id="abc")
            assert msg.request_id == "abc"

            # The worker's protobuf must be a *different* module instance
            # than the customer's. Otherwise the isolation is leaky.
            from azure_functions_worker._vendored.google import (
                protobuf as worker_pb,
            )
            assert worker_pb is not _customer_pb, (
                "worker and customer share the same google.protobuf "
                "instance; vendoring did not isolate them"
            )
            print("OK")
            """
        )

        result = self._run_in_subprocess(code, hostile_root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Worker failed to import protos with a hostile customer "
                f"protobuf on sys.path.\nSTDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            ),
        )
        self.assertIn("OK", result.stdout)

    @unittest.skipUnless(
        _vendored_protobuf_present(),
        "Vendored protobuf is not populated.",
    )
    def test_vendored_init_sets_pure_python_implementation(self):
        """Importing anything under the vendored namespace must guarantee
        that ``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`` is set,
        because the vendored protobuf is shipped without C extensions.
        The env var is set by ``azure_functions_worker/__init__.py``,
        which runs before any submodule (including ``_vendored``)."""
        code = textwrap.dedent(
            """
            import os
            os.environ.pop("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", None)
            import azure_functions_worker._vendored  # noqa: F401
            assert os.environ.get(
                "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"
            ) == "python"
            print("OK")
            """
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(WORKER_ROOT)
        # Avoid inheriting the parent's setting; we want to verify the
        # azure_functions_worker package __init__ installs it.
        env.pop("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
