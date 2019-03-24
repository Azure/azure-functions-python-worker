import json

import azure.functions as func


def main(event: func.EventHubEvent) -> str:
    return json.dumps(event.iothub_metadata)
