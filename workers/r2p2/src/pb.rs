// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// prost/tonic generated types for the AzureFunctionsRpcMessages package plus the
// imported identity/shared protos. The imported .proto files declare no package,
// so prost emits them into the root ("_") file; the AzureFunctionsRpcMessages
// code references those shared types via `super::`. We therefore include the
// root types at this module level and nest the message package one level deeper
// so `super::` resolves correctly.

#![allow(clippy::all)]
#![allow(dead_code)]

// Root (packageless) protos: RpcClaimsIdentity, RpcClaim, NullableString, ...
include!(concat!(env!("OUT_DIR"), "/_.rs"));

// AzureFunctionsRpcMessages package: StreamingMessage, InvocationRequest,
// TypedData, RpcHttp, ... and the FunctionRpc gRPC client. Nested so its
// `super::` references resolve to the root types included above.
pub mod messages {
    include!(concat!(env!("OUT_DIR"), "/azure_functions_rpc_messages.rs"));
}
