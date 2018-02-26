import json

import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.InputStream) -> str:
    return json.dumps({
        'queue': json.loads(file.read().decode('utf-8'))
    })
