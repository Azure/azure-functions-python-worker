# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import json

import azure.functions as func


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="r2p2_v2_response", methods=["POST"])
def r2p2_v2_response(req: func.HttpRequest) -> func.HttpResponse:
    payload = {
        'body': req.get_body().decode('utf-8'),
        'header': req.headers.get('x-r2p2-input'),
        'method': req.method,
        'query': req.params.get('query'),
        'url': req.url,
    }
    response = func.HttpResponse(
        json.dumps(payload),
        status_code=203,
        headers={
            'content-type': 'application/json',
            'x-r2p2-runtime': 'v2-sync',
        },
    )
    response.headers.add(
        'Set-Cookie',
        'r2p2_v2_session=active; Path=/; HttpOnly; '
        'SameSite=Strict; Max-Age=120',
    )
    response.headers.add(
        'Set-Cookie',
        'r2p2_v2_theme=dark; Path=/; SameSite=Lax',
    )
    return response


@app.route(route="r2p2_v2_async", methods=["GET"])
async def r2p2_v2_async(req: func.HttpRequest) -> func.HttpResponse:
    await asyncio.sleep(0)
    return func.HttpResponse(
        'v2-async',
        headers={'x-r2p2-runtime': 'v2-async'},
    )
