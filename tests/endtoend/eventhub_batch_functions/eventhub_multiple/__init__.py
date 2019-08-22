import json


def main(events):
    table_entries = []
    for event in events:
        json_entry = event.get_body()
        table_entry = json.loads(json_entry)
        table_entries.append(table_entry)

    table_json = json.dumps(table_entries)

    return table_json
