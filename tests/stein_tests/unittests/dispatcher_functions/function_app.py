import json
import azure.functions as func

app = func.FunctionsApp(auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="dispatcher_test")
@app.route(route="dispatcher_test")
def dispatcher_test(req: func.HttpRequest,
                    context: func.Context) -> func.HttpResponse:
    result = {
        'function_directory': context.function_directory,
        'function_name': context.function_name
    }
    return func.HttpResponse(body=json.dumps(result),
                             mimetype='application/json')
