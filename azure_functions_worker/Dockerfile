# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.11-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

# WORKDIR "D:\Repos\azure-functions-python-worker"
# VOLUME [ "/azure-functions-host/workers/python/3.11/LINUX/X64" ]
ADD . /azure-functions-host/workers/python/3.11/LINUX/X64

COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY . /home/site/wwwroot