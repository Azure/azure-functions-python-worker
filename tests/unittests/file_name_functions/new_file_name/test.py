# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func

app = func.FunctionApp()


@app.route(route="return_str")
def return_str(req: func.HttpRequest) -> str:
    return "Hello World!"
