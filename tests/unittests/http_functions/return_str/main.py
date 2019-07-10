import azure.functions


def main(req: azure.functions.HttpRequest, context) -> str:
    return 'Hello World!'
