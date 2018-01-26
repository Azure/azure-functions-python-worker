def main(context, req, res):

    context.logger.info('Python HTTP trigger function processed a request.')

    if req.params and req.params['name']:
        res.content = 'Hello ' + req.params['name']

    elif req.data and req.data['name']:
        res.content = 'Hello ' + req.data['name']

    else:
        res.content = 'Please pass a name on the query string or in the request body.'
        res.status_code = 400
