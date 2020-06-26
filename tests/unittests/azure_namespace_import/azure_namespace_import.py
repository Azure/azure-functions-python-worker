# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
import shutil
import asyncio

from azure_functions_worker import protos
from azure_functions_worker import testutils


async def vertify_nested_namespace_import():
    test_env = {}
    request = protos.FunctionEnvironmentReloadRequest(
        environment_variables=test_env)

    request_msg = protos.StreamingMessage(
        request_id='0',
        function_environment_reload_request=request)

    disp = testutils.create_dummy_dispatcher()

    # Mock intepreter starts in placeholder mode
    import azure.module_a as mod_a  # noqa: F401

    # Mock function specialization, load customer's libraries and functionapps
    ns_root = os.path.join(
        testutils.UNIT_TESTS_ROOT,
        'azure_namespace_import',
        'namespace_location_b')
    test_path = os.path.join(ns_root, 'azure', 'namespace_b', 'module_b')
    test_mod_path = os.path.join(test_path, 'test_module.py')

    os.makedirs(test_path)
    with open(test_mod_path, 'w') as f:
        f.write('MESSAGE = "module_b is imported"')

    try:
        # Mock a customer uses test_module
        if sys.argv[1].lower() == 'true':
            await disp._handle__function_environment_reload_request(
                request_msg)
        from azure.namespace_b.module_b import test_module
        print(test_module.MESSAGE)
    except ModuleNotFoundError:
        print('module_b fails to import')
    finally:
        # Cleanup
        shutil.rmtree(ns_root)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(vertify_nested_namespace_import())
    loop.close()
