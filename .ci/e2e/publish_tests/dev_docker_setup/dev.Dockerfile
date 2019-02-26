ARG BASE_IMAGE=mcr.microsoft.com/azure-functions/python:2.0
ARG PYTHON_WORKER_LOCATION=.
FROM ${BASE_IMAGE}

COPY ${PYTHON_WORKER_LOCATION} /python-worker-dev/

RUN pip install -e /python-worker-dev/ && \
    rm -rf /azure-functions-host/workers/python/worker.py && \
    mv /python-worker-dev/python/worker.py /azure-functions-host/workers/python/
