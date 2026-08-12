// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// Generates Rust types + the FunctionRpc gRPC client from the vendored protobuf
// definitions using prost/tonic. We point tonic-build at the protoc binary that
// `protoc-bin-vendored` ships, so builds need no system protobuf compiler (works
// identically on the dev box and inside the Docker builder).

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let protoc = protoc_bin_vendored::protoc_bin_path()?;
    std::env::set_var("PROTOC", protoc);

    tonic_build::configure()
        .build_server(false)
        .build_client(true)
        .compile_protos(&["proto/FunctionRpc.proto"], &["proto"])?;

    println!("cargo:rerun-if-changed=proto");
    Ok(())
}
