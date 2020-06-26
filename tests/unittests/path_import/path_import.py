# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
import shutil
import asyncio

from azure_functions_worker import protos
from azure_functions_worker import testutils


async def verify_path_imports():
    test_env = {}
    request = protos.FunctionEnvironmentReloadRequest(
        environment_variables=test_env)

    request_msg = protos.StreamingMessage(
        request_id='0',
        function_environment_reload_request=request)

    disp = testutils.create_dummy_dispatcher()

    test_path = 'test_module_dir'
    test_mod_path = os.path.join(test_path, 'test_module.py')

    os.mkdir(test_path)
    with open(test_mod_path, 'w') as f:
        f.write('CONSTANT = "This module was imported!"')

    if (sys.argv[1] == 'success'):
        await disp._handle__function_environment_reload_request(request_msg)

    try:
        import test_module
        print(test_module.CONSTANT)
    finally:
        # Cleanup
        shutil.rmtree(test_path)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(verify_path_imports())
    loop.close()
