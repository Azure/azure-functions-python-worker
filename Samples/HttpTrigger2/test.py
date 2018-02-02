from main import main
import logging

class HttpRequestMessage: 
    method = ''
    url = ''
    headers = {}
    data = {}
    params = {}
    body = b''


class HttpResponseMessage: 
    headers = {}
    status_code = 200
    content = ''
    url = ''


class Context: 
    logger = logging.Logger('execution context')
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def execute():
    request = HttpRequestMessage()
    response = HttpResponseMessage()
    context = Context()
    
    request.data['name'] = 'Azure'

    context.logger.info('Function started.')
    main(context,request,response) 
    context.logger.info('Function completed.')

    print(f'Function Output : {response.content}')


execute()