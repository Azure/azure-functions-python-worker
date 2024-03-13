#!/usr/bin/env bash
python -m pytest -q -n auto --dist loadfile --reruns 4 --instafail --cov=./azure_functions_worker --cov-report xml --cov-branch --cov-append tests/endtoend/test_worker_process_count_functions.py tests/endtoend/test_threadpool_thread_count_functions.py
python -m pytest -q -n auto --dist loadfile --reruns 4 --instafail --cov=./azure_functions_worker --cov-report xml --cov-branch --cov-append --ignore=tests/endtoend/test_worker_process_count_functions.py --ignore=tests/endtoend/test_threadpool_thread_count_functions.py --ignore=tests/endtoend/test_deferred_bindings.py tests/endtoend