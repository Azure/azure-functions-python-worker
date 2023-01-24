import logging
import azure.functions as func
import external_lib

bp = func.Blueprint()


@bp.route(route="test_blueprint_logging")
def test_blueprint_logging(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('logging from blueprint')
    external_lib.ExternalLib()
    return func.HttpResponse('ok')
