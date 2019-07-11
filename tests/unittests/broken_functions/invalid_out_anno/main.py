import azure.functions as azf


def main(req, ret: azf.Out[azf.HttpRequest]):
    return 'trust me, it is OK!'
