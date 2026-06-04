# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

# Runtime requirement, not a build-time/pipeline setting: protobuf selects its
# implementation when google.protobuf modules are imported in this worker
# process. Our vendored azure_functions_worker._vendored.google.protobuf tree
# deliberately contains only pure-Python files (native extensions are not
# copied), so force protobuf to use its pure-Python implementation at import
# time. This setdefault runs before any vendored protobuf import because
# azure_functions_worker/__init__.py is the package top-level module and
# executes before submodules, including _vendored.*.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
