#!/bin/bash

cd tests
python -m invoke -c test_setup build-protos
python -m invoke -c test_setup webhost --branch-name=gaaguiar/test_py_worker
python -m invoke -c test_setup extensions