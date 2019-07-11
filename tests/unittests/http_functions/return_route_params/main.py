import json
import azure.functions


def main(req: azure.functions.HttpRequest) -> str:
    return json.dumps(dict(req.route_params))
