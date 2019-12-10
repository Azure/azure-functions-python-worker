from typing import List
import azure.functions as func


def main(events: List[func.EventHubEvent]) -> str:
    return 'OK'
