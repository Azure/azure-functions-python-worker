#!/bin/bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# Verify the reviewed digest before extracting or executing CPython source.
set -euo pipefail

ARCHIVE="${1:-}"
EXPECTED_SHA256="${2:-}"
if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
   echo "CPYTHON_ARM64_ARCHIVE must point to an existing pipeline-staged source archive." >&2
   exit 1
fi
if [[ ! "$EXPECTED_SHA256" =~ ^[[:xdigit:]]{64}$ ]]; then
   echo "CPYTHON_ARM64_SHA256 must contain the reviewed 64-character SHA-256 digest." >&2
   exit 1
fi

# Hash stdin so filenames containing spaces or backslashes cannot alter parsing.
ACTUAL_SHA256="$(sha256sum < "$ARCHIVE")"
ACTUAL_SHA256="${ACTUAL_SHA256%% *}"
if [[ "$ACTUAL_SHA256" != "${EXPECTED_SHA256,,}" ]]; then
   echo "CPython source SHA-256 mismatch: expected ${EXPECTED_SHA256,,}, got $ACTUAL_SHA256." >&2
   exit 1
fi
echo "Verified CPython source SHA-256: $ACTUAL_SHA256"