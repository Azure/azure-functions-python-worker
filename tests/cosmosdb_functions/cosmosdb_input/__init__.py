import azure.functions as func


def main(req: func.HttpRequest, docs: func.DocumentList) -> str:
    return func.HttpResponse(docs[0].to_json(), mimetype='application/json')
