# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""End-to-end tests for the conditional vendored-protobuf activation.

The worker keeps a private pure-Python copy of ``google.protobuf``
under ``azure_functions_worker._vendored.google.protobuf`` that it
activates only when the customer ships their own ``google.protobuf``.
The selection is performed in ``azure_functions_worker/__init__.py``:

* No customer protobuf -> do nothing. Worker's pb2 stubs resolve
  top-level ``google.protobuf`` to the worker's own protobuf install
  on ``sys.path``. No env var is set. Vendored tree is unused.

* Customer protobuf present -> set
  ``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`` and register the
  vendored modules under their top-level ``google.protobuf`` names so
  the worker's pb2 stubs (which import top-level ``google.protobuf``)
  receive the vendored copy.

These tests cover both branches in subprocesses since the selection is
irreversible per process.
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


class TestVendoredProtobufActivation(unittest.TestCase):
    """Regression tests for the conditional vendored-protobuf bootstrap."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="vendored_pb_test_")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def _write_hostile_protobuf(self, root: Path) -> Path:
        """Create a fake ``google.protobuf`` under a simulated Azure
        Functions ``.python_packages`` tree.

        Returns the script-root path (the parent of ``.python_packages``)
        that should be passed via ``AzureWebJobsScriptRoot``.

        The stub is missing every modern symbol the worker's pb2 stubs
        reference (``runtime_version``, etc.), so any worker pb2 import
        that resolved to this stub would crash.
        """
        site_packages = (
            root / ".python_packages" / "lib" / "site-packages"
        )
        pkg = site_packages / "google" / "protobuf"
        pkg.mkdir(parents=True)
        (site_packages / "google" / "__init__.py").write_text(
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
                # would crash the worker without the vendored-fallback
                # bootstrap.
                __version__ = "4.25.3"
                """
            ).lstrip(),
            encoding="utf-8",
        )
        return root

    def _run_subprocess(
        self,
        code: str,
        *,
        extra_path: Path = None,
        script_root: str = None,
        use_vendored_override: str = None,
    ) -> subprocess.CompletedProcess:
        """Run ``code`` in a fresh interpreter with the worker on
        PYTHONPATH plus an optional ``extra_path`` prepended.

        ``use_vendored_override`` sets ``_AZFUNC_USE_VENDORED_PROTOBUF``
        in the child env when provided (``"1"`` to force activation,
        ``"0"`` to force no activation). When ``None`` (default), the
        env var is unset and the child uses the autodetect path.
        """
        env = os.environ.copy()
        path_parts = []
        if extra_path is not None:
            path_parts.append(str(extra_path))
        path_parts.append(str(WORKER_ROOT))
        existing = env.get("PYTHONPATH", "")
        if existing:
            path_parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(path_parts)
        # Don't carry parent's protobuf impl forcing — the worker's
        # __init__ sets it based on detection.
        env.pop("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", None)
        # Don't carry the launcher's vendored-protobuf override —
        # each test sets it (or leaves it unset) deliberately.
        env.pop("_AZFUNC_USE_VENDORED_PROTOBUF", None)
        if use_vendored_override is not None:
            env["_AZFUNC_USE_VENDORED_PROTOBUF"] = use_vendored_override
        if script_root is not None:
            env["AzureWebJobsScriptRoot"] = script_root
        else:
            env.pop("AzureWebJobsScriptRoot", None)
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
    def test_hostile_customer_protobuf_activates_vendored_fallback(self):
        """When the customer ships an incompatible ``google.protobuf``,
        the worker's ``__init__`` must detect that, set
        ``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python``, and alias
        the vendored modules under the top-level ``google.protobuf``
        names so the worker's pb2 stubs (which import top-level
        ``google.protobuf``) resolve to the vendored copy.
        """
        hostile_root = self._write_hostile_protobuf(Path(self.tmp_dir))
        hostile_site = (
            hostile_root / ".python_packages" / "lib" / "site-packages"
        )

        code = textwrap.dedent(
            """
            import sys
            # Sanity: the hostile google.protobuf must be discoverable
            # at the top level *before* the worker's __init__ runs.
            import google.protobuf as _customer_pb
            assert getattr(_customer_pb, "__version__", None) == "4.25.3", (
                "test setup error: hostile google.protobuf not on path"
            )

            # Importing the worker must detect the customer protobuf
            # and activate the vendored fallback.
            import os
            import azure_functions_worker  # noqa: F401  triggers detection
            assert (
                os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION")
                == "python"
            ), (
                "worker did not force pure-Python despite customer "
                "protobuf being present"
            )

            # After bootstrap, top-level google.protobuf must resolve
            # to the vendored copy — that's what redirects the pb2
            # stubs away from the hostile customer pin.
            from azure_functions_worker._vendored.google import (
                protobuf as vendored_pb,
            )
            assert sys.modules["google.protobuf"] is vendored_pb, (
                "bootstrap did not alias vendored google.protobuf"
            )

            # Worker pb2 stubs must load successfully now that
            # google.protobuf resolves to the vendored copy.
            from azure_functions_worker import protos
            msg = protos.StreamingMessage(request_id="abc")
            assert msg.request_id == "abc"
            data = msg.SerializeToString()
            roundtrip = protos.StreamingMessage()
            roundtrip.ParseFromString(data)
            assert roundtrip.request_id == "abc"
            print("OK")
            """
        )

        result = self._run_subprocess(
            code,
            extra_path=hostile_site,
            script_root=str(hostile_root),
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Worker failed under hostile customer protobuf.\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            ),
        )
        self.assertIn("OK", result.stdout)

    def test_no_customer_protobuf_does_not_touch_environment(self):
        """When the function app does not ship ``google.protobuf``,
        the worker's ``__init__`` must not touch the protobuf
        implementation env var and must not pre-import the vendored
        copy. The worker's own protobuf install handles everything.
        """
        empty_script_root = Path(self.tmp_dir) / "empty_app"
        empty_script_root.mkdir()
        # Create an empty .python_packages tree to make the detection
        # fast-path check explicitly miss (rather than relying on
        # AzureWebJobsScriptRoot being unset).
        (
            empty_script_root / ".python_packages" / "lib" / "site-packages"
        ).mkdir(parents=True)

        code = textwrap.dedent(
            """
            import os
            import sys

            # AzureWebJobsScriptRoot points at an app whose
            # .python_packages does not contain google/protobuf. The
            # detection's only check is os.path.isdir on that path, so
            # it must return False.
            import azure_functions_worker  # noqa: F401

            # The detection must not have set the env var.
            assert (
                os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION")
                is None
            ), (
                "worker forced pure-Python despite no customer "
                "protobuf being present"
            )

            # The vendored modules must not have been pre-imported
            # under their top-level names. ``google.protobuf`` may
            # still be in sys.modules if some unrelated worker import
            # touched it, but if so it must NOT be the vendored copy.
            top_pb = sys.modules.get("google.protobuf")
            if top_pb is not None:
                assert "_vendored" not in (top_pb.__file__ or ""), (
                    "vendored protobuf was activated despite no "
                    "customer protobuf being present"
                )
            print("OK")
            """
        )

        result = self._run_subprocess(
            code, script_root=str(empty_script_root)
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Worker failed under the no-customer-protobuf branch.\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            ),
        )
        self.assertIn("OK", result.stdout)

    @unittest.skipUnless(
        _vendored_protobuf_present(),
        "Vendored protobuf is not populated. Run "
        "`python eng/scripts/vendor_deps.py --target "
        "workers/azure_functions_worker/_vendored` first.",
    )
    def test_activation_does_not_shadow_other_google_packages(self):
        """Regression test for the ``google.cloud`` / ``google.auth``
        shadowing bug: aliasing ``sys.modules["google"]`` to the
        vendored package broke every other ``google.*`` namespace
        package the customer ships. The bootstrap must alias only the
        protobuf-specific names so that, for example,
        ``import google.cloud.foo`` still resolves to the customer's
        ``google`` namespace package.

        This is the most important regression to guard against because
        the most common reason customers end up with ``google.protobuf``
        in their dependency tree is precisely because they depend on
        ``google-cloud-*``, ``google-auth``, or ``google-api-core``.
        """
        # Build a fake customer site that includes both
        # google/protobuf (to trigger activation) AND google/cloud/foo
        # (to verify it stays importable after activation).
        site = (
            Path(self.tmp_dir)
            / ".python_packages"
            / "lib"
            / "site-packages"
        )
        (site / "google" / "protobuf").mkdir(parents=True)
        (site / "google" / "cloud" / "foo").mkdir(parents=True)
        (site / "google" / "__init__.py").write_text(
            "# Customer's google namespace package.\n", encoding="utf-8"
        )
        (site / "google" / "protobuf" / "__init__.py").write_text(
            '__version__ = "4.25.3"\n', encoding="utf-8"
        )
        (site / "google" / "cloud" / "__init__.py").write_text(
            "# Customer's google.cloud sub-package.\n", encoding="utf-8"
        )
        (site / "google" / "cloud" / "foo" / "__init__.py").write_text(
            'CUSTOMER_VALUE = "preserved"\n', encoding="utf-8"
        )

        code = textwrap.dedent(
            """
            import sys
            import azure_functions_worker  # noqa: F401  triggers bootstrap

            # protobuf must come from the vendored copy.
            from google.protobuf import timestamp_pb2
            assert "_vendored" in (timestamp_pb2.__file__ or ""), (
                "vendored protobuf was not activated"
            )

            # google.cloud.foo (customer-only) must still be reachable.
            import google.cloud.foo as cust
            assert cust.CUSTOMER_VALUE == "preserved", (
                "customer google.cloud.foo was shadowed by aliasing"
            )
            print("OK")
            """
        )

        result = self._run_subprocess(
            code,
            extra_path=site,
            script_root=str(Path(self.tmp_dir)),
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Worker bootstrap shadowed customer's other google.* "
                "packages after activating vendored protobuf.\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            ),
        )
        self.assertIn("OK", result.stdout)

    @unittest.skipUnless(
        _vendored_protobuf_present(),
        "Vendored protobuf is not populated. Run "
        "`python eng/scripts/vendor_deps.py --target "
        "workers/azure_functions_worker/_vendored` first.",
    )
    def test_launcher_override_forces_activation(self):
        """The local-dev launcher sets ``_AZFUNC_USE_VENDORED_PROTOBUF=1``
        before importing the worker so that the worker is isolated from
        whatever protobuf version sits in the customer's venv. This test
        simulates that path: env var set to ``"1"``, no ``.python_packages``
        layout, no customer protobuf on ``sys.path``. The worker must
        still activate the vendored fallback.
        """
        code = textwrap.dedent(
            """
            import os
            import sys
            import azure_functions_worker  # noqa: F401  triggers bootstrap

            assert (
                os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION")
                == "python"
            ), "launcher override did not force pure-Python"

            from azure_functions_worker._vendored.google import (
                protobuf as vendored_pb,
            )
            assert sys.modules["google.protobuf"] is vendored_pb, (
                "launcher override did not alias vendored google.protobuf"
            )
            print("OK")
            """
        )
        result = self._run_subprocess(code, use_vendored_override="1")
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Worker did not honor _AZFUNC_USE_VENDORED_PROTOBUF=1.\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            ),
        )
        self.assertIn("OK", result.stdout)

    def test_launcher_override_can_force_no_activation(self):
        """``_AZFUNC_USE_VENDORED_PROTOBUF=0`` is the escape hatch for
        users debugging protobuf-version-specific behavior against the
        worker's bundled protobuf. It must skip activation even when
        the canonical ``.python_packages`` layout would normally trigger
        autodetect.
        """
        hostile_root = self._write_hostile_protobuf(Path(self.tmp_dir))
        hostile_site = (
            hostile_root / ".python_packages" / "lib" / "site-packages"
        )

        code = textwrap.dedent(
            """
            import os
            import sys
            import azure_functions_worker  # noqa: F401  triggers bootstrap

            # Opt-out must beat autodetect: env var must remain unset
            # and the vendored modules must not be aliased.
            assert (
                os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION")
                is None
            ), "opt-out did not prevent forcing pure-Python"

            top_pb = sys.modules.get("google.protobuf")
            if top_pb is not None:
                assert "_vendored" not in (top_pb.__file__ or ""), (
                    "opt-out did not prevent vendored activation"
                )
            print("OK")
            """
        )
        result = self._run_subprocess(
            code,
            extra_path=hostile_site,
            script_root=str(hostile_root),
            use_vendored_override="0",
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Worker did not honor _AZFUNC_USE_VENDORED_PROTOBUF=0.\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            ),
        )
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
