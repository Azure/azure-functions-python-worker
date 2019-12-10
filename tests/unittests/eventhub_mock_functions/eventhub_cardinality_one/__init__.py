import azure.functions as func


def main(event: func.EventHubEvent) -> str:
    return 'OK'
