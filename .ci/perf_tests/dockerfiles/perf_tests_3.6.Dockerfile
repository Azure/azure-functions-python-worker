FROM mcr.microsoft.com/azure-functions/python:3.0.14492-python3.6

# Mounting local machines azure-functions-python-worker and azure-functions-python-library onto it
RUN rm -rf /azure-functions-host/workers/python/3.6/LINUX/X64/azure_functions_worker

# Use the following command to run the docker image with customizible worker and library
VOLUME ["/azure-functions-host/workers/python/3.6/LINUX/X64/azure_functions_worker"]

ENV FUNCTIONS_WORKER_RUNTIME_VERSION=3.6 \
    AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    FUNCTIONS_WORKER_PROCESS_COUNT=1 \
    AZURE_FUNCTIONS_ENVIRONMENT=Development

RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 379CE192D401AB61 && \
    echo "deb https://dl.bintray.com/loadimpact/deb stable main" | tee -a /etc/apt/sources.list  && \
    apt-get update && \
    apt-get install -y git k6 && \
    cd /home && \
    git clone https://github.com/vrdmr/AzFunctionsPythonPerformance.git && \
    mkdir -p /home/site/wwwroot/ && \
    cp -r AzFunctionsPythonPerformance/* /home/site/wwwroot/ && \
    pip install -r /home/site/wwwroot/requirements.txt

CMD [ "/azure-functions-host/Microsoft.Azure.WebJobs.Script.WebHost" ]
