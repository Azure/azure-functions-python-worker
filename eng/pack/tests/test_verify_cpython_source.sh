#!/bin/bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFIER="$SCRIPT_DIR/../scripts/verify_cpython_source.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

# The source archive is not a runnable x64 host Python. An empty agent cache
# must still permit UsePythonVersion to acquire the pinned build interpreter.
awk '/^- task: UsePythonVersion@0$/ { inside = 1; next }
     inside && /^- / { exit }
     inside { print }' "$SCRIPT_DIR/../templates/r2p2_env_gen.yml" > "$TEST_ROOT/python-task"
grep -Eq '^[[:space:]]+disableDownloadFromRegistry: false$' "$TEST_ROOT/python-task"
if grep -Eq '^[[:space:]]+disableDownloadFromRegistry: true$' "$TEST_ROOT/python-task"; then
   echo 'UsePythonVersion must allow acquisition on a host-interpreter cache miss.' >&2
   exit 1
fi

ARCHIVE="$TEST_ROOT/source archive.tgz"
printf 'known source bytes\n' > "$ARCHIVE"
DIGEST="$(sha256sum < "$ARCHIVE")"
DIGEST="${DIGEST%% *}"

expect_failure() {
   local expected="$1"
   shift
   if bash "$VERIFIER" "$@" > "$TEST_ROOT/output" 2>&1; then
      echo "Expected verification failure: $expected" >&2
      exit 1
   fi
   grep -F "$expected" "$TEST_ROOT/output" > /dev/null
}

bash "$VERIFIER" "$ARCHIVE" "$DIGEST"
bash "$VERIFIER" "$ARCHIVE" "${DIGEST^^}"
expect_failure 'CPYTHON_ARM64_ARCHIVE' '' "$DIGEST"
expect_failure 'CPYTHON_ARM64_ARCHIVE' "$TEST_ROOT/missing.tgz" "$DIGEST"
expect_failure 'CPYTHON_ARM64_SHA256' "$ARCHIVE" ''
expect_failure 'CPYTHON_ARM64_SHA256' "$ARCHIVE" 'not-a-digest'
expect_failure 'CPYTHON_ARM64_SHA256' "$ARCHIVE" "${DIGEST}0"
expect_failure 'CPYTHON_ARM64_SHA256' "$ARCHIVE" "$DIGEST"$'\n'
printf 'tampered bytes\n' >> "$ARCHIVE"
expect_failure 'SHA-256 mismatch' "$ARCHIVE" "$DIGEST"

# Exercise the build entrypoint: a corrupt archive must fail before Python setup.
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
if BUILD_SOURCESDIRECTORY="$REPO_ROOT" \
   CPYTHON_ARM64_ARCHIVE="$ARCHIVE" CPYTHON_ARM64_SHA256="$DIGEST" \
   bash -c '
      uname() { printf "Linux\n"; }
      python() { echo "UNEXPECTED_PYTHON_SETUP" >&2; return 99; }
      export -f uname python
      bash "$1" 3.15.2 arm64
   ' _ "$SCRIPT_DIR/../scripts/r2p2_deps.sh" > "$TEST_ROOT/output" 2>&1; then
   echo 'Expected the build entrypoint to reject corrupt source.' >&2
   exit 1
fi
grep -F 'SHA-256 mismatch' "$TEST_ROOT/output" > /dev/null
if grep -F 'UNEXPECTED_PYTHON_SETUP' "$TEST_ROOT/output" > /dev/null; then
   echo 'Python setup ran before source verification.' >&2
   exit 1
fi
echo 'All CPython source verification tests passed.'