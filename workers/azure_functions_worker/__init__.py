# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys

# ---------------------------------------------------------------------------
# Protobuf runtime selection
# ---------------------------------------------------------------------------
#
# The worker's generated ``*_pb2.py`` stubs import ``google.protobuf``
# at the top level. Two scenarios:
#
# 1. The function app does NOT ship its own ``google.protobuf``. The
#    top-level lookup resolves to the protobuf install that ships with
#    the worker runtime (under ``worker_deps_path`` on Azure Functions),
#    which is guaranteed compatible with the worker's pb2 stubs and
#    includes the fast ``upb`` C extension. Nothing to do here.
#
# 2. The function app DOES ship ``google.protobuf`` in
#    ``.python_packages``. On Azure Functions the customer's path
#    precedes the worker's on ``sys.path``, so a top-level
#    ``import google.protobuf`` resolves to the customer's copy. If the
#    customer pinned an older protobuf (the common case is 4.x) the
#    worker's pb2 stubs fail to load — for example ``from
#    google.protobuf import runtime_version`` does not exist before
#    protobuf 5.27. To insulate the worker from the customer's pin we:
#       a. Pre-import the vendored ``google.protobuf`` modules and
#          register them in ``sys.modules`` under their top-level names
#          so subsequent ``from google.protobuf import X`` resolves to
#          the vendored copy.
#       b. Force the vendored copy onto its pure-Python implementation
#          via ``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`` so the
#          vendored ``api_implementation`` does not try to load the
#          customer's ``google._upb._message`` C extension (which would
#          be incompatible with vendored protobuf and unsafe to load
#          alongside another ``_upb`` instance).
#
# Side effect of scenario 2: customer code that does ``import
# google.protobuf`` later in the process will resolve to the vendored
# copy rather than the customer's pinned copy. This trade-off is
# necessary because protobuf's runtime assumes a single coherent
# ``google.protobuf`` package per process.
#
# Detection cost: a single ``os.path.isdir`` call (and at most one
# ``importlib.util.find_spec`` fallback) at worker startup. Zero per
# invocation.


def _customer_ships_protobuf() -> bool:
    """Return True if the function app ships its own google.protobuf
    (directly or as a transitive dependency).

    We only check the canonical Azure Functions deployment layout —
    ``<AzureWebJobsScriptRoot>/.python_packages/lib/site-packages/google/
    protobuf``. We deliberately do *not* fall back to a generic
    ``importlib.util.find_spec`` lookup because that would also match
    the worker's own protobuf install (which is always on ``sys.path``
    and is not "customer protobuf"). A false positive there would
    activate the pure-Python vendored fallback for every function app,
    erasing the perf benefit of running the worker on ``upb``.
    """
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
    return os.path.isdir(candidate)


def _activate_vendored_protobuf() -> None:
    """Pre-import the vendored protobuf modules and alias them under
    the top-level ``google.protobuf`` names so the worker's pb2 stubs
    resolve to the vendored copy instead of the customer's pinned one.
    """
    try:
        import importlib

        # Alias only the protobuf-specific names. Do NOT alias the
        # top-level ``google`` package: the vendored ``google`` is a
        # regular package whose ``__path__`` covers only our vendored
        # tree, so aliasing it would shadow every other ``google.*``
        # the customer ships (``google.cloud.*``, ``google.auth``,
        # ``google.api_core``, etc.). Those packages are the most
        # common reason a customer ends up with protobuf in their
        # dependencies in the first place, so breaking them would
        # defeat the purpose of the fallback. ``from google.protobuf
        # import X`` short-circuits on ``sys.modules["google.protobuf"]``
        # without consulting ``sys.modules["google"]``, so aliasing
        # only the leaves is sufficient.
        modules_to_alias = (
            "google.protobuf",
            "google.protobuf.internal",
        )
        for top_name in modules_to_alias:
            vendored_name = "azure_functions_worker._vendored." + top_name
            mod = importlib.import_module(vendored_name)
            # Force the alias even if something already populated
            # ``sys.modules`` for the top-level name. The whole point
            # of activation is "the customer's protobuf must not be
            # what the worker's pb2 stubs see"; ``setdefault`` would
            # let an early customer import keep the slot.
            sys.modules[top_name] = mod
    except ImportError:
        # Vendored tree may be absent in some dev workflows (before
        # ``vendor_deps.py`` has been run). Stay quiet here; the next
        # worker import will surface a clearer error.
        return


if _customer_ships_protobuf():
    # Force the vendored copy onto pure-Python BEFORE pre-importing
    # any of its modules, so that vendored ``api_implementation``
    # doesn't try to load a (potentially incompatible) ``_upb``.
    os.environ.setdefault(
        "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python"
    )
    _activate_vendored_protobuf()
    if os.environ.get("AZURE_FUNCTIONS_PYTHON_PROTOBUF_DEBUG"):
        # Opt-in diagnostic. Off by default to avoid polluting
        # customer logs / log scrapers that treat stderr as warning.
        print(
            "[azure_functions_worker] Customer ships google.protobuf; "
            "activated vendored pure-Python fallback.",
            file=sys.stderr,
        )
# else: nothing to do. Worker's pb2 stubs will resolve top-level
# google.protobuf to the worker's own protobuf install and use upb
# naturally. We deliberately do NOT log on the no-op path: it would
# run on every worker startup for the entire fleet and provides no
# actionable signal to customers.


del _customer_ships_protobuf
del _activate_vendored_protobuf
