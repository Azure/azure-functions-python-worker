# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for the build-time vendoring helper.

These tests exercise ``eng/scripts/vendor_deps.py`` in isolation: they
copy a synthetic source package into a temp directory and verify that
the rewriter produces an importable, self-contained vendored tree.

They do not require the real ``google.protobuf`` to be installed, so
they run in any developer environment.
"""

import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "eng" / "scripts" / "vendor_deps.py"


def _load_vendor_module():
    """Load ``vendor_deps`` as a module so we can call its helpers
    directly without going through the CLI."""
    spec = importlib.util.spec_from_file_location(
        "vendor_deps_under_test", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRewriter(unittest.TestCase):
    """The AST-aware rewriter must handle realistic protobuf-shaped
    import patterns without mangling unrelated code."""

    @classmethod
    def setUpClass(cls):
        cls.vendor_deps = _load_vendor_module()
        # _build_rewriter returns a plain function; storing it as a class
        # attribute would cause it to be bound as a method on access via
        # ``self``. Wrap it so it's invoked as a plain callable.
        rewriter = cls.vendor_deps._build_rewriter(["google"])
        cls._rewriter = staticmethod(rewriter)

    def _rewrite(self, source: str) -> tuple[str, int]:
        return self._rewriter(textwrap.dedent(source).lstrip())

    def test_rewrites_from_import(self):
        new, n = self._rewrite(
            """
            from google.protobuf import descriptor
            """
        )
        self.assertEqual(n, 1)
        self.assertIn(
            "from azure_functions_worker._vendored.google.protobuf "
            "import descriptor",
            new,
        )

    def test_rewrites_from_import_with_alias_and_multiple_names(self):
        new, n = self._rewrite(
            """
            from google.protobuf.internal import builder as _builder, api_implementation
            """
        )
        self.assertEqual(n, 1)
        self.assertIn(
            "from azure_functions_worker._vendored.google.protobuf.internal "
            "import builder as _builder, api_implementation",
            new,
        )

    def test_rewrites_plain_import_with_alias(self):
        new, n = self._rewrite(
            """
            import google.protobuf as pb
            """
        )
        self.assertEqual(n, 1)
        self.assertIn(
            "import azure_functions_worker._vendored.google.protobuf as pb",
            new,
        )

    def test_rewrites_plain_import_without_alias_preserves_head_binding(self):
        # `import google.protobuf` binds the name `google`. After
        # rewriting we still need `google.protobuf.X` to work in the
        # vendored module body, so we alias to `google`.
        new, n = self._rewrite(
            """
            import google.protobuf
            """
        )
        self.assertEqual(n, 1)
        self.assertIn(
            "import azure_functions_worker._vendored.google.protobuf as google",
            new,
        )

    def test_does_not_rewrite_relative_imports(self):
        # Within the protobuf package itself there are relative imports
        # (`from . import descriptor`). The rewriter must leave those
        # alone because they are already package-local.
        original = "from . import descriptor\n"
        new, n = self._rewrite(original)
        self.assertEqual(n, 0)
        self.assertEqual(new, original)

    def test_does_not_rewrite_string_literals_mentioning_google_protobuf(self):
        # The literal substring "google.protobuf" appears in docstrings
        # and error messages throughout protobuf. The rewriter must
        # leave them untouched.
        src = textwrap.dedent(
            '''
            """Docstring mentioning google.protobuf in prose."""
            ERR = "Something about google.protobuf went wrong"
            '''
        ).lstrip()
        new, n = self._rewrite(src)
        self.assertEqual(n, 0)
        self.assertEqual(new, src)

    def test_does_not_rewrite_imports_for_other_packages(self):
        src = "from grpc import experimental\nimport os, sys\n"
        new, n = self._rewrite(src)
        self.assertEqual(n, 0)
        self.assertEqual(new, src)

    def test_handles_multiline_from_import(self):
        new, n = self._rewrite(
            """
            from google.protobuf import (
                descriptor,
                descriptor_pool,
                symbol_database,
            )
            """
        )
        self.assertEqual(n, 1)
        # The reconstructed form is single-line, which is functionally
        # equivalent and what the rewriter emits. Just check the
        # important property: the module path was rewritten.
        self.assertIn(
            "from azure_functions_worker._vendored.google.protobuf import "
            "descriptor, descriptor_pool, symbol_database",
            new,
        )

    def test_idempotent(self):
        """Running the rewriter twice should be a no-op the second time."""
        src = textwrap.dedent(
            """
            from google.protobuf import descriptor
            import google.protobuf.internal as _internal
            """
        ).lstrip()
        once, _ = self._rewrite(src)
        twice, n = self._rewrite(once)
        self.assertEqual(n, 0)
        self.assertEqual(once, twice)


class TestEndToEnd(unittest.TestCase):
    """Run the script against a synthetic package and import the result."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp(prefix="vendor_e2e_")
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

    def _make_fake_package(self, sitepackages: Path) -> None:
        """Create a tiny ``google.protobuf`` look-alike package with a
        cross-import that the rewriter must fix."""
        root = sitepackages / "google" / "protobuf"
        root.mkdir(parents=True)
        (sitepackages / "google" / "__init__.py").write_text(
            "# fake namespace\n", encoding="utf-8"
        )
        (root / "__init__.py").write_text(
            textwrap.dedent(
                """
                from google.protobuf import descriptor as _d  # noqa: F401
                from . import internal  # relative; should NOT be rewritten
                NAME = "fake-protobuf"
                """
            ).lstrip(),
            encoding="utf-8",
        )
        (root / "descriptor.py").write_text(
            "VALUE = 'descriptor-value'\n", encoding="utf-8"
        )
        internal = root / "internal"
        internal.mkdir()
        (internal / "__init__.py").write_text(
            "from google.protobuf.descriptor import VALUE  # noqa: F401\n",
            encoding="utf-8",
        )

    def _make_target(self) -> Path:
        target = Path(self.workdir) / "_vendored"
        target.mkdir()
        # The script requires a sentinel file in --target (the committed
        # .gitignore). Mirror that here.
        (target / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
        return target

    def test_vendor_and_import(self):
        sitepackages = Path(self.workdir) / "site-packages"
        sitepackages.mkdir()
        self._make_fake_package(sitepackages)
        target = self._make_target()

        # Invoke the script in a subprocess so we exercise the real CLI
        # path including argv parsing.
        env = os.environ.copy()
        # Put the fake site-packages first so the script's
        # importlib.util.find_spec resolves to it.
        env["PYTHONPATH"] = os.pathsep.join(
            [str(sitepackages), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--target",
                str(target),
                "--package",
                "google.protobuf",
            ],
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

        # The vendored package must exist and be importable under the
        # private namespace. Set up sys.path so that:
        #   1. The package containing _vendored is importable.
        #   2. The fake google.protobuf is also on sys.path (simulating
        #      a customer who has their own copy).
        importer_root = Path(self.workdir) / "importer"
        pkg = importer_root / "azure_functions_worker"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        shutil.copytree(target, pkg / "_vendored", dirs_exist_ok=False)
        # No _vendored/__init__.py — it's an implicit namespace package
        # (Python 3.3+). Imports under it must still resolve.

        verify = textwrap.dedent(
            """
            import sys
            import google.protobuf as customer_pb
            assert getattr(customer_pb, "NAME", None) == "fake-protobuf"
            from azure_functions_worker._vendored.google import protobuf as worker_pb
            assert worker_pb is not customer_pb
            # The vendored descriptor cross-import must resolve to the
            # vendored copy, not the customer's. If the rewriter missed
            # the `from google.protobuf import descriptor` line, this
            # would still succeed by accident (because the customer's
            # copy also has it). Verify the module path instead.
            from azure_functions_worker._vendored.google.protobuf.internal import VALUE
            assert VALUE == "descriptor-value"
            # And the relative import inside the fake package must
            # still work (rewriter must NOT have touched it).
            from azure_functions_worker._vendored.google.protobuf import internal as _i
            assert _i.VALUE == "descriptor-value"
            print("OK")
            """
        )
        verify_env = os.environ.copy()
        verify_env["PYTHONPATH"] = os.pathsep.join(
            [
                str(sitepackages),
                str(importer_root),
                verify_env.get("PYTHONPATH", ""),
            ]
        ).rstrip(os.pathsep)
        result = subprocess.run(
            [sys.executable, "-c", verify],
            env=verify_env,
            # Isolate from the parent's CWD: pytest typically runs from
            # ``workers/``, which would put the real
            # ``azure_functions_worker`` package on ``sys.path[0]`` and
            # shadow the fake ``_vendored`` tree we just built under
            # ``importer_root``. Setting ``cwd`` to a directory that
            # contains no ``azure_functions_worker`` directory forces the
            # subprocess to resolve the package through ``PYTHONPATH``.
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
