# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import re
import sys

# Protobuf runtime selection
#
# The worker's generated ``*_pb2.py`` stubs, loader and converters all
# import top-level ``google.protobuf``, so the whole worker shares one
# protobuf runtime and descriptor pool. Which protobuf that is depends on
# what the function app ships:
#
# 1. Function app ships no ``google.protobuf``: top-level resolves to the
#    worker's own protobuf (with the fast ``upb`` C extension). Nothing to do.
#
# 2. Function app ships ``google.protobuf`` in ``.python_packages`` (its
#    path precedes the worker's on ``sys.path``):
#
#    2a. Its protobuf is OLDER than the vendored copy (commonly 4.x): the
#        worker's pb2 stubs would fail on it. Alias top-level
#        ``google.protobuf`` to the vendored copy in ``sys.modules`` and
#        force pure-Python (``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python``)
#        so it does not load a mismatched ``_upb``.
#
#    2b. Its protobuf is the SAME or NEWER (e.g. protobuf 6.x from an
#        extension like the ServiceBus SDK binding): use it directly, no
#        alias. The worker's stubs run fine on a newer runtime, and forcing
#        a newer copy onto the older vendored one would raise a gencode
#        ``VersionError``.
#
# Note for 2a: function app code that imports ``google.protobuf`` then
# resolves to the vendored copy, since protobuf assumes one coherent
# ``google.protobuf`` per process.
#
# Override via ``_AZFUNC_USE_VENDORED_PROTOBUF``: ``"1"`` forces activation
# (set by the local-dev launcher ``worker.py``), ``"0"`` forces off, unset
# autodetects via ``.python_packages`` (the production path).

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


def _should_use_vendored_protobuf() -> bool:
    """Return True if the worker should activate its private pure-Python
    ``google.protobuf`` fallback for this process.

    The launcher (``worker.py``) sets ``_AZFUNC_USE_VENDORED_PROTOBUF`` to
    force the choice; when unset we autodetect via the ``.python_packages``
    layout.

    When the function app ships its own ``google.protobuf`` we fall back to
    the vendored copy only if that protobuf is older than ours. If it is the
    same or newer (e.g. protobuf 6.x from an extension) we use it directly,
    since the worker's stubs run on a newer runtime and forcing the newer
    copy onto the older vendored one would raise a ``VersionError``.

    We avoid a generic ``importlib.util.find_spec`` fallback: it would also
    match the worker's own protobuf install and needlessly force pure-Python
    for every function app.
    """
    override = os.environ.get(_USE_VENDORED_PROTOBUF_ENV)
    if override == "1":
        return True
    if override == "0":
        return False
    script_root = os.environ.get("AzureWebJobsScriptRoot")
    if not script_root:
        return False
    candidate = os.path.join(
        script_root,
        ".python_packages",
        "lib",
        "site-packages",
        "google",
        "protobuf",
    )
    if not os.path.isdir(candidate):
        return False

    app_version = _read_protobuf_version(candidate)
    vendored_version = _read_protobuf_version(_vendored_protobuf_dir())
    if app_version is None or vendored_version is None:
        # Cannot compare versions; insulate the worker (old behavior).
        return True
    # Fall back to vendored only when the app's protobuf is older than ours.
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
