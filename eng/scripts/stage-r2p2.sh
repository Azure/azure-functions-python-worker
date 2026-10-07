#!/bin/bash
set -euo pipefail

repo_root="${BUILD_SOURCESDIRECTORY:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
r2p2_dir="$repo_root/workers/r2p2"
worker_dir="$repo_root/workers/python/test_r2p2"
binary="$r2p2_dir/target/release/r2p2"

if [[ ! -f "$binary" ]]; then
    echo "R2P2 binary not found: $binary" >&2
    exit 1
fi
if [[ ! -d "$r2p2_dir/bridge" ]]; then
    echo "R2P2 bridge not found: $r2p2_dir/bridge" >&2
    exit 1
fi

rm -rf "$worker_dir"
mkdir -p "$worker_dir"
cp "$binary" "$worker_dir/r2p2"
chmod +x "$worker_dir/r2p2"
cp -r "$r2p2_dir/bridge" "$worker_dir/bridge"

cat > "$worker_dir/worker.config.json" <<JSON
{
    "description": {
        "language": "python",
        "defaultRuntimeVersion": "3.15",
        "supportedRuntimeVersions": ["3.15"],
        "supportedOperatingSystems": ["LINUX"],
        "supportedArchitectures": ["X64"],
        "extensions": [".py"],
        "defaultExecutablePath": "$worker_dir/r2p2",
        "workerIndexing": "true"
    },
    "processOptions": {
        "initializationTimeout": "00:02:00",
        "environmentReloadTimeout": "00:02:00"
    }
}
JSON

echo "Staged R2P2 at $worker_dir:"
ls -la "$worker_dir"