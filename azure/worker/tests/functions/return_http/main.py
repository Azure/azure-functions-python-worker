import azure.functions as azf


def main(req: azf.HttpRequest):
    return azf.HttpResponse('<h1>Hello World™</h1>',
                            mimetype='text/html')
