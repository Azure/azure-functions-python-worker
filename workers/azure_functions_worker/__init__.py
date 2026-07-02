# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import importlib.util
import os
import re
import sys

# Protobuf runtime selection
#
# The worker's generated ``*_pb2.py`` stubs, loader and converters all
# import top-level ``google.protobuf``, so the whole worker shares one
# protobuf runtime and descriptor pool. Which protobuf that is depends on
# what is first on ``sys.path`` (the function app's ``.python_packages`` and
# PYTHONPATH precede the worker's own protobuf):
#
# 1. The protobuf on the path is the same or newer than the worker's
#    vendored copy (including the worker's own protobuf, or protobuf 6.x
#    shipped by an extension): use it directly. The worker's stubs run fine
#    on a same-or-newer runtime.
#
# 2. The protobuf on the path is older than the vendored copy (e.g. an app
#    pins protobuf 4.x): alias top-level ``google.protobuf`` to the vendored
#    copy in ``sys.modules`` and force pure-Python
#    (``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python``), so the worker's
#    stubs do not load against an incompatible protobuf. The app's older
#    protobuf is shadowed for the whole process.
#
# Override via ``_AZFUNC_USE_VENDORED_PROTOBUF``: ``"1"`` forces activation,
# ``"0"`` forces off, unset autodetects by comparing versions.

_USE_VENDORED_PROTOBUF_ENV = "_AZFUNC_USE_VENDORED_PROTOBUF"


def _parse_protobuf_version(version_str):
    """Parse a protobuf version string into a comparable tuple of ints.

    Only the leading numeric dotted components are used; any pre-release
    or local suffix (e.g. ``rc1``) is ignored. Returns ``None`` if no
    numeric version can be parsed.
    """
    parts = []
    for token in version_str.split('.'):
        match = re.match(r'\d+', token.strip())
        if not match:
            break
        parts.append(int(match.group()))
    return tuple(parts) if parts else None


def _read_protobuf_version(protobuf_dir):
    """Read ``__version__`` from a ``google/protobuf`` package directory
    without importing it. Returns a comparable version tuple or ``None``
    when it cannot be determined.
    """
    init_path = os.path.join(protobuf_dir, "__init__.py")
    try:
        with open(init_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None
    match = re.search(
        r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
    if not match:
        return None
    return _parse_protobuf_version(match.group(1))


def _vendored_protobuf_dir():
    return os.path.join(
        os.path.dirname(__file__),
        "_vendored", "google", "protobuf",
    )


def _find_importable_protobuf_dir():
    """Return the directory of the top-level ``google.protobuf`` that would
    be imported from ``sys.path``, without importing it. None if not found.
    """
    try:
        spec = importlib.util.find_spec("google.protobuf")
    except (ImportError, ValueError, AttributeError):
        return None
    if spec is None or not spec.origin:
        return None
    return os.path.dirname(spec.origin)


def _should_use_vendored_protobuf() -> bool:
    """Return True if the worker should activate its private pure-Python
    ``google.protobuf`` fallback for this process.

    ``_AZFUNC_USE_VENDORED_PROTOBUF`` forces the choice when set. Otherwise
    we look at the ``google.protobuf`` that would be imported from
    ``sys.path`` and fall back to the vendored copy only when it is older
    than ours; a same-or-newer protobuf (including the worker's own) is used
    directly, so protobuf-6 extensions load and the worker keeps ``upb``.
    """
    override = os.environ.get(_USE_VENDORED_PROTOBUF_ENV)
    if override == "1":
        return True
    if override == "0":
        return False

    protobuf_dir = _find_importable_protobuf_dir()
    if protobuf_dir is None:
        return False
    if "_vendored" in protobuf_dir.split(os.sep):
        # Already resolves to our vendored copy.
        return False

    app_version = _read_protobuf_version(protobuf_dir)
    vendored_version = _read_protobuf_version(_vendored_protobuf_dir())
    if app_version is None or vendored_version is None:
        # Cannot compare versions; insulate the worker (old behavior).
        return True
    # Fall back to vendored only when the path protobuf is older than ours.
    return app_version < vendored_version


def _activate_vendored_protobuf() -> None:
    """Pre-import the vendored protobuf modules and alias them under the
    top-level ``google.protobuf`` names so the worker's pb2 stubs resolve to
    the vendored copy instead of the function app's.
    """
    try:
        import importlib

        # Alias only the protobuf-specific names, not the top-level
        # ``google`` package: the vendored ``google`` covers only our tree,
        # so aliasing it would shadow other ``google.*`` the function app
        # ships (``google.cloud.*``, ``google.auth``, etc.). ``from
        # google.protobuf import X`` short-circuits on
        # ``sys.modules["google.protobuf"]``, so aliasing the leaves is enough.
        modules_to_alias = (
            "google.protobuf",
            "google.protobuf.internal",
        )
        for top_name in modules_to_alias:
            vendored_name = "azure_functions_worker._vendored." + top_name
            mod = importlib.import_module(vendored_name)
            # Force the alias even if the name is already in ``sys.modules``;
            # ``setdefault`` would let an early import keep the slot.
            sys.modules[top_name] = mod
    except ImportError:
        # Vendored tree may be absent in some dev workflows (before
        # ``vendor_deps.py`` runs). Stay quiet; a later import surfaces it.
        return


if _should_use_vendored_protobuf():
    # Force pure-Python before importing the vendored modules so its
    # ``api_implementation`` does not load an incompatible ``_upb``.
    os.environ.setdefault(
        "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python"
    )
    _activate_vendored_protobuf()
# else: nothing to do. Stubs resolve top-level google.protobuf to the
# worker's own protobuf and use upb. No log on this path; it runs on every
# startup and gives no actionable signal.


del _should_use_vendored_protobuf
del _activate_vendored_protobuf
