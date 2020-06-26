# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


def main(req: func.HttpRequest, resp: func.Out[func.HttpResponse],
         msg: func.Out[func.QueueMessage]) -> None:
    data = req.get_body().decode()
    msg.set(func.QueueMessage(body=data))
    resp.set(func.HttpResponse(body='HTTP response: {}'.format(data)))
