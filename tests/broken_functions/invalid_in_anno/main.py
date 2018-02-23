import azure.functions as azf


def main(req: azf.HttpResponse):  # should be azf.HttpRequest
    return 'trust me, it is OK!'
