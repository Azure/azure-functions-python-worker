# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import uuid

import azure.functions as func


def main(req: func.HttpRequest, resp: func.Out[func.HttpResponse]):
    row_key_uuid = str(uuid.uuid4())
    table_dict = {'PartitionKey': 'test', 'RowKey': row_key_uuid}
    table_json = json.dumps(table_dict)
    http_resp = func.HttpResponse(status_code=200, headers=table_dict)
    resp.set(http_resp)
    return table_json
