import azure.functions as azf


def main(req: azf.HttpRequest, foo: azf.Out[int]):
    foo.set(42)
    return 'wat'
