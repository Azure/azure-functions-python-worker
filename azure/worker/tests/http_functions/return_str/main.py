import azure.functions


def main(req: azure.functions.HttpRequest, context):
    return 'Hello World!'
