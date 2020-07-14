# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


# An HttpTrigger to generating EventHub event from EventHub Output Binding
def main(req: func.HttpRequest) -> str:
    events = req.get_body().decode('utf-8')
    return events
