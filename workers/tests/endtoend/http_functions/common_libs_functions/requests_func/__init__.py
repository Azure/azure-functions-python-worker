# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
from unittest.mock import patch

import azure.functions as func
import requests


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Exercise Requests without depending on external network access or TLS.
    response = requests.Response()
    response.status_code = 200
    response._content = b'requests smoke test'
    with patch('requests.adapters.HTTPAdapter.send',
               return_value=response) as send:
        result = requests.get('https://requests-smoke-test.invalid/', timeout=5)
    send.assert_called_once()
    prepared_request = send.call_args.args[0]
    assert prepared_request.method == 'GET'
    assert prepared_request.url == 'https://requests-smoke-test.invalid/'
    res = "req status code: {}".format(result.status_code)

    return func.HttpResponse(res)
