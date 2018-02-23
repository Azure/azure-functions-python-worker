%PYTHON% .ci\appveyor_setup_worker.py > worker_path
set /p PYAZURE_WORKER_DIR=<worker_path
%PYTHON% setup.py test
