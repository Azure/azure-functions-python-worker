# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionsApp()

@app.function_name(name="testApp1")
@app.route(route="hello")
def main(req) -> str:
    return __name__
