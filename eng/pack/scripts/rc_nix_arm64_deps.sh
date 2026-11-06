#!/bin/bash
# Keep RC payloads subject to the same dependency constraints as stable builds.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/nix_arm64_deps_common.sh" "$@"