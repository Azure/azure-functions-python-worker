# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Protect required ARM64 builds and reviewed dependency pins from merge regressions."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]


class TestRequiredArm64Builds(unittest.TestCase):
    def test_both_arm64_jobs_are_blocking_and_pinned(self):
        text = (ROOT / 'eng/templates/official/jobs/build-artifacts.yml').read_text()
        for os_name, digest in (
            ('LINUX', 'f74e1db0eabd651cd01e4e2a00201bd41866abe74869ab716f9bf33cbbaa0943'),
            ('WINDOWS', 'aeb58f2bb6ba9a4cefacae6c23f720133f82bbdc91c8c9dc9a467d483a1a3534'),
        ):
            with self.subTest(os=os_name):
                job = re.search(
                    rf'(?ms)^- job: Build_R2P2_{os_name}_ARM64\n.*?(?=^- job:|\Z)', text)
                self.assertIsNotNone(job)
                block = job.group()
                self.assertNotIn('continueOnError:', block)
                self.assertNotIn('condition:', block)
                self.assertIn("pythonVersion: '3.15.2'", block)
                self.assertIn(digest, block)
                self.assertIn("hostArchitecture: 'x64'", block)

    def test_packaging_requires_both_arm64_artifacts(self):
        text = (ROOT / 'eng/templates/official/jobs/build-artifacts.yml').read_text()
        package = text.split('- job: PackageWorkers\n', 1)[1]
        dependencies = re.search(r'(?m)^  dependsOn:.*$', package).group()
        for os_name in ('LINUX', 'WINDOWS'):
            self.assertIn(f'Build_R2P2_{os_name}_ARM64', dependencies)
        self.assertNotIn('continueOnError:', package)
        self.assertNotIn('condition:', package)
        self.assertNotIn('$optionalArtifacts', package)
        self.assertNotIn('RemoveChild', package)
        nuspec = (ROOT / 'eng/pack/Microsoft.Azure.Functions.V4.PythonWorker.nuspec').read_text()
        for os_name in ('LINUX', 'WINDOWS'):
            self.assertIn(f'3.15_{os_name}_ARM64', nuspec)


if __name__ == '__main__':
    unittest.main()