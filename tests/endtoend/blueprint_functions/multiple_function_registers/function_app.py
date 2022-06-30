import azure.functions as func

app = func.FunctionApp()


@app.route(route="return_http")
def return_http(req: func.HttpRequest):
    return func.HttpResponse('<h1>Hello World™</h1>',
                             mimetype='text/html')


asgi_app = func.AsgiFunctionApp()
