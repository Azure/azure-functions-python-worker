#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Materialize the bridge's private, gRPC-free ``protos`` package.

The Rust worker's bridge must not import ``proxy_worker`` at runtime (for
Python 3.15 only the Rust worker ships; ``proxy_worker`` does not). It also must
not drag in ``grpcio`` (tonic owns the transport). This script produces a
self-contained ``bridge/protos`` package that exposes exactly the protobuf
*message* classes the bridge and the v2 runtime need, and nothing else.

It works by copying the protobuf message stubs (``*_pb2.py``; the gRPC service
stubs ``*_pb2_grpc.py`` are skipped) from an existing ``proxy_worker/protos``
tree and rewriting their absolute imports from ``proxy_worker.protos`` to
``protos`` so the copied tree stands alone.

Why copy instead of regenerate: the generated stubs embed a ``runtime_version``
guard that hard-fails on a protobuf major-version mismatch, so they must match
the protobuf runtime they execute against. The target Functions images bundle a
version-correct ``proxy_worker/protos`` but have no ``protoc``/``grpc_tools`` and
no network, so regenerating from ``.proto`` there is not possible. Copying the
environment's own already-version-correct stubs keeps the bridge stubs matched
to whatever protobuf the environment ships.

Committed to the bridge (hand-maintained): ``protos/__init__.py`` (the gRPC-free
re-export shim) and the package ``__init__.py`` files. Produced here and
git-ignored: the ``*_pb2.py`` message stubs. Run at Docker build and for local
development, for example::

    python workers/rust_worker/gen_protos.py \
        --source workers/proxy_worker/protos \
        --out workers/rust_worker/bridge/protos
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SRC_PACKAGE = "proxy_worker.protos"
_DST_PACKAGE = "protos"


def _copy_stub(src_file: Path, dst_file: Path) -> None:
    """Copy one ``*_pb2.py`` stub, rewriting its package-absolute imports."""
    text = src_file.read_text(encoding="utf-8")
    # The only cross-stub imports use the fully-qualified source package
    # (e.g. ``from proxy_worker.protos.shared import NullableTypes_pb2``).
    # Repoint them at the bridge's private package so the tree is self-contained.
    text = text.replace(_SRC_PACKAGE, _DST_PACKAGE)
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    dst_file.write_text(text, encoding="utf-8")


def _ensure_package_init(directory: Path) -> None:
    """Create an empty ``__init__.py`` if one is not already committed."""
    init = directory / "__init__.py"
    if not init.exists():
        init.write_text(
            "# Copyright (c) Microsoft Corporation. All rights reserved.\n"
            "# Licensed under the MIT License.\n",
            encoding="utf-8",
        )


def materialize(source: Path, out: Path) -> int:
    """Copy message stubs from ``source`` into ``out``. Returns files copied."""
    if not source.is_dir():
        raise SystemExit(f"--source {source!s} is not a directory")
    out.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src_file in sorted(source.rglob("*_pb2.py")):
        # Skip gRPC service stubs; the bridge never speaks gRPC in Python.
        if src_file.name.endswith("_pb2_grpc.py"):
            continue
        rel = src_file.relative_to(source)
        dst_file = out / rel
        _copy_stub(src_file, dst_file)
        _ensure_package_init(dst_file.parent)
        copied += 1
    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Path to an existing proxy_worker/protos directory to copy from.",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Destination bridge/protos directory.",
    )
    args = parser.parse_args(argv)

    source = args.source.resolve()
    out = args.out.resolve()
    copied = materialize(source, out)
    if copied == 0:
        print(f"No *_pb2.py stubs found under {source}", file=sys.stderr)
        return 1
    print(f"Materialized {copied} message stub(s) from {source} into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
