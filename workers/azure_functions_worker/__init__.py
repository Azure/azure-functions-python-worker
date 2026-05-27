# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

# The worker's generated protobuf stubs (azure_functions_worker.protos.*)
# import from azure_functions_worker._vendored.google.protobuf, which is a
# pure-Python build of protobuf vendored at build time. Force the
# pure-Python implementation here so that any vendored protobuf module
# imported transitively never tries to load a C extension. This must run
# before any submodule import that touches protobuf.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
