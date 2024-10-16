python -m venv .env
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip

python -m pip install .

$depsPath = Join-Path -Path $env:BUILD_SOURCESDIRECTORY -ChildPath "deps"
$protosPath = Join-Path -Path $depsPath -ChildPath "azure_functions_worker/protos"

python -m pip install . azure-functions --no-compile --target $depsPath.ToString()

python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

cd ..
Copy-Item -Path ".artifactignore" -Destination $depsPath.ToString()
Copy-Item -Path "azure_functions_worker/protos/*" -Destination $protosPath.ToString() -Recurse -Force
