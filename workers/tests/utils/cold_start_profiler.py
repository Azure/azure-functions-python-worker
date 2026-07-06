# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Cold-start profiling helpers for the Flex Consumption test harness.

Two profile modes are supported:

* ``importtime`` (default): set ``PYTHONPROFILEIMPORTTIME=1`` on the
  container so CPython writes per-import wall-time records to stderr.
  After the cold start completes we parse the lines out of
  ``docker logs`` and produce a flat report sorted by cumulative time.

* ``pyspy``: launch ``py-spy record`` inside the container against the
  worker process while it specializes, so we get a flame chart in
  speedscope JSON and SVG form.

These helpers are intentionally dependency-light: only stdlib + the
``docker`` CLI already used by ``testutils_fc``.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_IMPORT_TIME_LINE = re.compile(
    r'^import time:\s+(?P<self_us>\d+)\s+\|\s+(?P<cum_us>\d+)\s+\|'
    r'(?P<indent>\s*)(?P<module>\S+)\s*$'
)
# When the Functions Host captures the worker's stderr and re-emits it
# through its own logger, each line gets wrapped inside a CSV-quoted log
# field like:
#   MS_FUNCTION_LOGS 4,,sid,,,Worker.rpc...,"","  import time: 123 | 456 | foo"
# We strip the wrapper and rescan for ``import time:`` substrings.
_HOST_WRAPPED = re.compile(
    r'import time:\s+(?P<self_us>\d+)\s+\|\s+(?P<cum_us>\d+)\s+\|'
    r'(?P<indent>\s*)(?P<module>[A-Za-z_][\w\.]*)'
)


@dataclass
class ImportRecord:
    module: str
    self_us: int
    cum_us: int
    depth: int

    @property
    def self_ms(self) -> float:
        return self.self_us / 1000.0

    @property
    def cum_ms(self) -> float:
        return self.cum_us / 1000.0


@dataclass
class ImportTimeReport:
    records: List[ImportRecord] = field(default_factory=list)

    @property
    def total_ms(self) -> float:
        return sum(r.self_ms for r in self.records)

    def top_by_cumulative(self, n: int = 30) -> List[ImportRecord]:
        return sorted(self.records, key=lambda r: r.cum_us, reverse=True)[:n]

    def top_by_self(self, n: int = 30) -> List[ImportRecord]:
        return sorted(self.records, key=lambda r: r.self_us, reverse=True)[:n]

    def by_module(self) -> Dict[str, ImportRecord]:
        # Last record for a given module wins (importtime can emit duplicates
        # for re-imports across sys.path swaps; we keep the latest).
        out: Dict[str, ImportRecord] = {}
        for r in self.records:
            out[r.module] = r
        return out

    def format_text(self, top: int = 30) -> str:
        lines: List[str] = []
        lines.append(f'Total self-time across imports: {self.total_ms:.1f} ms')
        lines.append('')
        lines.append(f'Top {top} by cumulative time (ms):')
        lines.append(f'{"cum":>10}  {"self":>10}  module')
        for r in self.top_by_cumulative(top):
            lines.append(
                f'{r.cum_ms:>10.1f}  {r.self_ms:>10.1f}  '
                f'{"  " * r.depth}{r.module}'
            )
        lines.append('')
        lines.append(f'Top {top} by self time (ms):')
        lines.append(f'{"self":>10}  {"cum":>10}  module')
        for r in self.top_by_self(top):
            lines.append(
                f'{r.self_ms:>10.1f}  {r.cum_ms:>10.1f}  {r.module}'
            )
        return '\n'.join(lines)


def parse_importtime(log_text: str) -> ImportTimeReport:
    """Parse ``-X importtime`` / ``PYTHONPROFILEIMPORTTIME=1`` output.

    Handles two shapes:

    * Raw CPython stderr lines that match ``_IMPORT_TIME_LINE`` exactly.
    * Functions-Host-wrapped lines where each worker stderr line is
      embedded inside a CSV-quoted log field. In that case we scan with
      ``_HOST_WRAPPED`` which matches ``import time: …`` anywhere in
      the line.

    ``log_text`` may contain unrelated lines, ANSI codes, or be the raw
    output of ``docker logs``; only matching records are returned.
    """
    report = ImportTimeReport()
    for raw in log_text.splitlines():
        m = _IMPORT_TIME_LINE.match(raw)
        if m is None:
            m = _HOST_WRAPPED.search(raw)
        if not m:
            continue
        indent = m.group('indent') or ''
        # CPython indents with two spaces per level after the colon.
        depth = max(0, (len(indent) - 1) // 2)
        report.records.append(ImportRecord(
            module=m.group('module'),
            self_us=int(m.group('self_us')),
            cum_us=int(m.group('cum_us')),
            depth=depth,
        ))
    return report


def diff_reports(
    baseline: ImportTimeReport,
    current: ImportTimeReport,
    min_delta_ms: float = 1.0,
    top: int = 40,
) -> str:
    """Compare two importtime reports module-by-module."""
    base = baseline.by_module()
    cur = current.by_module()
    rows: List[Tuple[str, float, float, float]] = []
    for mod in set(base) | set(cur):
        b = base.get(mod)
        c = cur.get(mod)
        b_ms = b.cum_ms if b else 0.0
        c_ms = c.cum_ms if c else 0.0
        delta = c_ms - b_ms
        if abs(delta) >= min_delta_ms:
            rows.append((mod, b_ms, c_ms, delta))
    rows.sort(key=lambda r: r[3], reverse=True)
    rows = rows[:top]

    lines = [
        f'{"delta_ms":>10}  {"baseline":>10}  {"current":>10}  module',
    ]
    for mod, b_ms, c_ms, delta in rows:
        lines.append(
            f'{delta:>+10.1f}  {b_ms:>10.1f}  {c_ms:>10.1f}  {mod}'
        )
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# py-spy helpers
# ---------------------------------------------------------------------------

@dataclass
class PySpyResult:
    speedscope_path: Optional[Path]
    svg_path: Optional[Path]
    stderr: str


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['docker', *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def find_worker_pid(container: str, attempts: int = 30) -> int:
    """Find the python worker PID inside the container.

    The proxy worker is invoked as ``python -m proxy_worker``; we look for
    that, falling back to any python process matching the worker module.
    """
    pattern = re.compile(r'^\s*(\d+)\s+.*python.*proxy_worker', re.MULTILINE)
    for _ in range(attempts):
        proc = _docker('exec', container, 'ps', '-eo', 'pid,args', check=False)
        out = proc.stdout.decode('utf-8', errors='replace')
        m = pattern.search(out)
        if m:
            return int(m.group(1))
        time.sleep(0.25)
    raise RuntimeError(
        f'Could not find proxy_worker PID in container {container}. '
        f'Last ps output:\n{out}'
    )


def install_pyspy_in_container(container: str) -> None:
    """Best-effort install of py-spy inside the container.

    The mesh image ships pip, so this typically works in a few seconds.
    Caller may install py-spy ahead of time and skip this if preferred.
    """
    _docker(
        'exec', container,
        'pip', 'install', '--no-cache-dir', '--quiet', 'py-spy',
    )


def start_pyspy(
    container: str,
    worker_pid: int,
    out_dir: Path,
    duration: float = 8.0,
    rate: int = 250,
    fmt: str = 'speedscope',
) -> 'subprocess.Popen[bytes]':
    """Start py-spy record inside the container.

    Returns the Popen handle of the outer ``docker exec`` so the caller
    can wait()/kill() it. ``fmt`` is forwarded to ``py-spy record -f``;
    valid values include ``speedscope``, ``flamegraph`` (SVG), ``raw``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    container_out = f'/tmp/pyspy-{worker_pid}.{fmt}'
    cmd = [
        'docker', 'exec', container,
        'py-spy', 'record',
        '-p', str(worker_pid),
        '-o', container_out,
        '-d', str(int(duration)),
        '-r', str(rate),
        '-f', fmt,
        '--subprocesses',
        '--idle',
    ]
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def collect_pyspy_artifact(
    container: str,
    worker_pid: int,
    out_dir: Path,
    fmt: str = 'speedscope',
) -> Path:
    """Copy the py-spy output file out of the container."""
    container_path = f'/tmp/pyspy-{worker_pid}.{fmt}'
    suffix = 'json' if fmt == 'speedscope' else (
        'svg' if fmt == 'flamegraph' else fmt
    )
    host_path = out_dir / f'cold_start_{worker_pid}.{suffix}'
    _docker('cp', f'{container}:{container_path}', str(host_path))
    return host_path


# ---------------------------------------------------------------------------
# importtime shim injection
# ---------------------------------------------------------------------------

# The Functions Host launches the worker as ``python -u worker.py …`` via
# ``Process.Start``. Env vars passed via ``docker run -e`` do not reliably
# propagate to that child process (the Host curates the worker env), so
# ``PYTHONPROFILEIMPORTTIME=1`` set on the container env is silently
# dropped. To work around this we drop a shim earlier on PATH that
# re-invokes the real CPython with ``-X importtime`` prepended.

_PYTHON_SHIM = """#!/bin/sh
# Auto-generated by cold_start_profiler. Re-execs the real python with
# -X importtime so PYTHONPROFILEIMPORTTIME-equivalent output is emitted
# regardless of whether the parent process propagates env vars.
exec {real_python} -X importtime "$@"
"""


def inject_importtime_shim(container: str) -> str:
    """Replace ``python`` on the container PATH with a shim that enables
    importtime profiling for every subsequent invocation.

    Returns the path of the real python that the shim now wraps.
    """
    # 1. Resolve the real python binary (follow symlinks).
    proc = _docker(
        'exec', container, 'sh', '-c',
        'readlink -f "$(command -v python)"',
    )
    real_python = proc.stdout.decode('utf-8', errors='replace').strip()
    if not real_python:
        raise RuntimeError(
            f'Could not locate python in container {container}.'
        )

    # 2. Pick a shim location that wins over the real path. /usr/local/bin
    # is conventionally ahead of /usr/bin on Debian/Ubuntu PATH.
    shim_dir = '/usr/local/bin'
    shim_body = _PYTHON_SHIM.format(real_python=real_python)

    # Use base64 to avoid quoting hell through nested sh -c.
    import base64 as _b64
    encoded = _b64.b64encode(shim_body.encode('utf-8')).decode('ascii')

    install_cmd = (
        f'mkdir -p {shim_dir} && '
        f'echo {encoded} | base64 -d > {shim_dir}/python && '
        f'chmod +x {shim_dir}/python && '
        f'ln -sf {shim_dir}/python {shim_dir}/python3'
    )
    _docker('exec', container, 'sh', '-c', install_cmd)

    # 3. Verify the shim is what `command -v python` now resolves to.
    verify = _docker(
        'exec', container, 'sh', '-c', 'command -v python',
    )
    resolved = verify.stdout.decode('utf-8', errors='replace').strip()
    if resolved != f'{shim_dir}/python':
        raise RuntimeError(
            f'Shim install verification failed. Expected '
            f'{shim_dir}/python on PATH, got {resolved!r}.'
        )
    return real_python


# ---------------------------------------------------------------------------
# Convenience: dump artifacts
# ---------------------------------------------------------------------------

def write_importtime_artifacts(
    log_text: str,
    out_dir: Path,
    tag: str,
) -> Tuple[Path, Path, ImportTimeReport]:
    """Persist raw log + parsed importtime report to ``out_dir``.

    Returns (raw_log_path, report_path, parsed_report).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f'{tag}.docker.log'
    raw_path.write_text(log_text, encoding='utf-8')

    report = parse_importtime(log_text)
    report_path = out_dir / f'{tag}.importtime.txt'
    report_path.write_text(report.format_text(), encoding='utf-8')

    json_path = out_dir / f'{tag}.importtime.json'
    json_path.write_text(
        json.dumps(
            [
                {
                    'module': r.module,
                    'self_ms': r.self_ms,
                    'cum_ms': r.cum_ms,
                    'depth': r.depth,
                }
                for r in report.records
            ],
            indent=2,
        ),
        encoding='utf-8',
    )
    return raw_path, report_path, report
