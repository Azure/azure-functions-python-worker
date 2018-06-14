import json

import azure.functions


def main(req: azure.functions.HttpRequest):
    params = dict(req.params)
    params.pop('code', None)
    return json.dumps({
        'method': req.method,
        'url': req.url,
        'headers': dict(req.headers),
        'params': params,
        'get_body': req.get_body().decode(),
    })
