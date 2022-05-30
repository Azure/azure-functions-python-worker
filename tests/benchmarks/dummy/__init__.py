import azure.functions as func

def foo():
    pass

app = func.FunctionApp()

@app.route(route="func1")
def func1(req: func.HttpRequest) -> func.HttpResponse:
    ...


@app.route(route="func1")
def func2(req: func.HttpRequest, arg1) -> func.HttpResponse:
    ...


@app.route(route="func1")
def func3(req: func.HttpRequest, arg1, arg2) -> func.HttpResponse:
    ...


@app.route(route="func1")
def func4(req: func.HttpRequest, arg1, arg2, arg3) -> func.HttpResponse:
    ...

