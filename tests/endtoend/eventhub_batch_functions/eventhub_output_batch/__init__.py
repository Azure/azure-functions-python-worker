import azure.functions as func


def main(req: func.HttpRequest) -> str:
    events = req.get_body().decode('utf-8')
    return events
