import azure.functions as azf


def main(req: azf.HttpRequest, file: bytes) -> str:
    assert isinstance(file, bytes)
    return file.decode('utf-8')
