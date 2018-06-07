import azure.functions as azf


def main(req: azf.HttpRequest):
    location = 'return_http?code={}'.format(req.params['code'])
    return azf.HttpResponse(
        status_code=302,
        headers={'location': location})
