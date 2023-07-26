# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func
import json

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.generic_trigger(arg_name="req", type="httpTrigger")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(arg_name="products", type="sql",
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

@app.generic_trigger(arg_name="req", type="httpTrigger")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_output_binding(arg_name="product", type="sql",
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
