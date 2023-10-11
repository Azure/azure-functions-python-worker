# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import azure.functions as func


def main(changes, r: func.Out[func.SqlRow]) -> str:
    row = func.SqlRow.from_dict(json.loads(changes)[0]["Item"])
    r.set(row)
