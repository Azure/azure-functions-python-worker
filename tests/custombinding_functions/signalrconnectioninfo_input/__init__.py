import logging

import azure.functions as func


def main(req: func.HttpRequest, connectionInfo: str) -> func.HttpResponse:
    return func.HttpResponse(connectionInfo)
