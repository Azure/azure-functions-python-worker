#!/bin/bash
# Stable and RC builds must use the same wheel and proto-generation workflow.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/nix_arm64_deps_common.sh" "$@"