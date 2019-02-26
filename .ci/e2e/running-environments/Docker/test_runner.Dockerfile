# When running, make sure to mount Docker sock and use the python-worker directory as the base dir
# Example-
# docker build -f .ci\e2e\running-environments\Docker\test_runner.Dockerfile -t my-test-image <path-to-python-worker>
# docker run -v /var/run/docker.sock:/var/run/docker.sock my-test-image

FROM mcr.microsoft.com/azure-functions/python:2.0

COPY . /azure-functions-python-worker

RUN apt-get update && \
    apt-get install azure-functions-core-tools jq git unzip -y

# Install docker amd azure CLI
RUN curl -sSL https://get.docker.com/ | sh && \
    apt-get update && \
    apt-get install apt-transport-https lsb-release software-properties-common dirmngr -y && \
    AZ_REPO=$(lsb_release -cs) && \
    echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" | tee /etc/apt/sources.list.d/azure-cli.list && \
    apt-key --keyring /etc/apt/trusted.gpg.d/Microsoft.gpg adv --keyserver packages.microsoft.com --recv-keys BC528686B50D79E339D3721CEB3E94ADBE1229CF && \
    apt-get update && \
    apt-get install azure-cli -y

# RUN bash /azure-functions-python-worker/.ci/e2e/publish_tests/test_runners/setup_test_environment.sh

ENV ENVIRONMENT=DOCKER
ENV EXIT_ON_FAIL=FALSE

CMD [ "bash", "/azure-functions-python-worker/.ci/e2e/running-environments/Docker/start_tests_docker.sh" ]