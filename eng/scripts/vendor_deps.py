#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Vendor third-party packages into the worker's private namespace.

This script copies one or more installed top-level packages (by default
``google.protobuf``) into ``azure_functions_worker/_vendored/`` and rewrites
every cross-import inside the vendored tree so that the package is
self-contained under ``azure_functions_worker._vendored``.

It is invoked from the build pipeline after ``pip install``::

    python eng/scripts/vendor_deps.py \
        --target workers/azure_functions_worker/_vendored

The script is idempotent: re-running it removes any previously vendored
content for the named packages and re-copies a fresh tree.

Design notes
------------
* Pure-Python only: native C extensions are skipped. The vendored
  protobuf runs under ``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python``
  (set in ``azure_functions_worker/__init__.py``).
* Rewrites are AST-aware to avoid mangling string literals, comments, or
  identifiers that merely contain the substring ``google.protobuf``.
  ``import`` and ``from ... import`` statements are detected via the
  ``ast`` module; the source spans they cover are replaced via
  textual substitution that preserves surrounding whitespace.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path

# Default set of packages to vendor. Each entry is a dotted top-level path;
# the *whole* package tree is vendored.
DEFAULT_PACKAGES: tuple[str, ...] = ("google.protobuf",)

# File suffixes that are treated as native extensions and skipped during
# the copy step. The vendored protobuf is required to run under its
# pure-Python implementation.
NATIVE_EXTENSION_SUFFIXES: tuple[str, ...] = (".so", ".pyd", ".dylib")

# The vendored namespace prefix that every rewritten import must point at.
VENDORED_PREFIX = "azure_functions_worker._vendored"


def _resolve_package_root(dotted_name: str) -> Path:
    """Return the on-disk directory that contains ``dotted_name``'s package.

    For ``google.protobuf`` this returns the directory ``.../google/protobuf``
    (i.e. the leaf package, not the namespace parent).
    """
    spec = importlib.util.find_spec(dotted_name)
    if spec is None or spec.origin is None:
        raise RuntimeError(
            f"Cannot find installed package {dotted_name!r}. Did you run "
            f"`pip install` first?"
        )
    origin = Path(spec.origin)
    # For a regular package, origin points at ``.../<pkg>/__init__.py``.
    if origin.name != "__init__.py":
        raise RuntimeError(
            f"Package {dotted_name!r} is not a regular package "
            f"(origin={origin!s}). Only regular packages are supported."
        )
    return origin.parent


def _copy_package(src: Path, dst: Path) -> int:
    """Copy ``src`` to ``dst`` recursively, skipping native extensions.

    Returns the number of Python source files copied.
    """
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    copied = 0
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if path.suffix in NATIVE_EXTENSION_SUFFIXES:
            continue
        # Drop bytecode caches; they will be regenerated.
        if "__pycache__" in path.parts:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if path.suffix == ".py":
            copied += 1
    return copied


def _build_rewriter(top_level_names: Iterable[str]):
    """Build a rewriter for copied vendored package files.

    ``_rewrite_tree`` applies this to the package files after ``_copy_package``
    copies them, not to worker source code. Imports targeting an original
    top-level name (for example, ``google.protobuf...``) are rewritten under
    ``VENDORED_PREFIX`` so vendored files reference the private namespace.
    Worker source imports are hand-edited; generated ``*_pb2.py`` stubs are
    rewritten separately by ``make_absolute_imports`` in ``workers/tests``.
    """
    top_levels = frozenset(top_level_names)

    def _needs_rewrite(module: str | None) -> bool:
        if not module:
            return False
        head = module.split(".", 1)[0]
        return head in top_levels

    def _rewrite_module_path(module: str) -> str:
        return f"{VENDORED_PREFIX}.{module}"

    def rewrite_source(source: str) -> tuple[str, int]:
        """Return ``(new_source, num_rewrites)``."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # Skip files we cannot parse. Vendored packages we ship are
            # known-good, but be defensive.
            return source, 0

        # Collect edits as (lineno, col_offset, end_lineno, end_col_offset,
        # replacement). ``ast`` gives us 1-based line numbers.
        edits: list[tuple[int, int, int, int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Relative imports (level > 0) are already package-local;
                # leave them alone.
                if node.level:
                    continue
                if not _needs_rewrite(node.module):
                    continue
                new_module = _rewrite_module_path(node.module or "")
                # Reconstruct the import: ``from <module> import a, b as c``.
                names = ", ".join(
                    alias.name + (f" as {alias.asname}" if alias.asname else "")
                    for alias in node.names
                )
                replacement = f"from {new_module} import {names}"
                edits.append(
                    (
                        node.lineno,
                        node.col_offset,
                        node.end_lineno or node.lineno,
                        node.end_col_offset or node.col_offset,
                        replacement,
                    )
                )
            elif isinstance(node, ast.Import):
                # ``import a, b as c`` -> rewrite per alias, then combine.
                new_aliases: list[str] = []
                changed = False
                for alias in node.names:
                    if _needs_rewrite(alias.name):
                        changed = True
                        new_name = _rewrite_module_path(alias.name)
                        if alias.asname:
                            new_aliases.append(f"{new_name} as {alias.asname}")
                        else:
                            # ``import google.protobuf`` with no alias is a
                            # binding for ``google``. Preserve callers'
                            # expectation by aliasing to the original head
                            # segment so subsequent ``google.protobuf.X``
                            # access still resolves.
                            head = alias.name.split(".", 1)[0]
                            new_aliases.append(f"{new_name} as {head}")
                    else:
                        if alias.asname:
                            new_aliases.append(
                                f"{alias.name} as {alias.asname}"
                            )
                        else:
                            new_aliases.append(alias.name)
                if not changed:
                    continue
                replacement = "import " + ", ".join(new_aliases)
                edits.append(
                    (
                        node.lineno,
                        node.col_offset,
                        node.end_lineno or node.lineno,
                        node.end_col_offset or node.col_offset,
                        replacement,
                    )
                )

        if not edits:
            return source, 0

        # Apply edits from the bottom up so earlier offsets stay valid.
        lines = source.splitlines(keepends=True)
        edits.sort(reverse=True)
        for start_line, start_col, end_line, end_col, replacement in edits:
            start_idx = sum(len(line) for line in lines[: start_line - 1]) + start_col
            end_idx = sum(len(line) for line in lines[: end_line - 1]) + end_col
            source = source[:start_idx] + replacement + source[end_idx:]
            lines = source.splitlines(keepends=True)

        return source, len(edits)

    return rewrite_source


def _rewrite_tree(root: Path, top_level_names: Iterable[str]) -> tuple[int, int]:
    """Walk ``root`` and rewrite imports in every ``.py`` file.

    Returns ``(files_rewritten, total_rewrites)``.
    """
    rewriter = _build_rewriter(top_level_names)
    files_rewritten = 0
    total_rewrites = 0
    for py_file in root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        new_text, n = rewriter(text)
        if n:
            py_file.write_text(new_text, encoding="utf-8")
            files_rewritten += 1
            total_rewrites += n
    return files_rewritten, total_rewrites


def _ensure_namespace_packages(target: Path, dotted_name: str) -> None:
    """Ensure every intermediate directory in ``dotted_name`` has __init__.py.

    For ``google.protobuf`` vendored at ``_vendored/google/protobuf``, this
    ensures ``_vendored/google/__init__.py`` exists so the namespace is a
    regular package owned by us (and not a PEP 420 namespace package that
    could collide with the customer's ``google.*``).
    """
    parts = dotted_name.split(".")
    current = target
    for part in parts[:-1]:
        current = current / part
        init = current / "__init__.py"
        if not init.exists():
            init.write_text(
                "# Copyright (c) Microsoft Corporation. All rights reserved.\n"
                "# Licensed under the MIT License.\n"
                "# Vendored namespace package. See ../README.md.\n",
                encoding="utf-8",
            )


def vendor_package(dotted_name: str, target_root: Path) -> dict:
    """Vendor a single package into ``target_root``.

    Returns a small summary dict for logging.
    """
    src = _resolve_package_root(dotted_name)
    parts = dotted_name.split(".")
    dst = target_root.joinpath(*parts)

    copied = _copy_package(src, dst)
    _ensure_namespace_packages(target_root, dotted_name)
    files_rewritten, rewrites = _rewrite_tree(
        target_root, top_level_names=[parts[0]]
    )
    return {
        "package": dotted_name,
        "source": str(src),
        "target": str(dst),
        "py_files_copied": copied,
        "files_rewritten": files_rewritten,
        "import_rewrites": rewrites,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="Path to the _vendored directory (must already exist).",
    )
    parser.add_argument(
        "--package",
        action="append",
        dest="packages",
        default=None,
        help=(
            "Dotted name of a package to vendor. May be passed multiple "
            "times. Defaults to: " + ", ".join(DEFAULT_PACKAGES) + "."
        ),
    )
    args = parser.parse_args(argv)

    target: Path = args.target.resolve()
    if not target.exists() or not target.is_dir():
        parser.error(f"--target {target!s} does not exist or is not a directory")

    init = target / ".gitignore"
    if not init.exists():
        parser.error(
            f"--target {target!s} is missing .gitignore; expected the "
            f"committed _vendored package skeleton."
        )

    packages = tuple(args.packages) if args.packages else DEFAULT_PACKAGES

    print(f"Vendoring into: {target}")
    summaries = []
    for pkg in packages:
        summary = vendor_package(pkg, target)
        summaries.append(summary)
        print(
            f"  {pkg}: copied {summary['py_files_copied']} .py files from "
            f"{summary['source']}; rewrote {summary['import_rewrites']} "
            f"imports across {summary['files_rewritten']} files."
        )

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
