from . import aio_compat
from . import dispatcher


async def start_async(host, port, worker_id, request_id):
    disp = await dispatcher.Dispatcher.connect(
        host, port, worker_id, request_id,
        connect_timeout=5.0)

    await disp.dispatch_forever()


def start(host: str, port: int, worker_id: str, request_id: str):
    return aio_compat.run(start_async(host, port, worker_id, request_id))
