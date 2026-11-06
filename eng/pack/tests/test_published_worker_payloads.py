# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Exercise the post-download gate against independent synthetic artifacts."""

import importlib.util
import shutil
import subprocess
import sys

from test_worker_payload_validation import PayloadTestCase, REPO_ROOT


SCRIPT = REPO_ROOT / "eng/pack/scripts/validate_published_worker_payloads.py"
NUSPEC = REPO_ROOT / "eng/pack/Microsoft.Azure.Functions.V4.PythonWorker.nuspec"
spec = importlib.util.spec_from_file_location("published_payload_validator", SCRIPT)
published = importlib.util.module_from_spec(spec)
spec.loader.exec_module(published)


class TestPublishedWorkerPayloads(PayloadTestCase):
    def stage_all(self):
        # Independent matrix: 3.10-3.14 on six targets, 3.15 on seven.
        targets = (("WINDOWS", "x64", "win_amd64.pyd"),
                   ("WINDOWS", "x86", "win32.pyd"),
                   ("LINUX", "x64", "x86_64-linux-gnu.so"),
                   ("LINUX", "arm64", "aarch64-linux-gnu.so"),
                   ("OSX", "x64", "darwin.so"),
                   ("OSX", "arm64", "darwin.so"))
        for minor in range(10, 16):
            package = ("azure_functions_worker" if minor < 13 else
                       "proxy_worker" if minor < 15 else "r2p2")
            for os_name, arch, grpc in targets + (
                    (("WINDOWS", "arm64", None),) if minor == 15 else ()):
                name = None if minor == 15 else f"cygrpc.cp3{minor}-{grpc}"
                path = self.payload(package, os_name, arch, name)
                path.rename(self.workspace / f"3.{minor}_{os_name}_{arch.upper()}")

    def run_gate(self, nuspec=NUSPEC):
        return subprocess.run(
            [sys.executable, "-I", "-S", str(SCRIPT), str(self.workspace),
             "--nuspec", str(nuspec)], capture_output=True, text=True, timeout=30)

    def test_all_manifest_payloads_are_checked_from_downloaded_outputs(self):
        self.stage_all()
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated all 37 published worker payloads", result.stdout)

    def test_empty_download_directory_is_not_silently_accepted(self):
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing published worker artifact", result.stderr)

    def test_missing_arm64_artifact_blocks_packaging(self):
        self.stage_all()
        shutil.rmtree(self.workspace / "3.15_WINDOWS_ARM64")
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing published worker artifact: 3.15_WINDOWS_ARM64",
                      result.stderr)

    def test_wrong_arm64_executable_blocks_packaging(self):
        self.stage_all()
        shutil.copyfile(self.workspace / "3.15_WINDOWS_X64/r2p2.exe",
                        self.workspace / "3.15_WINDOWS_ARM64/r2p2.exe")
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not target WINDOWS arm64", result.stderr)

    def test_missing_worker_module_blocks_packaging(self):
        self.stage_all()
        (self.workspace / "3.12_LINUX_ARM64/azure_functions_worker/dispatcher.py").unlink()
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("azure_functions_worker/dispatcher.py", result.stderr)

    def test_manifest_without_payloads_is_rejected(self):
        manifest = self.workspace / "empty.nuspec"
        manifest.write_text("<package><files /></package>", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no worker payloads"):
            published.required_payloads(manifest)