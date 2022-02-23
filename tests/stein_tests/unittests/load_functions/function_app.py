# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionsApp(auth_level=func.AuthLevel.ANONYMOUS)
app1 = func.FunctionsApp(auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="simple")
@app.route(route="hello")
def main(req) -> str:
    return __name__
