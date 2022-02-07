# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# Import a module from thirdparty package azure-eventhub
import azure.eventhub as eh
import azure.functions as func

app = func.FunctionsApp()

@app.function_name(name="testApp1")
@app.route(route="/")
def main(req) -> str:
    return f'eh = {eh.__name__}'
