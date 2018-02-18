import functools
import inspect
import unittest

from azure.worker import aio_compat
from azure.worker import protos
from azure.worker import testutils


class MockHostTestsMeta(type(unittest.TestCase)):

    def __new__(mcls, name, bases, ns):
        for attrname, attr in ns.items():
            if (attrname.startswith('test_') and
                    inspect.iscoroutinefunction(attr)):
                ns[attrname] = mcls._sync_wrap(attr)

        return super().__new__(mcls, name, bases, ns)

    @staticmethod
    def _sync_wrap(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return aio_compat.run(func(*args, **kwargs))
        return wrapper


class TestMockHost(unittest.TestCase, metaclass=MockHostTestsMeta):

    async def test_call_sync_function_check_logs(self):
        async with testutils.start_mockhost() as host:
            await host.load_function('sync_logging')

            invoke_id, r = await host.invoke_function(
                'sync_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET')))
                ])

            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            self.assertEqual(len(r.logs), 1)

            log = r.logs[0]
            self.assertEqual(log.invocation_id, invoke_id)
            self.assertEqual(log.message, 'a gracefully handled error')

            self.assertEqual(r.response.return_value.string, 'OK-sync')

    async def test_call_async_function_check_logs(self):
        async with testutils.start_mockhost() as host:
            await host.load_function('async_logging')

            invoke_id, r = await host.invoke_function(
                'async_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET')))
                ])

            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            self.assertEqual(len(r.logs), 2)

            self.assertEqual(r.logs[0].invocation_id, invoke_id)
            self.assertEqual(r.logs[0].message, 'one error')

            self.assertEqual(r.logs[1].invocation_id, invoke_id)
            self.assertEqual(r.logs[1].message, 'and another error')

            self.assertEqual(r.response.return_value.string, 'OK-async')
