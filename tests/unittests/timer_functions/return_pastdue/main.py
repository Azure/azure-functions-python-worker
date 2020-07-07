# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(timer: azf.TimerRequest, pastdue: azf.Out[str]):
    pastdue.set(str(timer.past_due))
