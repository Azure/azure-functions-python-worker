# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.generic_trigger(arg_name="req", type="httpTrigger", route="sql_input/{productid}")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(arg_name="products", type="sql",
                           command_text="SELECT * FROM Products "
                           "WHERE ProductId = @ProductId",
                           command_type="Text",
                           parameters="@ProductId={productid}",
                           connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_input(req: func.HttpRequest, products: func.SqlRowList) -> func.HttpResponse:
    rows = list(map(lambda r: json.loads(r.to_json()), products))

    return func.HttpResponse(
        json.dumps(rows),
        status_code=200,
        mimetype="application/json"
    )


@app.generic_trigger(arg_name="req", type="httpTrigger", route="sql_input2/{productid}")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(arg_name="products", type="sql",
                           command_text="SELECT * FROM Products2 "
                           "WHERE ProductId = @ProductId",
                           command_type="Text",
                           parameters="@ProductId={productid}",
                           connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_input2(req: func.HttpRequest, products: func.SqlRowList) -> func.HttpResponse:
    rows = list(map(lambda r: json.loads(r.to_json()), products))

    return func.HttpResponse(
        json.dumps(rows),
        status_code=200,
        mimetype="application/json"
    )


@app.generic_trigger(arg_name="req", type="httpTrigger", route="sql_output")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_output_binding(arg_name="r", type="sql",
                            command_text="[dbo].[Products]",
                            connection_string_setting="AzureWebJobs"
                            "SqlConnectionString")
def sql_output(req: func.HttpRequest, r: func.Out[func.SqlRow]) \
        -> func.HttpResponse:
    body = json.loads(req.get_body())
    row = func.SqlRow.from_dict(body)
    r.set(row)

    return func.HttpResponse(
        body=req.get_body(),
        status_code=201,
        mimetype="application/json"
    )


@app.generic_trigger(arg_name="changes", type="sqlTrigger",
                     table_name="Products",
                     connection_string_setting="AzureWebJobsSqlConnectionString")
@app.generic_output_binding(arg_name="r", type="sql",
                            command_text="[dbo].[Products2]",
                            connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_trigger(changes, r: func.Out[func.SqlRow]) -> str:
    row = func.SqlRow.from_dict(json.loads(changes)[0]["Item"])
    r.set(row)
    return "OK"
