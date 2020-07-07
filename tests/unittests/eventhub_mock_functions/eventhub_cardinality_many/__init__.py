# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import List
import azure.functions as func


# This is testing the function load feature for the multiple events annotation
def main(events: List[func.EventHubEvent]) -> str:
    return 'OK_MANY'
