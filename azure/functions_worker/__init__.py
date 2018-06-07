from . import aio_compat
from . import dispatcher


async def start_async(host, port, worker_id, request_id, grpc_max_msg_len):
    disp = await dispatcher.Dispatcher.connect(
        host, port, worker_id, request_id,
        connect_timeout=5.0, max_msg_len=grpc_max_msg_len)

    await disp.dispatch_forever()


def start(host: str, port: int, worker_id: str, request_id: str,
          grpc_max_msg_len: int):
    return aio_compat.run(start_async(
        host, port, worker_id, request_id, grpc_max_msg_len))
