// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// A raw-bytes tonic Codec. Protobuf work stays in the Python bridge, so the
// Rust transport never needs prost/protoc: it just carries the already
// length-prefixed `StreamingMessage` payloads across the wire as opaque bytes.

use bytes::{Buf, BufMut, Bytes};
use tonic::codec::{Codec, DecodeBuf, Decoder, EncodeBuf, Encoder};
use tonic::Status;

#[derive(Default, Clone)]
pub struct BytesCodec;

impl Codec for BytesCodec {
    type Encode = Bytes;
    type Decode = Bytes;
    type Encoder = BytesEncoder;
    type Decoder = BytesDecoder;

    fn encoder(&mut self) -> Self::Encoder {
        BytesEncoder
    }

    fn decoder(&mut self) -> Self::Decoder {
        BytesDecoder
    }
}

pub struct BytesEncoder;

impl Encoder for BytesEncoder {
    type Item = Bytes;
    type Error = Status;

    fn encode(&mut self, item: Bytes, dst: &mut EncodeBuf<'_>) -> Result<(), Status> {
        dst.put_slice(&item);
        Ok(())
    }
}

pub struct BytesDecoder;

impl Decoder for BytesDecoder {
    type Item = Bytes;
    type Error = Status;

    // tonic strips the gRPC 5-byte frame header and hands us exactly one
    // message worth of bytes per call.
    fn decode(&mut self, src: &mut DecodeBuf<'_>) -> Result<Option<Bytes>, Status> {
        if !src.has_remaining() {
            return Ok(None);
        }
        let len = src.remaining();
        Ok(Some(src.copy_to_bytes(len)))
    }
}
