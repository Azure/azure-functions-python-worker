#!/usr/bin/env bash
# Step 1: Create venv
python${PYTHON_VERSION} -m venv .env
source .env/bin/activate
python -m pip install "setuptools<68" wheel

# Step 2: Install Bazel
# Try system package manager first, otherwise fallback to binary download
echo "=== Install Bazel ==="
if command -v apt-get &>/dev/null; then
  sudo apt-get update
  sudo apt-get install -y bazel
elif command -v brew &>/dev/null; then
  brew install bazelisk   # macOS: bazelisk auto-tracks correct Bazel version
else
  BAZEL_VERSION=6.5.0
  curl -LO "https://github.com/bazelbuild/bazel/releases/download/${BAZEL_VERSION}/bazel-${BAZEL_VERSION}-linux-x86_64"
  chmod +x "bazel-${BAZEL_VERSION}-linux-x86_64"
  sudo mv "bazel-${BAZEL_VERSION}-linux-x86_64" /usr/local/bin/bazel
fi

bazel --version

echo "=== Checking Python version being used ==="
python --version
pip --version

echo "=== Cloning grpc repo ==="
if [ ! -d "grpc" ]; then
    git clone --recursive https://github.com/grpc/grpc
else
    ( cd grpc && git fetch origin && git submodule update --init --recursive )
fi

cd grpc

echo "=== Building grpcio wheel with setup.py ==="
python setup.py bdist_wheel -d dist

echo "=== Checking built wheels ==="
ls -la dist

echo "=== Installing grpcio wheel into venv ==="
for whl in dist/grpcio-*.whl; do
    if [ -f "$whl" ]; then
        echo "Installing wheel: $whl"
        pip install "$whl"
    else
        echo "❌ No grpcio wheel found in dist/"
        exit 1
    fi
done

cd ..
echo "=== Installing your workers package ==="
cd workers
python -m pip install .

python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"

python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

cd ..
cp .artifactignore "$BUILD_SOURCESDIRECTORY/deps"

version_minor=$(echo $1 | cut -d '.' -f 2)
if [[ $version_minor -lt 13 ]]; then
    cp -r azure_functions_worker/protos "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker"
else
    cp -r proxy_worker/protos "$BUILD_SOURCESDIRECTORY/deps/proxy_worker"
fi