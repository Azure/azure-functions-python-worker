# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="sql_input/{productid}")
@app.sql_input(arg_name="products",
               command_text="SELECT * FROM Products WHERE ProductId = @ProductId",
               command_type="Text",
               parameters="@ProductId={productid}",
               connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_input(req: func.HttpRequest, products: func.SqlRowList) \
        -> func.HttpResponse:
    rows = list(map(lambda r: json.loads(r.to_json()), products))

    return func.HttpResponse(
        json.dumps(rows),
        status_code=200,
        mimetype="application/json"
    )


@app.route(route="sql_input2/{productid}")
@app.sql_input(arg_name="products",
               command_text="SELECT * FROM Products2 WHERE ProductId = @ProductId",
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


@app.route(route="sql_output")
@app.sql_output(arg_name="r",
                command_text="[dbo].[Products]",
                connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_output(req: func.HttpRequest, r: func.Out[func.SqlRow]) -> func.HttpResponse:
    body = json.loads(req.get_body())
    row = func.SqlRow.from_dict(body)
    r.set(row)

    return func.HttpResponse(
        body=req.get_body(),
        status_code=201,
        mimetype="application/json"
    )


@app.sql_trigger(arg_name="changes",
                 table_name="Products",
                 connection_string_setting="AzureWebJobsSqlConnectionString")
@app.sql_output(arg_name="r",
                command_text="[dbo].[Products2]",
                connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_trigger(changes, r: func.Out[func.SqlRow]) -> str:
    row = func.SqlRow.from_dict(json.loads(changes)[0]["Item"])
    r.set(row)
    return "OK"
