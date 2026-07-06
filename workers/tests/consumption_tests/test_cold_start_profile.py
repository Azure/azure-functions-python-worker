# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Cold-start profiling tests for Flex Consumption.

These tests are opt-in. They are not part of the normal unit test run
because they require Docker, a real Azure Storage connection string,
and the dev encryption key. They reuse FlexConsumptionWebHostController
so the cold start they profile is the same path that ships to
production.

Set ``COLD_START_PROFILE=1`` to enable them:

    AzureWebJobsStorage="<conn-str>" \
    _DUMMY_CONT_KEY="<dev key>" \
    COLD_START_PROFILE=1 \
    python -m pytest workers/tests/consumption_tests/test_cold_start_profile.py -s

Artifacts (raw container log, parsed importtime report, optional py-spy
speedscope flame chart) land in ``workers/tests/.artifacts/cold_start/``.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

from requests import Request

from ..utils import constants
from ..utils.cold_start_profiler import (
    collect_pyspy_artifact,
    diff_reports,
    find_worker_pid,
    install_pyspy_in_container,
    parse_importtime,
    start_pyspy,
    write_importtime_artifacts,
)
# Available as a manual override if env propagation breaks again; not
# used by the default importtime test path.
from ..utils.cold_start_profiler import inject_importtime_shim  # noqa: F401
from ..utils.testutils_fc import FlexConsumptionWebHostController

_DEFAULT_HOST_VERSION = '4'
_ARTIFACT_DIR = constants.WORKERS_TESTS_ROOT / '.artifacts' / 'cold_start'

_ENABLED = os.getenv('COLD_START_PROFILE') == '1'


@unittest.skipUnless(_ENABLED, 'Set COLD_START_PROFILE=1 to enable')
class TestColdStartProfile(unittest.TestCase):
    """Capture cold-start profiles against a real Flex mesh container."""

    @classmethod
    def setUpClass(cls):
        cls._py_version = f'{sys.version_info.major}.{sys.version_info.minor}'
        if os.getenv('AzureWebJobsStorage') is None:
            raise unittest.SkipTest('AzureWebJobsStorage not set')
        if os.getenv('_DUMMY_CONT_KEY') is None:
            raise unittest.SkipTest('_DUMMY_CONT_KEY not set')
        _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # importtime profile (always available, no extra deps)
    # ------------------------------------------------------------------

    def _spawn_with_env(self, container_env):
        """Spawn the FC container with extra docker -e env vars.

        ``FlexConsumptionWebHostController.__enter__`` spawns with no
        env, but ``PYTHONPROFILEIMPORTTIME`` is read at CPython startup
        and must be present in the worker process env from boot. Setting
        it via ``docker run -e`` is sufficient: the Functions Host
        inherits the container env and passes it through to the worker
        process it spawns.
        """
        ctrl = FlexConsumptionWebHostController(
            _DEFAULT_HOST_VERSION, self._py_version,
        )
        mesh_image = (
            os.environ.get('CUSTOM_IMAGE')
            or ctrl._find_latest_mesh_image(
                _DEFAULT_HOST_VERSION, self._py_version,
            )
        )
        ctrl.spawn_container(image=mesh_image, env=container_env)
        return ctrl

    def _run_importtime_capture(self, fixture_zip: str, tag_suffix: str):
        """Common importtime capture flow used by v1 and v2 cases."""
        base_tag = os.getenv(
            'COLD_START_TAG', f'current_py{self._py_version}',
        )
        tag = f'{base_tag}_{tag_suffix}'
        storage = os.environ['AzureWebJobsStorage']

        ctrl = self._spawn_with_env({
            'PYTHONPROFILEIMPORTTIME': '1',
            # Unbuffered stderr so importtime lines flush into docker logs
            # promptly even if the worker exits abnormally.
            'PYTHONUNBUFFERED': '1',
        })
        try:
            ctrl.assign_container(env={
                'AzureWebJobsStorage': storage,
                'SCM_RUN_FROM_PACKAGE': fixture_zip,
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            self.assertEqual(
                resp.status_code, 200,
                msg=f'Cold-start invocation failed: {resp.text}',
            )
            # Give the worker a moment to flush stderr buffers.
            time.sleep(2)
            logs = ctrl.get_container_logs()
        finally:
            ctrl.safe_kill_container()

        raw_path, report_path, report = write_importtime_artifacts(
            logs, _ARTIFACT_DIR, tag,
        )

        print(f'\n[cold-start] fixture:    {fixture_zip}')
        print(f'[cold-start] raw log:    {raw_path}')
        print(f'[cold-start] report:     {report_path}')
        print(f'[cold-start] total imports: {len(report.records)} '
              f'totalling {report.total_ms:.1f} ms')
        print()
        print(report.format_text(top=20))

        self.assertGreater(
            len(report.records), 0,
            msg='No importtime records found. If the raw log does not '
                'contain "import time:" substrings at all, try the '
                'inject_importtime_shim() helper from '
                'cold_start_profiler to bypass env propagation.',
        )

        # Sanity check: confirm we hit the expected runtime path. The v1
        # fixture pulls in azure_functions_runtime_v1; the v2 fixture
        # pulls in azure_functions_runtime. If we see the wrong one,
        # something is wrong with the fixture or the dispatcher.
        modules = {r.module for r in report.records}
        if tag_suffix == 'v1':
            self.assertTrue(
                any(m.startswith('azure_functions_runtime_v1')
                    for m in modules),
                msg='Expected azure_functions_runtime_v1 in the v1 '
                    'profile but did not find it. Sample modules: '
                    f'{sorted(modules)[:10]}',
            )
        elif tag_suffix == 'v2':
            self.assertTrue(
                any(m == 'azure_functions_runtime'
                    or m.startswith('azure_functions_runtime.')
                    for m in modules),
                msg='Expected azure_functions_runtime (v2) in the v2 '
                    'profile but did not find it. The dispatcher may '
                    'have fallen back to v1 because function_app.py '
                    'was not detected at the app root. Sample modules: '
                    f'{sorted(modules)[:10]}',
            )

    def test_cold_start_importtime(self):
        """Capture ``-X importtime`` waterfall through a full cold start.

        Uses the v1 ``HttpNoAuth.zip`` fixture (legacy host.json + per-
        function folder model). The dispatcher loads
        ``azure_functions_runtime_v1`` for this path.

        Spawns the placeholder container with
        ``PYTHONPROFILEIMPORTTIME=1`` set via ``docker run -e`` so the
        worker python process inherits it at interpreter start.
        Specializes (EnvironmentReloadRequest, the Flex cold path),
        invokes once, then dumps importtime artifacts. The Functions
        Host wraps each worker stderr line inside its own JSON log
        payload; ``parse_importtime`` handles both raw and host-wrapped
        formats.

        If this test ever finds zero records, drop a shim with
        :func:`inject_importtime_shim` from ``cold_start_profiler``
        BEFORE calling ``assign_container``. The shim replaces
        ``python`` on PATH with a wrapper that adds ``-X importtime``,
        bypassing any env propagation issues.
        """
        self._run_importtime_capture('HttpNoAuth.zip', 'v1')

    def test_cold_start_importtime_v2(self):
        """Capture ``-X importtime`` for the v2 programming model path.

        Uses ``HttpNoAuthV2.zip`` which ships a top-level
        ``function_app.py``. The dispatcher detects the v2 script file
        and loads ``azure_functions_runtime`` (v2) — this is the path
        used by Python 3.13+ in production and where the cold-start
        regression lives.
        """
        self._run_importtime_capture('HttpNoAuthV2.zip', 'v2')

    # ------------------------------------------------------------------
    # py-spy flame chart (optional)
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        os.getenv('COLD_START_PYSPY') == '1',
        'Set COLD_START_PYSPY=1 to enable py-spy flame chart capture',
    )
    def test_cold_start_pyspy_flame(self):
        """Capture a py-spy flame chart across the specialize/invoke window."""
        tag = os.getenv('COLD_START_TAG', f'current_py{self._py_version}')
        storage = os.environ['AzureWebJobsStorage']
        out_dir = _ARTIFACT_DIR / tag

        with FlexConsumptionWebHostController(
                _DEFAULT_HOST_VERSION, self._py_version) as ctrl:
            install_pyspy_in_container(ctrl._uuid)
            # Specialize first so a worker process exists for py-spy to
            # attach to. py-spy records the steady invocation path; for
            # the pure cold-import waterfall use the importtime test.
            ctrl.assign_container(env={
                'AzureWebJobsStorage': storage,
                'SCM_RUN_FROM_PACKAGE': 'HttpNoAuth.zip',
            })

            pid = find_worker_pid(ctrl._uuid)

            # Capture both formats: speedscope for interactive inspection,
            # SVG for quick visual.
            for fmt in ('speedscope', 'flamegraph'):
                proc = start_pyspy(
                    ctrl._uuid, pid, out_dir,
                    duration=6.0, rate=250, fmt=fmt,
                )

                # Trigger work during the recording window.
                req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
                resp = ctrl.send_request(req)
                self.assertEqual(resp.status_code, 200)

                proc.wait(timeout=30)
                if proc.returncode != 0:
                    self.fail(
                        f'py-spy ({fmt}) failed: '
                        f'{proc.stderr.read().decode("utf-8", "replace")}'
                    )
                artifact = collect_pyspy_artifact(
                    ctrl._uuid, pid, out_dir, fmt=fmt,
                )
                print(f'[cold-start] py-spy {fmt}: {artifact}')

    # ------------------------------------------------------------------
    # A/B diff convenience
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        os.getenv('COLD_START_DIFF_BASELINE'),
        'Set COLD_START_DIFF_BASELINE=<path to baseline raw log> to enable',
    )
    def test_diff_against_baseline(self):
        """Compare the current run against a baseline raw docker log.

        Workflow:
          1. ``git worktree add ../base <baseline-sha>``
          2. Run ``test_cold_start_importtime`` from the baseline tree
             with ``COLD_START_TAG=baseline``; copy the .docker.log to
             a stable location.
          3. Run this test against the current tree with
             ``COLD_START_DIFF_BASELINE=<that log>``.
        """
        baseline_path = Path(os.environ['COLD_START_DIFF_BASELINE'])
        tag = os.getenv('COLD_START_TAG', f'current_py{self._py_version}')
        current_log_path = _ARTIFACT_DIR / f'{tag}.docker.log'
        if not current_log_path.exists():
            self.skipTest(
                f'No current log at {current_log_path}; run '
                f'test_cold_start_importtime first.'
            )

        baseline = parse_importtime(baseline_path.read_text(encoding='utf-8'))
        current = parse_importtime(current_log_path.read_text(encoding='utf-8'))

        diff_text = diff_reports(baseline, current, min_delta_ms=1.0, top=50)
        diff_path = _ARTIFACT_DIR / f'{tag}.diff_vs_baseline.txt'
        diff_path.write_text(diff_text, encoding='utf-8')

        print(f'\n[cold-start] diff vs baseline ({baseline_path.name}):')
        print(diff_text)
        print(f'\nWritten to {diff_path}')

        self.assertGreater(
            len(current.records), 0,
            msg='Current report is empty; nothing to diff.',
        )
