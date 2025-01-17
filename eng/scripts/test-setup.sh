#!/bin/bash

cd tests
python -m invoke -c test_setup build-protos
python -m invoke -c test_setup webhost --branch-name=satvu/test-snake-case
python -m invoke -c test_setup extensions