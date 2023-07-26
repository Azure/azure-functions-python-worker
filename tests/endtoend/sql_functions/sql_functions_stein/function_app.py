# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func
import json

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route()
@app.sql_input(arg_name="products",
                command_text="SELECT * FROM Products",
                command_type="Text",
                connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_input(req: func.HttpRequest, products: func.SqlRowList) -> func.HttpResponse:
    rows = list(map(lambda r: json.loads(r.to_json()), products))

    return func.HttpResponse(
        json.dumps(rows),
        status_code=200,
        mimetype="application/json"
    )

@app.route()
@app.sql_output(arg_name="product",
                command_text="[dbo].[Products]",
                connection_string_setting="AzureWebJobsSqlConnectionString")
def sql_output(req: func.HttpRequest, product: func.Out[func.SqlRow]) -> func.HttpResponse:
    body = json.loads(req.get_body())
    row = func.SqlRow.from_dict(body)
    product.set(row)

    return func.HttpResponse(
        body=req.get_body(),
        status_code=201,
        mimetype="application/json"
    )

