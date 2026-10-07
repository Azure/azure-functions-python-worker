# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import json

import azure.functions as func


async def main(req: func.HttpRequest) -> func.HttpResponse:
    await asyncio.sleep(0)
    payload = {
        'body': req.get_body().decode('utf-8'),
        'header': req.headers.get('x-r2p2-input'),
        'method': req.method,
        'query': req.params.get('query'),
        'url': req.url,
    }
    response = func.HttpResponse(
        json.dumps(payload),
        status_code=202,
        headers={
            'content-type': 'application/json',
            'x-r2p2-runtime': 'v1-async',
        },
    )
    response.headers.add(
        'Set-Cookie',
        'r2p2_v1_session=active; Path=/; HttpOnly; '
        'SameSite=Strict; Max-Age=120',
    )
    response.headers.add(
        'Set-Cookie',
        'r2p2_v1_theme=dark; Path=/; SameSite=Lax',
    )
    return response
