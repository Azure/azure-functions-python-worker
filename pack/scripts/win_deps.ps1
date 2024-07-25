python -m venv .env
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip

python -m pip install .

$depsPath = Join-Path -Path $env:BUILD_SOURCESDIRECTORY -ChildPath "deps"

python -m pip install . azure-functions --no-compile --target $depsPath.ToString()

cd tests
python -m invoke -c test_setup build-protos
python -m invoke -c test_setup build-protos --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"

Copy-Item -Path ".artifactignore" -Destination $depsPath.ToString()
