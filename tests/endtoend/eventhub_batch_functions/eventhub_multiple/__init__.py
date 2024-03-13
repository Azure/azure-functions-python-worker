# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json


# This is an actual EventHub trigger which handles Eventhub events in batches.
# It serializes multiple event data into a json and store it into a blob.
def main(events):
    table_entries = []
    for event in events:
        json_entry = event.get_body()
        table_entry = json.loads(json_entry)
        table_entries.append(table_entry)

    table_json = json.dumps(table_entries)

    return table_json
