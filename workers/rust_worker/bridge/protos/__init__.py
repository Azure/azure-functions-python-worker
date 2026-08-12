# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""The bridge's private, gRPC-free protobuf message package.

This is the Rust worker's own copy of the FunctionRpc message classes, so the
bridge does not import ``proxy_worker`` (not shipped for Python 3.15) and does
not drag in ``grpcio`` (tonic owns the transport). Only the protobuf *message*
stubs are exposed here -- no ``*_pb2_grpc`` service stubs.

The ``*_pb2.py`` modules imported below are produced at build time (and for
local dev) by ``workers/rust_worker/gen_protos.py`` and are not committed;
only this shim and the package ``__init__.py`` files are.
"""
from .FunctionRpc_pb2 import (  # NoQA
    StreamingMessage,
    StartStream,
    WorkerInitRequest,
    WorkerInitResponse,
    RpcFunctionMetadata,
    FunctionLoadRequest,
    FunctionLoadResponse,
    FunctionEnvironmentReloadRequest,
    FunctionEnvironmentReloadResponse,
    InvocationRequest,
    InvocationResponse,
    WorkerHeartbeat,
    WorkerStatusRequest,
    WorkerStatusResponse,
    BindingInfo,
    StatusResult,
    RpcException,
    ParameterBinding,
    TypedData,
    RpcHttp,
    RpcHttpCookie,
    RpcLog,
    RpcSharedMemory,
    RpcDataType,
    CloseSharedMemoryResourcesRequest,
    CloseSharedMemoryResourcesResponse,
    FunctionsMetadataRequest,
    FunctionMetadataResponse,
    WorkerMetadata,
    RpcRetryOptions)

from .shared.NullableTypes_pb2 import (  # NoQA
    NullableString,
    NullableBool,
    NullableDouble,
    NullableTimestamp)
