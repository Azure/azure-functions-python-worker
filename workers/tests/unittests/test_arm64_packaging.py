# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Packaging regressions, runnable without ARM64 wheels or a Functions host."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "eng" / "pack" / "scripts"
VALIDATOR = SCRIPTS / "validate_worker_payload.py"
PACKAGES = ("azure_functions_worker", "proxy_worker")
PROTOS = (
    "FunctionRpc_pb2", "FunctionRpc_pb2_grpc",
    "identity/ClaimsIdentityRpc_pb2", "identity/ClaimsIdentityRpc_pb2_grpc",
    "shared/NullableTypes_pb2", "shared/NullableTypes_pb2_grpc",
)


class TestArm64PayloadValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def make_payload(self, package):
        version = (3, 12) if package == "azure_functions_worker" else (3, 14)
        spec = importlib.util.spec_from_file_location("payload_validator", VALIDATOR)
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        files, directories = validator.expected_contents(version, "LINUX")
        for name in files:
            self.write(name)
        for name in directories:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.write(f"grpc/_cython/cygrpc.cpython-{version[0]}{version[1]}-test.so")
        entry = "main" if package == "azure_functions_worker" else "start_worker"
        for name in (
            "__init__", "__main__", entry, "dispatcher", "utils/__init__",
            "utils/dependency", "protos/__init__",
            "_vendored/google/protobuf/__init__",
        ):
            self.write(f"{package}/{name}.py")
        for proto in PROTOS:
            self.write(f"{package}/protos/{proto}.py")
        for name in (
            "grpc/__init__", "grpc/_cython/__init__", "grpc/_cython/cygrpc",
            "google/__init__", "google/protobuf/__init__",
            "azure/__init__", "azure/functions/__init__",
        ):
            self.write(f"{name}.py")
        self.write("worker.py", (
            "import argparse, sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).parent))\n"
            f"from {package} import {entry}\n"
            "argparse.ArgumentParser().parse_args()\n"
        ))

    def validate(self, package, env=None):
        # Test synthetic imports on any host Python. The production CLI
        # additionally requires a matching interpreter before importing.
        code = (
            "import runpy, sys; "
            "validator = runpy.run_path(sys.argv[1]); "
            "version = (3, 12) if sys.argv[3] == 'azure_functions_worker' "
            "else (3, 14); "
            "validator['validate_contents'](sys.argv[2], version, 'LINUX', "
            "'x64', 'test.so'); "
            "validator['validate_imports'](sys.argv[2], sys.argv[3])"
        )
        return subprocess.run(
            [sys.executable, "-I", "-S", "-c", code,
             str(VALIDATOR), str(self.root), package],
            capture_output=True, text=True, env=env, timeout=30,
        )

    def test_complete_payload_and_launcher_import_for_both_workers(self):
        for package in PACKAGES:
            with self.subTest(package=package):
                self.make_payload(package)
                result = self.validate(package)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"Imported {package}.dispatcher", result.stdout)
                self.assertIn("--help", result.stdout)

    def test_rejects_missing_executable_modules(self):
        for package in PACKAGES:
            entry = "main" if package == "azure_functions_worker" else "start_worker"
            for name in ("__init__", "__main__", entry, "dispatcher",
                         "utils/dependency"):
                with self.subTest(package=package, module=name):
                    self.make_payload(package)
                    (self.root / package / f"{name}.py").unlink()
                    result = self.validate(package)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"{package}/{name}.py", result.stderr)

    def test_rejects_proto_only_payloads(self):
        for package in PACKAGES:
            with self.subTest(package=package):
                self.make_payload(package)
                for path in (self.root / package).glob("*.py"):
                    path.unlink()
                result = self.validate(package)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Missing worker payload files", result.stderr)

    def test_rejects_missing_generated_module(self):
        for package in PACKAGES:
            with self.subTest(package=package):
                self.make_payload(package)
                (self.root / package / "protos/shared/NullableTypes_pb2.py").unlink()
                result = self.validate(package)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("shared/NullableTypes_pb2.py", result.stderr)

    def test_rejects_missing_vendored_protobuf(self):
        self.make_payload("azure_functions_worker")
        vendored = self.root / "azure_functions_worker/_vendored/google/protobuf"
        (vendored / "__init__.py").unlink()
        result = self.validate("azure_functions_worker")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("_vendored/google/protobuf", result.stderr)

    def test_generated_runtime_errors_are_not_suppressed(self):
        # Simulate the import-time guards emitted by protoc and grpcio-tools.
        for package in PACKAGES:
            for proto, error in (
                ("FunctionRpc_pb2", "incompatible Protobuf Gencode/Runtime"),
                ("FunctionRpc_pb2_grpc", "generated code requires newer grpcio"),
            ):
                with self.subTest(package=package, proto=proto):
                    self.make_payload(package)
                    self.write(f"{package}/protos/{proto}.py",
                               f"raise RuntimeError({error!r})\n")
                    result = self.validate(package)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(error, result.stderr)

    def test_pythonpath_cannot_supply_missing_dependencies(self):
        self.make_payload("proxy_worker")
        self.write("host-only/grpc/__init__.py")
        self.write("host-only/grpc/_cython/__init__.py")
        self.write("host-only/grpc/_cython/cygrpc.py")
        (self.root / "grpc/_cython/cygrpc.py").unlink()
        env = dict(os.environ, PYTHONPATH=str(self.root / "host-only"))
        result = self.validate("proxy_worker", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grpc._cython.cygrpc", result.stderr)

    def test_rejects_broken_launcher(self):
        self.make_payload("proxy_worker")
        self.write("worker.py", "raise RuntimeError('launcher is broken')\n")
        result = self.validate("proxy_worker")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("launcher is broken", result.stderr)


class TestArm64PackagingWorkflow(unittest.TestCase):
    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("pip", "setuptools", "wheel")),
        "Offline wheel build requires pip, setuptools and wheel",
    )
    def test_built_worker_wheel_contains_both_executable_packages(self):
        # Build from clean sources, not workers/build or a previously installed
        # editable worker. No feed access or ARM64 interpreter is needed here.
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "worker"
            project.mkdir()
            workers = REPO_ROOT / "workers"
            for name in ("pyproject.toml", "README.md"):
                shutil.copy2(workers / name, project / name)
            shutil.copy2(REPO_ROOT / "LICENSE", project / "LICENSE")
            for package in PACKAGES:
                shutil.copytree(
                    workers / package, project / package,
                    ignore=shutil.ignore_patterns("__pycache__", "_src", "_vendored"),
                )
            wheels = Path(temp) / "wheels"
            result = subprocess.run(
                [sys.executable, "-m", "pip", "wheel", "--no-index",
                 "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheels),
                 str(project)],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            built = list(wheels.glob("azure_functions_worker-*.whl"))
            self.assertEqual(len(built), 1)
            downloaded = Path(temp) / "downloaded"
            result = subprocess.run(
                [sys.executable, "-m", "pip", "download", "--no-index",
                 "--no-deps", "--platform", "manylinux_2_17_aarch64",
                 "--only-binary=:all:", "--dest", str(downloaded), str(built[0])],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # Unlike a local source directory, the local wheel is saved by
            # pip download and therefore reaches the payload extraction loop.
            with ZipFile(downloaded / built[0].name) as wheel:
                contents = set(wheel.namelist())
            for name in (
                "azure_functions_worker/__init__.py",
                "azure_functions_worker/__main__.py",
                "azure_functions_worker/main.py",
                "azure_functions_worker/dispatcher.py",
                "proxy_worker/__init__.py",
                "proxy_worker/__main__.py",
                "proxy_worker/start_worker.py",
                "proxy_worker/dispatcher.py",
            ):
                self.assertIn(name, contents)

    def test_stable_and_rc_share_the_same_implementation(self):
        for name in ("nix_arm64_deps.sh", "rc_nix_arm64_deps.sh"):
            with self.subTest(script=name):
                script = (SCRIPTS / name).read_text(encoding="utf-8")
                self.assertIn('source "$(dirname "${BASH_SOURCE[0]}")/'
                              'nix_arm64_deps_common.sh" "$@"', script)

    def test_local_wheel_and_matching_generator_versions_are_downloaded(self):
        script = (SCRIPTS / "nix_arm64_deps_common.sh").read_text(encoding="utf-8")
        self.assertIn("python -m pip install . invoke", script)
        self.assertIn('("grpcio", "grpcio-tools", "protobuf")', script)
        self.assertIn('--constraint "$work_dir/proto-constraints.txt"', script)
        self.assertIn('"$work_dir/worker-wheel"/*.whl', script)
        self.assertLess(script.index("build-protos"), script.index("pip wheel"))
        self.assertLess(script.index("pip wheel"), script.index("pip download \\\n"))

    def test_final_artifact_is_validated_with_isolated_arm64_python(self):
        template = (REPO_ROOT / "eng/pack/templates/nix_arm64_env_gen.yml").read_text(
            encoding="utf-8")
        self.assertIn("--platform linux/arm64", template)
        self.assertIn("python -I -S /validation/validate_worker_payload.py", template)
        self.assertIn(
            "source=$(Build.ArtifactStagingDirectory),target=/payload,readonly",
            template,
        )
        self.assertIn("--os LINUX --architecture arm64", template)
        self.assertIn("--check-imports", template)