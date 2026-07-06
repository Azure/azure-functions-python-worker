# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Pytest configuration for the v1 runtime test tree.

The v1 tests import via ``tests.protos``, ``tests.utils``, and friends.
The ``workers/`` tree in this repository also has a regular ``tests``
package, so without explicit sys.path control the wrong tree wins
depending on the current working directory or whether the worker
package was installed editable.

Forcing ``runtimes/v1`` to the front of ``sys.path`` from this
conftest guarantees that ``import tests.protos`` resolves to
``runtimes/v1/tests/protos`` no matter where pytest is invoked from.
"""
import os
import sys

_V1_ROOT = os.path.dirname(os.path.abspath(__file__))
if _V1_ROOT not in sys.path:
    sys.path.insert(0, _V1_ROOT)
elif sys.path.index(_V1_ROOT) != 0:
    sys.path.remove(_V1_ROOT)
    sys.path.insert(0, _V1_ROOT)
