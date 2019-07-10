import azure.functions as func


def main(req: func.HttpRequest, file: func.InputStream) -> str:
    return func.HttpResponse(
        file.read().decode('utf-8'), mimetype='application/json')
