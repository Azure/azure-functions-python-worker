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

fn encode_bytes(item: Bytes, dst: &mut impl BufMut) {
    dst.put_slice(&item);
}

impl Encoder for BytesEncoder {
    type Item = Bytes;
    type Error = Status;

    fn encode(&mut self, item: Bytes, dst: &mut EncodeBuf<'_>) -> Result<(), Status> {
        encode_bytes(item, dst);
        Ok(())
    }
}

pub struct BytesDecoder;

fn decode_bytes(src: &mut impl Buf) -> Option<Bytes> {
    if !src.has_remaining() {
        return None;
    }
    let len = src.remaining();
    Some(src.copy_to_bytes(len))
}

impl Decoder for BytesDecoder {
    type Item = Bytes;
    type Error = Status;

    // tonic strips the gRPC 5-byte frame header and hands us exactly one
    // message worth of bytes per call.
    fn decode(&mut self, src: &mut DecodeBuf<'_>) -> Result<Option<Bytes>, Status> {
        Ok(decode_bytes(src))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::BytesMut;

    #[test]
    fn codec_creates_raw_bytes_encoder_and_decoder() {
        let mut codec = BytesCodec;

        let _: BytesEncoder = codec.encoder();
        let _: BytesDecoder = codec.decoder();
    }

    #[test]
    fn encoder_copies_exact_payload() {
        let mut destination = BytesMut::from(&b"prefix"[..]);

        encode_bytes(Bytes::from_static(&[0, 1, 2, 255]), &mut destination);

        assert_eq!(&destination[..], b"prefix\x00\x01\x02\xff");
    }

    #[test]
    fn decoder_returns_all_remaining_bytes() {
        let mut source = Bytes::from_static(&[0, 1, 2, 255]);

        assert_eq!(
            decode_bytes(&mut source),
            Some(Bytes::from_static(&[0, 1, 2, 255]))
        );
        assert!(!source.has_remaining());
    }

    #[test]
    fn decoder_returns_none_for_empty_payload() {
        let mut source = Bytes::new();

        assert_eq!(decode_bytes(&mut source), None);
    }
}
