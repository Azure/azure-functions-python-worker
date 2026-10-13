#!/bin/bash
set -euo pipefail

cargo_config="$1"
manifest_path="$(dirname "$(dirname "$cargo_config")")/Cargo.toml"

if [[ "$cargo_config" != *.public.toml ]]; then
    exit 0
fi

if ! command -v cargo >/dev/null 2>&1; then
    echo "cargo is required before preparing Cargo authentication" >&2
    exit 1
fi

test "${CARGO_REGISTRIES_PYTHONWORKER_PUBLICPACKAGES_CREDENTIAL_PROVIDER:-}" = "cargo:token"

# The public feed advertises auth-required=false, but uncached upstream crates
# require authentication. Initialize Cargo's sparse cache, then correct its
# cached metadata before retrying the command that invoked this setup.
cargo --config "$cargo_config" fetch --manifest-path "$manifest_path" --locked || true
python - "$cargo_config" <<'PY'
import json
import os
from pathlib import Path
import sys
import tomllib
from urllib.request import urlopen

cargo_config = Path(sys.argv[1])
with cargo_config.open("rb") as config_file:
    registries = tomllib.load(config_file)["registries"]

if len(registries) != 1:
    raise RuntimeError(f"Expected one Cargo registry, found {len(registries)}")

index_url = next(iter(registries.values()))["index"].removeprefix("sparse+")
with urlopen(f"{index_url}config.json") as response:
    expected_api = json.load(response)["api"].rstrip("/").lower()

cargo_home = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))
matches = []
for cached_config in (cargo_home / "registry" / "index").glob("*/config.json"):
    with cached_config.open(encoding="utf-8") as config_file:
        metadata = json.load(config_file)
    if metadata.get("api", "").rstrip("/").lower() == expected_api:
        metadata["auth-required"] = True
        cached_config.write_text(json.dumps(metadata), encoding="utf-8")
        matches.append(cached_config)

if len(matches) != 1:
    raise RuntimeError(
        f"Expected one cached config for {expected_api}, found {len(matches)}"
    )
print(f"Enabled Cargo authentication in {matches[0]}")
PY