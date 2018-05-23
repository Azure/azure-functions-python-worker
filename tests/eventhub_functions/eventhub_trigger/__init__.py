import azure.functions as func


def main(event: func.EventHubEvent) -> bytes:
    return event.get_body()
