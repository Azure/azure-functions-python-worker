import logging
import time
from datetime import datetime

import azure.functions as func

bp = func.Blueprint()


@bp.route(route="default_template")
def default_template(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(
            f"Hello, {name}. This HTTP triggered function "
            f"executed successfully.")
    else:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. "
            "Pass a name in the query string or in the request body for a"
            " personalized response.",
            status_code=200
        )


@bp.route(route="http_func")
def http_func(req: func.HttpRequest) -> func.HttpResponse:
    time.sleep(1)

    current_time = datetime.now().strftime("%H:%M:%S")
    return func.HttpResponse(f"{current_time}")