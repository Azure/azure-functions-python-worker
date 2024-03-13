# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import uuid
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="table_in_binding")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="table_in_binding/{id}")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="BindingTestTable",
    row_key="{id}",
    partition_key="test")
def table_in_binding(req: func.HttpRequest, testEntity):
    headers_dict = json.loads(testEntity)
    return func.HttpResponse(status_code=200, headers=headers_dict)


@app.function_name(name="table_out_binding")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="table_out_binding")
@app.generic_output_binding(arg_name="resp", type="http")
@app.generic_output_binding(
    arg_name="$return",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="BindingTestTable")
def table_out_binding(req: func.HttpRequest, resp: func.Out[func.HttpResponse]):
    row_key_uuid = str(uuid.uuid4())
    table_dict = {'PartitionKey': 'test', 'RowKey': row_key_uuid}
    table_json = json.dumps(table_dict)
    http_resp = func.HttpResponse(status_code=200, headers=table_dict)
    resp.set(http_resp)
    return table_json
