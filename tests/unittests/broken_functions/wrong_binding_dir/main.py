import azure.functions as azf


def main(req, foo: azf.Out[str]):
    return 'trust me, it is OK!'
