import azure.functions as azf


def main(req: azf.HttpRequest, msg: azf.Out[str]):
    msg.set(req.get_body().decode('utf-8'))

    return 'OK'
