# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import uuid

import azure.functions as func


def main(req: func.HttpRequest, resp: func.Out[func.HttpResponse]):
    row_key_uuid = str(uuid.uuid4())
    table_dict = {'PartitionKey': 'test', 'RowKey': row_key_uuid}
    table_json = json.dumps(table_dict)
    resp.set(table_json)
    return table_json
