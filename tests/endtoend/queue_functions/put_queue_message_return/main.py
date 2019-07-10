import azure.functions as azf


def main(req: azf.HttpRequest) -> bytes:
    return azf.QueueMessage(body=req.get_body())
