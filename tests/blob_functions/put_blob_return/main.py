import azure.functions as azf


def main(req: azf.HttpRequest) -> str:
    return 'FROM RETURN'
