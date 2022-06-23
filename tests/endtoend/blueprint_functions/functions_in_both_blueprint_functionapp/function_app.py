import azure.functions as func

from azure_functions_worker import logging
from blueprint import bp

app = func.FunctionApp()

app.register_blueprint(bp)


@app.route(route="return_http")
def return_http(req: func.HttpRequest):
    return func.HttpResponse('<h1>Hello World™</h1>',
                             mimetype='text/html')
