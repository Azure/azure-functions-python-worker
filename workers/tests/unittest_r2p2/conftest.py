# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Put the R2P2 bridge directory on sys.path so the tests can import the pure
# Python bridge (``bridge`` + ``protos_adapter``) directly, with no built Rust
# binary and no installed runtime. ``bridge.py`` imports ``protos_adapter`` at
# module load (a protobuf-free, dependency-free module) and imports the
# ``azure_functions_runtime`` lazily inside ``configure()``, so importing the
# module for unit testing needs nothing beyond the standard library.
import os
import sys

BRIDGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "r2p2", "bridge")
)

if BRIDGE_DIR not in sys.path:
    sys.path.insert(0, BRIDGE_DIR)
