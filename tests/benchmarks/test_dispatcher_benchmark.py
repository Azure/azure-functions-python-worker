# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from azure_functions_worker import protos, testutils


def test_invoke_function(aio_benchmark):

    async def invoke_function():
        async with testutils.start_mockhost() as host:
            await host.load_function('return_str')

            await host.invoke_function(
                    'return_str', [
                        protos.ParameterBinding(
                            name='req',
                            data=protos.TypedData(
                                http=protos.RpcHttp(
                                    method='GET')))
                    ])
    
    aio_benchmark(invoke_function)
