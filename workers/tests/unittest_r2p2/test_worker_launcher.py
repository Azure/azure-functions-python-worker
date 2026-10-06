# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import runpy
import sys
from pathlib import Path

import pytest


WORKER_PATH = Path(__file__).resolve().parents[2] / "python" / "r2p2" / "worker.py"


class _ExecCalled(Exception):
    pass


@pytest.mark.parametrize(
    ("platform_name", "binary_name"),
    (("nt", "r2p2.exe"), ("posix", "r2p2")),
)
def test_worker_execs_native_binary_with_forwarded_arguments(
        monkeypatch, platform_name, binary_name):
    captured = {}

    def fake_execv(executable, arguments):
        captured["executable"] = executable
        captured["arguments"] = arguments
        raise _ExecCalled

    monkeypatch.setattr(os, "name", platform_name)
    monkeypatch.setattr(os, "execv", fake_execv)
    monkeypatch.setattr(
        sys, "argv", [str(WORKER_PATH), "--host", "localhost", "--port", "5001"])

    with pytest.raises(_ExecCalled):
        runpy.run_path(str(WORKER_PATH), run_name="__main__")

    expected = str(WORKER_PATH.parent / binary_name)
    assert captured == {
        "executable": expected,
        "arguments": [expected, "--host", "localhost", "--port", "5001"],
    }
