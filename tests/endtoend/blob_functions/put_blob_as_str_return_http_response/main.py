# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import string
import random
import json
import hashlib
import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.Out[str]) -> azf.HttpResponse:
    num_chars = int(req.params['num_chars'])

    content = ''.join(random.choices(string.ascii_uppercase + string.digits,
                                     k=num_chars))
    content_bytes = content.encode('utf-8')
    content_size = len(content_bytes)
    content_md5 = hashlib.md5(content_bytes).hexdigest()

    file.set(content)

    response_dict = {
        'num_chars': num_chars,
        'content_size': content_size,
        'content_md5': content_md5
    }

    response_body = json.dumps(response_dict, indent=2)

    return azf.HttpResponse(
        body=response_body,
        mimetype="application/json",
        status_code=200
    )
