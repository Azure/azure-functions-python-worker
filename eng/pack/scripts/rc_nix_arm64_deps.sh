#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip

version_minor=$(echo $1 | cut -d '.' -f 2)
mkdir -p $BUILD_SOURCESDIRECTORY/deps

# Targeting: grpcio manylinux_2_17_aarch64.whl build

# Starts a docker container using the linux/arm64 platform
# Inside the container, we perform the same steps as our typical builds
# However, since we're running them on the linux/arm64 platform, we ensure
# that we pull in the correct grpc, etc. builds
docker run --privileged --rm tonistiigi/binfmt --install all
docker run --name my-arm64-container --rm -i --platform linux/arm64 \
      -v ./:/src \
      -w /src \
      python:3.14.0rc3-alpine3.22 sh -c "
        ls -la /src  # debug: see what files exist
        apk update && apk add --no-cache git curl build-base && \
        pip install --upgrade pip setuptools wheel cython&& \
        git clone --recursive https://github.com/grpc/grpc && \
        cd grpc && \
        git submodule update --init --recursive && \
        export GRPC_PYTHON_BUILD_WITH_CYTHON=1 && \
        pip wheel . -w dist && \
        ls -la dist && \
        GRPC_WHEEL=\$(ls dist/grpcio-*.whl | head -n 1) && \
        pip install \"\$GRPC_WHEEL\" && \ \
        cd .. && \
        cd workers && \
        pip install . && \
        pip install grpcio-tools==1.70.0 && \
        pip install \"\$GRPC_WHEEL\" --target /src && \
        pip install --upgrade pip setuptools wheel cython --target /src && \
        pip install . --target /src && \
        pip install grpcio-tools==1.70.0 --target /src && \
        pip install invoke && \
        cd tests && \
        python -m invoke -c test_setup build-protos && \
        ls -la /src
      "

cd workers

# This copies over the build files from the docker container to the local pipeline
docker cp my-arm64-container:/src/. $BUILD_SOURCESDIRECTORY/all/
docker rm my-arm64-container

# From the container, we have many unnecessary files. Here, we only
# copy over the relevant files to the 'deps/' directory.
copy_list=(
  "azure"
  "azure_functions_worker"
  "azure_functions_runtime"
  "azure_functions_runtime_v1"
  "azurefunctions"
  "dateutil"
  "google"
  "grpc"
  "markupsafe"
  "proxy_worker"
  "six.py"
  "werkzeug"
)

for dir in "${copy_list[@]}"; do
      src="$BUILD_SOURCESDIRECTORY/all/$dir"
      dest="$BUILD_SOURCESDIRECTORY/deps"

      if [ -e $src ]; then
        echo "Copying $dir..."
        cp -r $src $dest
      else
        echo "Directory $dir not found in deps — skipping"
      fi
    done

cp .artifactignore "$BUILD_SOURCESDIRECTORY/deps"

version_minor=$(echo $1 | cut -d '.' -f 2)
if [[ $version_minor -lt 13 ]]; then
    cp -r azure_functions_worker/protos "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker"
else
    cp -r proxy_worker/protos "$BUILD_SOURCESDIRECTORY/deps/proxy_worker"
fi

echo "Listing contents of deps directory:"
ls -la $BUILD_SOURCESDIRECTORY/deps