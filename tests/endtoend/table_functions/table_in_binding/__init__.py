import json

import azure.functions as func


def main(req: func.HttpRequest, testEntity):
    headers_dict = json.loads(testEntity)
    return func.HttpResponse(status_code=200, headers=headers_dict)
