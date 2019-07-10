import azure.functions as azf


def main(req: azf.HttpRequest) -> bytes:
    return req.get_body()
