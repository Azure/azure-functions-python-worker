#!/bin/bash
set -e

echo "--- pip index configuration ---"
for _f in /etc/pip.conf "${HOME}/.config/pip/pip.conf" "${HOME}/.pip/pip.ini"; do
    if [ -f "$_f" ]; then echo "  found: $_f"; else echo "  not found: $_f"; fi
done
_feed_url=$(grep -h -m1 -E '^\s*(extra-)?index-url\s*=' \
                /etc/pip.conf "${HOME}/.config/pip/pip.conf" "${HOME}/.pip/pip.ini" \
                2>/dev/null | sed 's/^[^=]*=\s*//' | awk '{print $1}')
if [ -n "$_feed_url" ]; then
    echo "  feed URL: $(echo "$_feed_url" | sed 's|://[^@]*@|://***@|')"
    echo "  setting PIP_INDEX_URL, UV_INDEX_URL, UV_KEYRING_PROVIDER=subprocess"
    export PIP_INDEX_URL="$_feed_url"
    export UV_INDEX_URL="$_feed_url"
    export UV_KEYRING_PROVIDER=subprocess
else
    echo "  no internal feed detected; installs will use PyPI"
fi

python -m pip install --upgrade pip
python -m pip install uv

UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e $1/PythonSdkArtifact
$UV_PIP -e workers/[dev]

$UV_PIP -U --prerelease=allow -e workers/[test-http-v2]
$UV_PIP -U --prerelease=allow -e workers/[test-deferred-bindings]