import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_body()
    body_len = str(len(body))

    headers = {'body-len': body_len}
    return func.HttpResponse("OK", status_code=200, headers=headers)
