from typing import List
import azure.functions as func


# This is testing the function load feature for the multiple events annotation
# The event shouldn't be List[str]
def main(events: List[str]) -> str:
    return 'BAD'
