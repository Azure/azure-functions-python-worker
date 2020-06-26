# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import azure.functions


def main(req: azure.functions.HttpRequest) -> str:
    return json.dumps(dict(req.route_params))
