from azurefunctions.extensions.http.fastapi import Request, Response
import azure.functions as func


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="http_trigger")
def http_trigger(req: Request) -> Response:
    return Response("ok")
