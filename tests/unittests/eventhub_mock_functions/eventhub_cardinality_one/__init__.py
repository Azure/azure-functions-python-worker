# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


# This is testing the function load feature for the single event annotation
def main(event: func.EventHubEvent) -> str:
    return 'OK_ONE'
