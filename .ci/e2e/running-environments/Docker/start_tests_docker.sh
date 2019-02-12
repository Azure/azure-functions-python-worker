#!/usr/bin/env bash

# This needs to happen after the docker container is built. This is because the setup uses Docker deamon
# And the /var/run/docker.sock needs to be mounted for the setup script to use Docker.
# This is done when the Docker container is run.
/azure-functions-python-worker/.ci/e2e/publish_tests/test_runners/setup_test_environment.sh

/azure-functions-python-worker/.ci/e2e/publish_tests/test_runners/run_all_serial.sh