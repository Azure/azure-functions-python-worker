import queue

import grpc

try:
    from . import protos
except ImportError:
    raise RuntimeError(
        'cannot start worker; generate pb2/grpc files in azure/worker/protos')

from . import dispatcher


def start(host: str, port: int, worker_id: str, request_id: str):
    channel = grpc.insecure_channel(f'{host}:{port}')
    stub = protos.FunctionRpcStub(channel)

    def gen(q):
        while True:
            yield q.get()

    response_queue = queue.Queue()
    response_queue.put(protos.StreamingMessage(
        request_id=request_id,
        start_stream=protos.StartStream(
            worker_id=worker_id)))

    resp_stream = stub.EventStream(gen(response_queue))
    disp = dispatcher.Dispatcher(response_queue, request_id)

    for resp in resp_stream:
        disp.dispatch(resp)
