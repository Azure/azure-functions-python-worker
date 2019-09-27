python -m venv .env
.env\scripts\activate
python -m pip install .

$depsPath = Join-Path -Path $env:BUILD_SOURCESDIRECTORY -ChildPath "deps"

python -m pip install . azure-functions --no-compile --target $depsPath.ToString()