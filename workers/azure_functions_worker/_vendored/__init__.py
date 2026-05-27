# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Private vendored copies of third-party packages.

This package isolates the worker's dependencies (currently
``google.protobuf``) from whatever versions the customer ships in
``.python_packages``. The packages under this namespace are populated at
build time by ``eng/scripts/vendor_deps.py`` and are not committed to
source control.

Two invariants:

1. Importing anything from this package must not pull in ``google.protobuf``
   or ``grpc`` from the customer's site-packages. The vendoring script
   rewrites every ``from google.protobuf`` / ``import google.protobuf``
   reference inside the vendored tree so that all internal cross-imports
   resolve under ``azure_functions_worker._vendored``.

2. The vendored protobuf runs under its pure-Python implementation so we
   don't have to ship per-Python C extensions. The environment variable
   below must be set before any vendored protobuf module is imported.
"""

import os

# Force the pure-Python protobuf implementation for the vendored copy. This
# avoids having to vendor (and rebuild) C extensions across the Python
# version / OS / arch matrix. Worker proto traffic is the host<->worker
# control channel only, not the invocation hot path, so the pure-Python
# overhead is negligible.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
