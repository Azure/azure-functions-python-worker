import json
import logging
import typing

import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="get_queue_blob")
@app.route(route="get_queue_blob")
@app.read_blob(arg_name="file",
               connection="AzureWebJobsStorage",
               path="python-worker-tests/test-queue-blob.txt")
def get_queue_blob(req: func.HttpRequest, file: func.InputStream) -> str:
    return json.dumps({
        'queue': json.loads(file.read().decode('utf-8'))
    })


@app.function_name(name="get_queue_blob_message_return")
@app.route(route="get_queue_blob_message_return")
@app.read_blob(arg_name="file",
               connection="AzureWebJobsStorage",
               path="python-worker-tests/test-queue-blob-message-return.txt")
def get_queue_blob_message_return(req: func.HttpRequest,
                                  file: func.InputStream) -> str:
    return file.read().decode('utf-8')


@app.function_name(name="get_queue_blob_return")
@app.route(route="get_queue_blob_return")
@app.read_blob(arg_name="file",
               connection="AzureWebJobsStorage",
               path="python-worker-tests/test-queue-blob-return.txt")
def get_queue_blob_return(req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode('utf-8')


@app.function_name(name="get_queue_untyped_blob_return")
@app.route(route="get_queue_untyped_blob_return")
@app.read_blob(arg_name="file",
               connection="AzureWebJobsStorage",
               path="python-worker-tests/test-queue-untyped-blob-return.txt")
def get_queue_untyped_blob_return(req: func.HttpRequest,
                                  file: func.InputStream) -> str:
    return file.read().decode('utf-8')


@app.function_name(name="put_queue")
@app.route(route="put_queue")
@app.write_queue(arg_name="msg",
                 connection="AzureWebJobsStorage",
                 queue_name="testqueue")
def put_queue(req: func.HttpRequest, msg: func.Out[str]):
    msg.set(req.get_body())

    return 'OK'


@app.function_name(name="put_queue_message_return")
@app.route(route="put_queue_message_return", binding_arg_name="resp")
@app.write_queue(arg_name="$return",
                 connection="AzureWebJobsStorage",
                 queue_name="testqueue-message-return")
def main(req: func.HttpRequest, resp: func.Out[str]) -> bytes:
    return func.QueueMessage(body=req.get_body())


@app.function_name("put_queue_multiple_out")
@app.route(route="put_queue_multiple_out", binding_arg_name="resp")
@app.write_queue(arg_name="msg",
                 connection="AzureWebJobsStorage",
                 queue_name="testqueue-return-multiple-outparam")
def put_queue_multiple_out(req: func.HttpRequest,
                           resp: func.Out[func.HttpResponse],
                           msg: func.Out[func.QueueMessage]) -> None:
    data = req.get_body().decode()
    msg.set(func.QueueMessage(body=data))
    resp.set(func.HttpResponse(body='HTTP response: {}'.format(data)))


@app.function_name("put_queue_return")
@app.route(route="put_queue_return", binding_arg_name="resp")
@app.write_queue(arg_name="$return",
                 connection="AzureWebJobsStorage",
                 queue_name="testqueue-return")
def put_queue_return(req: func.HttpRequest, resp: func.Out[str]) -> bytes:
    return req.get_body()


@app.function_name(name="put_queue_multiple_return")
@app.route(route="put_queue_multiple_return")
@app.write_queue(arg_name="msgs",
                 connection="AzureWebJobsStorage",
                 queue_name="testqueue-return-multiple")
def put_queue_multiple_return(req: func.HttpRequest,
                              msgs: func.Out[typing.List[str]]):
    msgs.set(['one', 'two'])


@app.function_name(name="put_queue_untyped_return")
@app.route(route="put_queue_untyped_return", binding_arg_name="resp")
@app.write_queue(arg_name="$return",
                 connection="AzureWebJobsStorage",
                 queue_name="testqueue-untyped-return")
def put_queue_untyped_return(req: func.HttpRequest,
                             resp: func.Out[str]) -> bytes:
    return func.QueueMessage(body=req.get_body())


@app.function_name(name="queue_trigger")
@app.on_queue_change(arg_name="msg",
                     queue_name="testqueue",
                     connection="AzureWebJobsStorage")
@app.write_blob(arg_name="$return",
                connection="AzureWebJobsStorage",
                path="python-worker-tests/test-queue-blob.txt")
def queue_trigger(msg: func.QueueMessage) -> str:
    result = json.dumps({
        'id': msg.id,
        'body': msg.get_body().decode('utf-8'),
        'expiration_time': (msg.expiration_time.isoformat()
                            if msg.expiration_time else None),
        'insertion_time': (msg.insertion_time.isoformat()
                           if msg.insertion_time else None),
        'time_next_visible': (msg.time_next_visible.isoformat()
                              if msg.time_next_visible else None),
        'pop_receipt': msg.pop_receipt,
        'dequeue_count': msg.dequeue_count
    })

    return result


@app.function_name(name="queue_trigger_message_return")
@app.on_queue_change(arg_name="msg",
                     queue_name="testqueue-message-return",
                     connection="AzureWebJobsStorage")
@app.write_blob(arg_name="$return",
                connection="AzureWebJobsStorage",
                path="python-worker-tests/test-queue-blob-message-return.txt")
def queue_trigger_message_return(msg: func.QueueMessage) -> bytes:
    return msg.get_body()


@app.function_name(name="queue_trigger_return")
@app.on_queue_change(arg_name="msg",
                     queue_name="testqueue-return",
                     connection="AzureWebJobsStorage")
@app.write_blob(arg_name="$return",
                connection="AzureWebJobsStorage",
                path="python-worker-tests/test-queue-blob-return.txt")
def queue_trigger_return(msg: func.QueueMessage) -> bytes:
    return msg.get_body()


@app.function_name(name="queue_trigger_return_multiple")
@app.on_queue_change(arg_name="msg",
                     queue_name="testqueue-return-multiple",
                     connection="AzureWebJobsStorage")
def queue_trigger_return_multiple(msg: func.QueueMessage) -> None:
    logging.info('trigger on message: %s', msg.get_body().decode('utf-8'))


@app.function_name(name="queue_trigger_untyped")
@app.on_queue_change(arg_name="msg",
                     queue_name="testqueue-untyped-return",
                     connection="AzureWebJobsStorage")
@app.write_blob(arg_name="$return",
                connection="AzureWebJobsStorage",
                path="python-worker-tests/test-queue-untyped-blob-return.txt")
def queue_trigger_untyped(msg: str) -> str:
    return msg


@app.function_name(name="put_queue_return_multiple")
@app.route(route="put_queue_return_multiple", binding_arg_name="resp")
@app.write_queue(arg_name="msgs",
                 connection="AzureWebJobsStorage",
                 queue_name="testqueue-return-multiple")
def put_queue_return_multiple(req: func.HttpRequest,
                              resp: func.Out[str],
                              msgs: func.Out[typing.List[str]]):
    msgs.set(['one', 'two'])
