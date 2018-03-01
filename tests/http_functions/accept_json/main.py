import json

import azure.functions


def main(req: azure.functions.HttpRequest):
    return json.dumps({
        'method': req.method,
        'url': req.url,
        'headers': dict(req.headers),
        'params': dict(req.params),
        'get_body': req.get_body().decode(),
        'get_json': req.get_json()
    })
