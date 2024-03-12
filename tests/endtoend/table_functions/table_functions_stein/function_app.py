# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import uuid
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="table_in_binding")
@app.route(route="table_in_binding/{id}")
@app.table_input(arg_name="testEntity",
                 connection="AzureWebJobsStorage",
                 table_name="BindingTestTable",
                 row_key='{id}',
                 partition_key="test")
def table_in_binding(req: func.HttpRequest, testEntity):
    return func.HttpResponse(status_code=200, body=testEntity)


@app.function_name(name="table_out_binding")
@app.route(route="table_out_binding", binding_arg_name="resp")
@app.table_output(arg_name="$return",
                  connection="AzureWebJobsStorage",
                  table_name="BindingTestTable")
def table_out_binding(req: func.HttpRequest, resp: func.Out[func.HttpResponse]):
    row_key_uuid = str(uuid.uuid4())
    table_dict = {'PartitionKey': 'test', 'RowKey': row_key_uuid}
    table_json = json.dumps(table_dict)
    resp.set(table_json)
    return table_json
