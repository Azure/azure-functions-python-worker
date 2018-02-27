import io

import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.Out[str]) -> str:
    file.set(io.StringIO('filelike'))
    return 'OK'
