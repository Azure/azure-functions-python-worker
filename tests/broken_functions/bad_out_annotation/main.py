import azure.functions as azf


def main(req, foo: azf.Out):
    return 'trust me, it is OK!'
