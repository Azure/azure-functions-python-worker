import azure.functions as azf


def main(req: azf.HttpRequest, file: str) -> str:
    assert isinstance(file, str)
    return file
