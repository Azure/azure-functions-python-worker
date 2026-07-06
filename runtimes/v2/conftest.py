# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Pytest configuration for the v2 runtime test tree.

The v2 tests import via ``tests.protos``, ``tests.utils``, and friends.
The ``workers/`` tree in this repository also has a regular ``tests``
package, so without explicit sys.path control the wrong tree wins
depending on the current working directory or whether the worker
package was installed editable.

Forcing ``runtimes/v2`` to the front of ``sys.path`` from this
conftest guarantees that ``import tests.protos`` resolves to
``runtimes/v2/tests/protos`` no matter where pytest is invoked from.
"""
import os
import sys

_V2_ROOT = os.path.dirname(os.path.abspath(__file__))
if _V2_ROOT not in sys.path:
    sys.path.insert(0, _V2_ROOT)
elif sys.path.index(_V2_ROOT) != 0:
    sys.path.remove(_V2_ROOT)
    sys.path.insert(0, _V2_ROOT)
