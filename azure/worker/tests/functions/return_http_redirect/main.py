import azure.functions as azf


def main(req: azf.HttpRequest):
    return azf.HttpResponse(
        status_code=302,
        headers={'location': 'return_http'})
