import azure.functions as func


def main(req: func.HttpRequest, testEntities):
    return func.HttpResponse(status_code=200, body=testEntities)
