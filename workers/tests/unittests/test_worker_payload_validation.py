# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Portable, standard-library-only tests of staged worker validation.

Fixtures describe the artifact contract independently of expected_contents().
Native headers are data, never executed, so every target runs on any host.
"""

import contextlib
import importlib.util
import io
import itertools
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "eng/pack/scripts/validate_worker_payload.py"
TEMPLATES = REPO_ROOT / "eng/pack/templates"
SPEC = importlib.util.spec_from_file_location("worker_payload_validator", VALIDATOR)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

LEGACY = "azure_functions_worker"
PROXY = "proxy_worker"
RUNTIMES = ("azure_functions_runtime", "azure_functions_runtime_v1")
PROTOS = (
    "FunctionRpc_pb2", "FunctionRpc_pb2_grpc",
    "identity/ClaimsIdentityRpc_pb2", "identity/ClaimsIdentityRpc_pb2_grpc",
    "shared/NullableTypes_pb2", "shared/NullableTypes_pb2_grpc",
)
TARGETS = tuple(itertools.product(
    ("WINDOWS", "LINUX", "OSX"), ("x86", "x64", "arm64"),
))


def manifest(package, os_name):
    """Explicit staging contract; do not derive fixtures from the validator."""
    files = ["worker.py"]
    directories = ["azure", "azurefunctions"]
    if package == "r2p2":
        files += [
            "r2p2.exe" if os_name == "WINDOWS" else "r2p2",
            "bridge/bridge.py", "bridge/protos_adapter.py",
            "azure_functions_runtime/native_invocation.py",
            "azure_functions_runtime/utils/executor.py",
            "azure_functions_runtime_v1/native_invocation.py",
            "azure_functions_runtime_v1/utils/executor.py",
        ]
        directories += list(RUNTIMES)
    else:
        files += [".artifactignore", "six.py"]
        directories += [
            "google", "grpc", "markupsafe", "werkzeug", package,
            f"{package}/protos/_src",
        ]
        entry = "main.py" if package == LEGACY else "start_worker.py"
        files += [f"{package}/{name}" for name in (
            "__init__.py", "__main__.py", entry, "dispatcher.py",
            "utils/dependency.py", "protos/__init__.py",
        )]
        files += [f"{package}/protos/{name}.py" for name in PROTOS]
        if package == LEGACY:
            directories += ["dateutil"]
            files += [f"{package}/_vendored/google/protobuf/__init__.py"]
        else:
            directories += list(RUNTIMES)
    return files, directories


def pe_image(architecture):
    # DOS e_lfanew -> PE signature -> IMAGE_FILE_HEADER.Machine.
    image = bytearray(128)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 60, 64)
    image[64:68] = b"PE\0\0"
    machine = {"x86": 0x14c, "x64": 0x8664, "arm64": 0xaa64}[architecture]
    struct.pack_into("<H", image, 68, machine)
    return bytes(image)


def elf_image(architecture):
    image = bytearray(64)
    image[:7] = b"\x7fELF" + bytes((1 if architecture == "x86" else 2, 1, 1))
    # e_type = ET_EXEC; e_machine follows at offset 18.
    struct.pack_into("<HHI", image, 16, 2, {
        "x86": 3, "x64": 62, "arm64": 183,
    }[architecture], 1)
    return bytes(image)


def macho_image(architecture, endian="<"):
    cpu = {"x86": 7, "x64": 0x01000007, "arm64": 0x0100000c}[architecture]
    magic = 0xfeedface if architecture == "x86" else 0xfeedfacf
    header = struct.pack(endian + "7I", magic, cpu, 0, 2, 0, 0, 0)
    return header if architecture == "x86" else header + bytes(4)


def fat_image(architectures, endian=">", wide=False):
    # fat_header and fat_arch/fat_arch_64 records, followed by thin images.
    images = [macho_image(arch) for arch in architectures]
    offset = 8 + len(images) * (32 if wide else 20)
    header = struct.pack(endian + "II", 0xcafebabf if wide else 0xcafebabe,
                         len(images))
    records = []
    for arch, image in zip(architectures, images):
        cpu = {"x86": 7, "x64": 0x01000007, "arm64": 0x0100000c}[arch]
        values = (cpu, 0, offset, len(image), 0)
        if wide:
            values += (0,)
        records.append(struct.pack(endian + ("IIQQII" if wide else "IIIII"),
                                   *values))
        offset += len(image)
    return header + b"".join(records) + b"".join(images)


def native_image(os_name, architecture):
    return {"WINDOWS": pe_image, "LINUX": elf_image,
            "OSX": macho_image}[os_name](architecture)


class PayloadTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        self.counter = itertools.count()
        self.output = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.output))

    def payload(self, package=LEGACY, os_name="LINUX", architecture="x64",
                grpc_name="cygrpc.cpython-312-test.so"):
        root = self.workspace / f"payload with spaces {next(self.counter)}"
        root.mkdir()
        files, directories = manifest(package, os_name)
        for directory in directories:
            (root / directory).mkdir(parents=True, exist_ok=True)
        for name in files:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")
        if package == "r2p2":
            name = "r2p2.exe" if os_name == "WINDOWS" else "r2p2"
            (root / name).write_bytes(native_image(os_name, architecture))
        elif grpc_name is not None:
            directory = root / "grpc/_cython"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / grpc_name).write_bytes(b"not executed by layout checks")
        return root

    def contents(self, root, version=(3, 12), os_name="LINUX",
                 architecture="x64", grpc_build="test.so"):
        validator.validate_contents(root, version, os_name, architecture,
                                    grpc_build)

    def cli(self, root, version="3.12", os_name="LINUX", architecture="x64",
            grpc_build="test.so", check_imports=False):
        command = [sys.executable, "-I", "-S", str(VALIDATOR), str(root),
                   "--python-version", version, "--os", os_name,
                   "--architecture", architecture]
        if grpc_build is not None:
            command += ["--grpc-build", grpc_build]
        if check_imports:
            command += ["--check-imports"]
        return subprocess.run(command, capture_output=True, text=True,
                              timeout=30, cwd=self.workspace)


class TestVersionSelection(unittest.TestCase):
    def test_supported_versions_select_the_right_worker(self):
        cases = ((10, LEGACY), (11, LEGACY), (12, LEGACY),
                 (13, PROXY), (14, PROXY), (15, "r2p2"), (16, "r2p2"),
                 (100, "r2p2"))
        for minor, package in cases:
            for suffix in ("", ".0", ".12", ".0rc2", "rc1", ".0a3", ".0b1"):
                value = f"3.{minor}{suffix}"
                with self.subTest(value=value):
                    version = validator.parse_python_version(value)
                    self.assertEqual(version, (3, minor))
                    self.assertEqual(validator.worker_package(version), package)

    def test_invalid_and_unsupported_versions_are_rejected(self):
        for value in ("", "3", "3.", "v3.12", " 3.12", "three.12", "3.x"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Invalid Python version"):
                    validator.parse_python_version(value)
        for value in ("2.7", "3.0", "3.9.20", "4.0", "30.12"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Unsupported Python"):
                    validator.parse_python_version(value)


class TestPayloadManifests(PayloadTestCase):
    def test_manifests_equal_independent_staging_contract(self):
        for minor, package in ((10, LEGACY), (11, LEGACY), (12, LEGACY),
                               (13, PROXY), (14, PROXY), (15, "r2p2"),
                               (16, "r2p2")):
            for os_name in ("WINDOWS", "LINUX", "OSX"):
                with self.subTest(minor=minor, os_name=os_name):
                    files, directories = validator.expected_contents(
                        (3, minor), os_name)
                    wanted_files, wanted_dirs = manifest(package, os_name)
                    self.assertCountEqual(files, wanted_files)
                    self.assertCountEqual(directories, wanted_dirs)

    def test_complete_legacy_and_proxy_payloads_on_every_target(self):
        for minor, package in ((10, LEGACY), (11, LEGACY), (12, LEGACY),
                               (13, PROXY), (14, PROXY)):
            for os_name, architecture in TARGETS:
                with self.subTest(minor=minor, target=(os_name, architecture)):
                    root = self.payload(package, os_name, architecture,
                                        f"cygrpc.cpython-3{minor}-test.so")
                    self.contents(root, (3, minor), os_name, architecture)
                    self.assertIn(f"Validated {package}", self.output.getvalue())

    def test_complete_r2p2_payloads_on_every_target_without_grpc(self):
        for os_name, architecture in TARGETS:
            with self.subTest(target=(os_name, architecture)):
                root = self.payload("r2p2", os_name, architecture)
                self.contents(root, (3, 15), os_name, architecture, None)

    def test_each_required_file_is_checked_as_a_file(self):
        for package, version in ((LEGACY, (3, 12)), (PROXY, (3, 14)),
                                 ("r2p2", (3, 15))):
            for name in manifest(package, "LINUX")[0]:
                for replacement in ("missing", "directory"):
                    with self.subTest(package=package, name=name,
                                      replacement=replacement):
                        root = self.payload(package)
                        path = root / name
                        path.unlink()
                        if replacement == "directory":
                            path.mkdir()
                        with self.assertRaisesRegex(
                                RuntimeError, "Missing worker payload") as caught:
                            self.contents(root, version)
                        self.assertIn(name, str(caught.exception))

    def test_each_required_directory_is_checked_as_a_directory(self):
        for package, version in ((LEGACY, (3, 12)), (PROXY, (3, 14)),
                                 ("r2p2", (3, 15))):
            for name in manifest(package, "LINUX")[1]:
                for replacement in ("missing", "file"):
                    with self.subTest(package=package, name=name,
                                      replacement=replacement):
                        root = self.payload(package)
                        path = root / name
                        shutil.rmtree(path)
                        if replacement == "file":
                            path.write_bytes(b"")
                        with self.assertRaisesRegex(
                                RuntimeError, "Missing worker payload") as caught:
                            self.contents(root, version)
                        self.assertIn(name + "/", str(caught.exception))

    def test_missing_items_are_reported_together(self):
        root = self.payload()
        (root / "worker.py").unlink()
        (root / "six.py").unlink()
        (root / "azure").rmdir()
        with self.assertRaisesRegex(RuntimeError, "Missing worker payload") as caught:
            self.contents(root)
        for name in ("worker.py", "six.py", "azure/"):
            self.assertIn(name, str(caught.exception))

    def test_r2p2_rejects_each_pruned_package_as_file_or_directory(self):
        for name in (LEGACY, PROXY, "grpc", "uvloop"):
            for kind in ("file", "directory"):
                with self.subTest(name=name, kind=kind):
                    root = self.payload("r2p2")
                    path = root / name
                    path.mkdir() if kind == "directory" else path.touch()
                    with self.assertRaisesRegex(
                            RuntimeError, "Pruned packages unexpectedly present"
                    ) as caught:
                        self.contents(root, (3, 15), grpc_build=None)
                    self.assertIn(name, str(caught.exception))

    def test_r2p2_requires_the_platform_specific_executable(self):
        for os_name, expected, wrong in (
                ("WINDOWS", "r2p2.exe", "r2p2"),
                ("LINUX", "r2p2", "r2p2.exe"),
                ("OSX", "r2p2", "r2p2.exe")):
            with self.subTest(os_name=os_name):
                root = self.payload("r2p2", os_name)
                (root / expected).rename(root / wrong)
                with self.assertRaisesRegex(RuntimeError, "Missing worker payload"):
                    self.contents(root, (3, 15), os_name)

    def test_r2p2_contents_rejects_wrong_binary_architecture(self):
        root = self.payload("r2p2", "WINDOWS", "x86")
        with self.assertRaisesRegex(RuntimeError, "does not target WINDOWS arm64"):
            self.contents(root, (3, 15), "WINDOWS", "arm64", None)


class TestGrpcFilenames(PayloadTestCase):
    def test_platform_and_prerelease_extension_names(self):
        # Literal filenames model wheel extensions, not the validator's glob.
        cases = (
            ("WINDOWS", "x86", "3.10", LEGACY,
             "cygrpc.cp310-win32.pyd", "win32.pyd"),
            ("WINDOWS", "x64", "3.12.10", LEGACY,
             "cygrpc.cp312-win_amd64.pyd", "win_amd64.pyd"),
            ("WINDOWS", "arm64", "3.14.0rc2", PROXY,
             "cygrpc.cp314-win_arm64.pyd", "win_arm64.pyd"),
            ("LINUX", "x64", "3.11", LEGACY,
             "cygrpc.cpython-311-x86_64-linux-gnu.so", "x86_64-linux-gnu.so"),
            ("LINUX", "arm64", "3.13.0rc1", PROXY,
             "cygrpc.cpython-313-aarch64-linux-gnu.so", "aarch64-linux-gnu.so"),
            ("LINUX", "arm64", "3.14.0rc2", PROXY,
             "cygrpc.cpython-314rc2-aarch64-linux-gnu.so", "aarch64-linux-gnu.so"),
            ("OSX", "x64", "3.12", LEGACY,
             "cygrpc.cpython-312-darwin.so", "darwin.so"),
            ("OSX", "arm64", "3.14.0b1", PROXY,
             "cygrpc.cpython-314-darwin.so", "darwin.so"),
        )
        for os_name, architecture, value, package, filename, build in cases:
            with self.subTest(filename=filename):
                root = self.payload(package, os_name, architecture, filename)
                self.contents(root, validator.parse_python_version(value),
                              os_name, architecture, build)

    def test_missing_and_wrong_abi_or_platform_extensions_fail(self):
        cases = (
            ("WINDOWS", "win_amd64.pyd", "cygrpc.cp311-win_amd64.pyd"),
            ("WINDOWS", "win_amd64.pyd", "cygrpc.cp312-win32.pyd"),
            ("LINUX", "aarch64-linux-gnu.so",
             "cygrpc.cpython-311-aarch64-linux-gnu.so"),
            ("LINUX", "aarch64-linux-gnu.so",
             "cygrpc.cpython-312-x86_64-linux-gnu.so"),
            ("OSX", "darwin.so", "cygrpc.cpython-311-darwin.so"),
            ("OSX", "darwin.so", "cygrpc.cpython-312-x86_64-linux-gnu.so"),
        )
        for os_name, build, wrong_name in cases:
            for filename in (None, wrong_name):
                with self.subTest(os_name=os_name, filename=filename):
                    root = self.payload(os_name=os_name, grpc_name=filename)
                    with self.assertRaisesRegex(RuntimeError, "Missing gRPC binary"):
                        self.contents(root, os_name=os_name, grpc_build=build)

    def test_legacy_and_proxy_require_grpc_build_argument(self):
        for package, version in ((LEGACY, (3, 12)), (PROXY, (3, 14))):
            for build in (None, ""):
                with self.subTest(package=package, build=build):
                    root = self.payload(package)
                    with self.assertRaisesRegex(ValueError, "--grpc-build is required"):
                        self.contents(root, version, grpc_build=build)

    def test_grpc_binary_must_be_in_cython_directory(self):
        root = self.payload()
        (root / "grpc/_cython/cygrpc.cpython-312-test.so").rename(
            root / "grpc/cygrpc.cpython-312-test.so")
        with self.assertRaisesRegex(RuntimeError, "Missing gRPC binary"):
            self.contents(root)

    def test_grpc_binary_cannot_be_a_directory(self):
        root = self.payload()
        path = root / "grpc/_cython/cygrpc.cpython-312-test.so"
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(RuntimeError, "Missing gRPC binary"):
            self.contents(root)


class TestNativeBinaryHeaders(PayloadTestCase):
    def binary(self, data):
        path = self.workspace / "native binary"
        path.write_bytes(data)
        return path

    def test_pe_elf_and_thin_macho_match_only_the_declared_architecture(self):
        for os_name, actual_arch in TARGETS:
            path = self.binary(native_image(os_name, actual_arch))
            for requested in ("x86", "x64", "arm64"):
                with self.subTest(os_name=os_name, actual=actual_arch,
                                  requested=requested):
                    if requested == actual_arch:
                        validator.validate_binary(path, os_name, requested)
                    else:
                        with self.assertRaisesRegex(
                                RuntimeError, f"does not target {os_name} {requested}"):
                            validator.validate_binary(path, os_name, requested)

    def test_thin_macho_both_byte_orders_and_word_sizes(self):
        for endian, arch in itertools.product(("<", ">"), ("x86", "x64", "arm64")):
            with self.subTest(endian=endian, arch=arch):
                path = self.binary(macho_image(arch, endian))
                validator.validate_binary(path, "OSX", arch)

    def test_fat_macho_all_magic_encodings_and_architecture_membership(self):
        for endian, wide in itertools.product(("<", ">"), (False, True)):
            for members in (("x86", "x64"), ("x64", "arm64"),
                            ("x86", "arm64"), ("x86", "x64", "arm64")):
                path = self.binary(fat_image(members, endian, wide))
                for requested in ("x86", "x64", "arm64"):
                    with self.subTest(endian=endian, wide=wide,
                                      members=members, requested=requested):
                        if requested in members:
                            validator.validate_binary(path, "OSX", requested)
                        else:
                            with self.assertRaisesRegex(RuntimeError,
                                                        "does not target OSX"):
                                validator.validate_binary(path, "OSX", requested)

    def test_unknown_machine_types_are_rejected(self):
        for os_name, offset, fmt in (("WINDOWS", 68, "<H"),
                                     ("LINUX", 18, "<H"), ("OSX", 4, "<I")):
            with self.subTest(os_name=os_name):
                data = bytearray(native_image(os_name, "x64"))
                struct.pack_into(fmt, data, offset, 0xffff)
                with self.assertRaisesRegex(RuntimeError, "found machine types"):
                    validator.validate_binary(self.binary(data), os_name, "x64")

    def test_truncated_headers_fail_with_validation_errors(self):
        cases = (("WINDOWS", pe_image("x64"), (0, 1, 2, 60, 63, 64, 67, 69)),
                 ("LINUX", elf_image("x64"), (0, 1, 4, 6, 18, 19)))
        for os_name, data, lengths in cases:
            for length in lengths:
                with self.subTest(os_name=os_name, length=length):
                    with self.assertRaisesRegex(RuntimeError, "PE|ELF"):
                        validator.validate_binary(self.binary(data[:length]),
                                                  os_name, "x64")
        for endian, arch in itertools.product(("<", ">"), ("x86", "x64", "arm64")):
            for length in (0, 3, 4, 7):
                with self.subTest(endian=endian, arch=arch, length=length):
                    path = self.binary(macho_image(arch, endian)[:length])
                    with self.assertRaisesRegex(RuntimeError, "not a Mach-O"):
                        validator.validate_binary(path, "OSX", arch)

    def test_pe_invalid_signature_and_out_of_bounds_offsets(self):
        for offset in (0, 127, 128, 0xffffffff):
            with self.subTest(offset=offset):
                data = bytearray(pe_image("x64"))
                struct.pack_into("<I", data, 60, offset)
                with self.assertRaisesRegex(RuntimeError, "invalid PE header"):
                    validator.validate_binary(self.binary(data), "WINDOWS", "x64")
        data = bytearray(pe_image("x64"))
        data[64:68] = b"PX\0\0"
        with self.assertRaisesRegex(RuntimeError, "invalid PE header"):
            validator.validate_binary(self.binary(data), "WINDOWS", "x64")

    def test_bad_magic_and_wrong_binary_formats_are_rejected(self):
        for os_name, architecture in TARGETS:
            for data in (b"not an executable" * 8,
                         native_image("LINUX" if os_name != "LINUX" else "OSX",
                                      architecture)):
                with self.subTest(os_name=os_name, architecture=architecture):
                    with self.assertRaisesRegex(RuntimeError, "not a"):
                        validator.validate_binary(self.binary(data), os_name,
                                                  architecture)

    def test_elf_requires_little_endian_encoding(self):
        for encoding in (0, 2, 255):
            with self.subTest(encoding=encoding):
                data = bytearray(elf_image("x64"))
                data[5] = encoding
                with self.assertRaisesRegex(RuntimeError, "little-endian ELF"):
                    validator.validate_binary(self.binary(data), "LINUX", "x64")

    def test_fat_macho_rejects_zero_counts_and_incomplete_tables(self):
        for endian, wide in itertools.product(("<", ">"), (False, True)):
            data = fat_image(("x64", "arm64"), endian, wide)
            table_end = 8 + 2 * (32 if wide else 20)
            for count, length in ((0, len(data)), (2, table_end - 1),
                                  (0xffffffff, len(data)), (2, 7)):
                with self.subTest(endian=endian, wide=wide,
                                  count=count, length=length):
                    broken = bytearray(data)
                    struct.pack_into(endian + "I", broken, 4, count)
                    with self.assertRaisesRegex(RuntimeError, "Mach-O"):
                        validator.validate_binary(self.binary(broken[:length]),
                                                  "OSX", "arm64")


class TestInterpreterValidation(unittest.TestCase):
    def check(self, version=(3, 12), os_name="WINDOWS", architecture="x64",
              actual_version=(3, 12, 10), platform="win32", machine="AMD64",
              pointer_size=8):
        with (
            mock.patch.object(validator.sys, "version_info", actual_version),
            mock.patch.object(validator.sys, "platform", platform),
            mock.patch.object(validator.platform, "machine", return_value=machine),
            mock.patch.object(validator.struct, "calcsize", return_value=pointer_size),
        ):
            validator.validate_interpreter(version, os_name, architecture)

    def test_matching_platforms_architectures_and_aliases(self):
        for platform, os_name in (("win32", "WINDOWS"), ("linux", "LINUX"),
                                  ("darwin", "OSX")):
            for machine, architecture, width in (
                    ("AMD64", "x64", 8), ("x86_64", "x64", 8),
                    ("ARM64", "arm64", 8), ("aarch64", "arm64", 8),
                    ("i686", "x86", 4)):
                with self.subTest(platform=platform, machine=machine):
                    self.check(os_name=os_name, architecture=architecture,
                               platform=platform, machine=machine,
                               pointer_size=width)

    def test_32_bit_windows_python_uses_pointer_width_not_os_machine(self):
        for machine in ("AMD64", "ARM64", "x86"):
            with self.subTest(machine=machine):
                self.check(architecture="x86", machine=machine, pointer_size=4)
                with self.assertRaisesRegex(RuntimeError, "found WINDOWS/x86"):
                    self.check(architecture="x64", machine=machine, pointer_size=4)

    def test_python_minor_or_major_mismatch_fails_before_imports(self):
        for version in ((3, 11, 9), (3, 13, 0), (4, 12, 0)):
            with self.subTest(version=version):
                with self.assertRaisesRegex(RuntimeError, "target Python"):
                    self.check(actual_version=version)

    def test_platform_architecture_and_unknown_host_mismatches(self):
        cases = ({"platform": "linux"}, {"platform": "darwin"},
                 {"platform": "freebsd"}, {"machine": "arm64"},
                 {"machine": "unknown"}, {"architecture": "x86"})
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(
                        RuntimeError, "matching target OS/architecture"):
                    self.check(**arguments)


class TestImportValidation(PayloadTestCase):
    def test_requires_isolation_and_no_site(self):
        for isolated, no_site in ((0, 0), (1, 0), (0, 1)):
            with self.subTest(isolated=isolated, no_site=no_site):
                flags = SimpleNamespace(isolated=isolated, no_site=no_site)
                with (
                    mock.patch.object(validator.sys, "flags", flags),
                    mock.patch.object(validator.importlib, "import_module") as imports,
                ):
                    with self.assertRaisesRegex(RuntimeError, "Python -I -S"):
                        validator.validate_imports(self.workspace, LEGACY)
                    imports.assert_not_called()

    def test_r2p2_imports_explicitly_require_native_integration(self):
        with mock.patch.object(validator.importlib, "import_module") as imports:
            with self.assertRaisesRegex(ValueError, "native integration tests"):
                validator.validate_imports(self.workspace, "r2p2")
            imports.assert_not_called()

    def test_imports_stay_in_artifact_and_launcher_gets_clean_environment(self):
        for package, entry in ((LEGACY, "main"), (PROXY, "start_worker")):
            with self.subTest(package=package):
                root = self.payload(package)
                expected = ["grpc", "grpc._cython.cygrpc", "google.protobuf",
                            "azure.functions", f"{package}.{entry}",
                            f"{package}.dispatcher"]
                expected += [f"{package}.protos.{name.replace('/', '.')}"
                             for name in PROTOS]
                flags = SimpleNamespace(isolated=1, no_site=1)
                environment = {"CONTAINER_NAME": "container",
                               "WEBSITE_INSTANCE_ID": "instance", "KEEP": "yes"}
                with (
                    mock.patch.object(validator.sys, "flags", flags),
                    mock.patch.object(validator.sys, "path", []),
                    mock.patch.dict(os.environ, environment, clear=True),
                    mock.patch.object(validator.importlib, "import_module") as imports,
                    mock.patch.object(validator.subprocess, "run") as launch,
                ):
                    imports.side_effect = lambda name: SimpleNamespace(
                        __file__=str(root / (name.replace(".", "/") + ".py")))
                    validator.validate_imports(root, package)
                    self.assertEqual(imports.call_args_list,
                                     [mock.call(name) for name in expected])
                    self.assertEqual(sys.path[0], str(root.resolve()))
                    launch.assert_called_once_with(
                        [sys.executable, "-I", "-S", str(root / "worker.py"), "--help"],
                        cwd=root, env={"KEEP": "yes"}, check=True, timeout=60)
                    self.assertEqual(os.environ["CONTAINER_NAME"], "container")

    def test_external_imports_and_import_errors_prevent_launcher_execution(self):
        root = self.payload()
        flags = SimpleNamespace(isolated=1, no_site=1)
        # A sibling whose name starts with root is still outside the artifact.
        external = root.with_name(root.name + "-outside") / "grpc.py"
        for failure in (SimpleNamespace(__file__=str(external)),
                        ImportError("native ABI mismatch"),
                        RuntimeError("generated protobuf runtime mismatch")):
            with self.subTest(failure=failure):
                with (
                    mock.patch.object(validator.sys, "flags", flags),
                    mock.patch.object(validator.sys, "path", []),
                    mock.patch.object(validator.importlib, "import_module") as imports,
                    mock.patch.object(validator.subprocess, "run") as launch,
                ):
                    if isinstance(failure, Exception):
                        imports.side_effect = failure
                        error, message = type(failure), str(failure)
                    else:
                        imports.return_value = failure
                        error, message = RuntimeError, "outside the artifact"
                    with self.assertRaisesRegex(error, message):
                        validator.validate_imports(root, LEGACY)
                    launch.assert_not_called()

    def test_launcher_failure_or_timeout_is_not_suppressed(self):
        root = self.payload()
        flags = SimpleNamespace(isolated=1, no_site=1)
        for failure in (subprocess.CalledProcessError(2, "worker.py"),
                        subprocess.TimeoutExpired("worker.py", 60)):
            with self.subTest(failure=type(failure).__name__):
                with (
                    mock.patch.object(validator.sys, "flags", flags),
                    mock.patch.object(validator.sys, "path", []),
                    mock.patch.object(validator.importlib, "import_module") as imports,
                    mock.patch.object(validator.subprocess, "run") as launch,
                ):
                    imports.return_value = SimpleNamespace(
                        __file__=str(root / "module.py"))
                    launch.side_effect = failure
                    with self.assertRaises(type(failure)) as caught:
                        validator.validate_imports(root, LEGACY)
                    self.assertIs(caught.exception, failure)
                    launch.assert_called_once()


class TestValidatorCli(PayloadTestCase):
    def test_structure_only_cli_accepts_all_worker_generations(self):
        for value, package, filename in (
                ("3.10.14", LEGACY, "cygrpc.cp310-test.so"),
                ("3.12.0rc2", LEGACY, "cygrpc.cp312-test.so"),
                ("3.13.0rc1", PROXY, "cygrpc.cp313-test.so"),
                ("3.14", PROXY, "cygrpc.cp314-test.so"),
                ("3.15.0a1", "r2p2", None), ("3.16", "r2p2", None)):
            with self.subTest(value=value):
                root = self.payload(package, grpc_name=filename)
                result = self.cli(root, value, grpc_build=(
                    None if package == "r2p2" else "test.so"))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"Validated {package}", result.stdout)
                self.assertNotIn("Imported ", result.stdout)

    def test_check_imports_rejects_mismatched_python_before_importing(self):
        # Always choose a supported target different from the running Python.
        minor = 13 if sys.version_info[:2] != (3, 13) else 12
        package = PROXY if minor == 13 else LEGACY
        root = self.payload(package, grpc_name=f"cygrpc.cp3{minor}-test.so")
        result = self.cli(root, f"3.{minor}", check_imports=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"Validated {package}", result.stdout)
        self.assertIn("interpreter does not match target Python", result.stderr)
        self.assertNotIn("Imported ", result.stdout)

    def test_check_imports_rejects_mismatched_os_and_architecture(self):
        version = sys.version_info[:2]
        package = (LEGACY if version < (3, 13) else
                   PROXY if version < (3, 15) else "r2p2")
        actual_os = {"win32": "WINDOWS", "linux": "LINUX", "darwin": "OSX"}[
            sys.platform]
        other_os = "LINUX" if actual_os != "LINUX" else "WINDOWS"
        other_arch = "x86" if struct.calcsize("P") == 8 else "x64"
        for os_name, architecture in ((other_os, "x64"), (actual_os, other_arch)):
            with self.subTest(os_name=os_name, architecture=architecture):
                root = self.payload(package, os_name, architecture,
                                    f"cygrpc.cp{version[0]}{version[1]}-test.so")
                result = self.cli(root, f"{version[0]}.{version[1]}", os_name,
                                  architecture, check_imports=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"Validated {package}", result.stdout)
                self.assertIn("matching target OS/architecture", result.stderr)
                self.assertNotIn("Imported ", result.stdout)

    def test_cli_reports_missing_payload_and_missing_grpc_build(self):
        root = self.payload()
        result = self.cli(root, grpc_build=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--grpc-build is required", result.stderr)
        (root / "worker.py").unlink()
        result = self.cli(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing worker payload files/folders: worker.py", result.stderr)

    def test_cli_rejects_invalid_versions_and_target_arguments(self):
        root = self.payload()
        for kwargs, message in (({"version": "invalid"}, "Invalid Python version"),
                                ({"version": "3.9"}, "Unsupported Python version"),
                                ({"os_name": "FREEBSD"}, "invalid choice"),
                                ({"architecture": "mips"}, "invalid choice")):
            with self.subTest(arguments=kwargs):
                result = self.cli(root, **kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)


class TestPackagingTemplateWiring(unittest.TestCase):
    def scripts(self, name):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        return re.findall(
            r"(?m)^- (?:powershell|bash): [>|]-?\n((?:    .*\n|\n)+)", text)

    def test_every_env_gen_template_uses_shared_validator_without_manifest_copy(self):
        templates = list(TEMPLATES.glob("*env_gen.yml"))
        self.assertTrue(templates, "No packaging templates found")
        self.assertTrue({"win_env_gen.yml", "nix_env_gen.yml",
                         "nix_arm64_env_gen.yml", "macos_64_env_gen.yml",
                         "r2p2_env_gen.yml"}.issubset({p.name for p in templates}))
        for path in templates:
            with self.subTest(template=path.name):
                scripts = "\n".join(self.scripts(path.name))
                self.assertIn("/eng/pack/scripts/validate_worker_payload.py", scripts)
                self.assertNotRegex(scripts.lower(), r"\$expected\b")
                self.assertNotIn("validate_arm64_payload.py", scripts)
                for argument in ("--python-version", "--os", "--architecture"):
                    self.assertIn(argument, scripts)

    def test_native_templates_validate_imports_in_isolated_python(self):
        for name, os_name in (("win_env_gen.yml", "WINDOWS"),
                              ("nix_env_gen.yml", "LINUX"),
                              ("macos_64_env_gen.yml", "OSX")):
            with self.subTest(template=name):
                scripts = [script for script in self.scripts(name)
                           if "validate_worker_payload.py" in script]
                self.assertEqual(len(scripts), 1)
                script = scripts[0]
                self.assertIn("python -I -S", script)
                self.assertIn("--check-imports", script)
                self.assertIn(f"--os {os_name}", script)
                self.assertIn("--grpc-build '${{ parameters.grpcBuild }}'", script)

    def test_arm64_imports_run_in_target_docker_not_cross_build_host(self):
        scripts = [script for script in self.scripts("nix_arm64_env_gen.yml")
                   if "validate_worker_payload.py" in script]
        self.assertEqual(len(scripts), 2)
        structural, docker = scripts
        self.assertNotIn("--check-imports", structural)
        self.assertIn("--os LINUX --architecture arm64", structural)
        for fragment in (
                "docker run --rm --platform linux/arm64 --network none",
                "target=/payload,readonly", "target=/validation,readonly",
                "python:${{ parameters.pythonVersion }}-slim",
                "python -I -S /validation/validate_worker_payload.py /payload",
                "--os LINUX --architecture arm64", "--check-imports",
                "--grpc-build '${{ parameters.grpcBuild }}'",
                "tonistiigi/binfmt --install arm64"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, docker)

    def test_r2p2_cross_build_validation_is_structure_only(self):
        scripts = [script for script in self.scripts("r2p2_env_gen.yml")
                   if "validate_worker_payload.py" in script]
        self.assertEqual(len(scripts), 1)
        self.assertIn("python -I -S", scripts[0])
        self.assertIn("--os ${{ parameters.osName }}", scripts[0])
        self.assertIn("--architecture ${{ parameters.architecture }}", scripts[0])
        self.assertNotIn("--check-imports", scripts[0])
        self.assertNotIn("--grpc-build", scripts[0])


if __name__ == "__main__":
    unittest.main()