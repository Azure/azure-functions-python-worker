# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Validate downloaded official-build payloads required by the NuGet manifest.

Run only after all worker build jobs publish their pipeline artifacts. Checks
are structural/cross-platform; native import checks remain in the producer jobs.
"""

import argparse
from pathlib import Path, PureWindowsPath
import re
import runpy
import xml.etree.ElementTree as ET


# Resolve the trusted sibling explicitly, including under Python -I -S.
_validator = runpy.run_path(str(Path(__file__).with_name("validate_worker_payload.py")))
parse_python_version = _validator["parse_python_version"]
validate_contents = _validator["validate_contents"]


GRPC_BUILDS = {
    ("WINDOWS", "x64"): "win_amd64.pyd",
    ("WINDOWS", "x86"): "win32.pyd",
    ("LINUX", "x64"): "x86_64-linux-gnu.so",
    ("LINUX", "arm64"): "aarch64-linux-gnu.so",
    ("OSX", "x64"): "darwin.so",
    ("OSX", "arm64"): "darwin.so",
}


def required_payloads(nuspec):
    """Use explicit package inputs, not whatever artifact folders happen to exist."""
    payloads = []
    for element in ET.parse(nuspec).getroot().findall("{*}files/{*}file"):
        parts = PureWindowsPath(element.attrib["target"]).parts
        if not parts or parts[0] != "tools" or len(parts) == 1:
            continue
        if len(parts) != 4:
            raise ValueError(f"Unsupported worker target: {element.attrib['target']}")
        _, version, os_name, architecture = parts
        architecture = architecture.lower()
        if (not re.fullmatch(r"\d+\.\d+", version)
            or os_name not in ("WINDOWS", "LINUX", "OSX")
            or architecture not in ("x86", "x64", "arm64")):
            raise ValueError(f"Unsupported worker target: {parts}")
        source = PureWindowsPath(element.attrib["src"]).parts
        if len(source) != 4 or source[:2] != ("..", "..") or source[-1] != "**":
            raise ValueError(f"Unsupported worker source: {element.attrib['src']}")
        payloads.append((source[2], version, os_name, architecture))
    if not payloads:
        raise ValueError("NuGet manifest contains no worker payloads")
    return payloads


def validate_published_payloads(root, nuspec):
    payloads = required_payloads(nuspec)
    for artifact, version, os_name, architecture in payloads:
        path = Path(root) / artifact
        if not path.is_dir():
            raise RuntimeError(f"Missing published worker artifact: {artifact}")
        validate_contents(path, parse_python_version(version), os_name,
                          architecture, GRPC_BUILDS.get((os_name, architecture)))
    print(f"Validated all {len(payloads)} published worker payloads", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--nuspec", required=True, type=Path)
    args = parser.parse_args()
    validate_published_payloads(args.root, args.nuspec)


if __name__ == "__main__":
    main()