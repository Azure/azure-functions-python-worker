# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

from azure_functions_worker import protos
from azure_functions_worker import testutils


class TestTimerFunctions(testutils.AsyncTestCase):
    timer_funcs_dir = testutils.UNIT_TESTS_FOLDER / 'timer_functions'

    async def test_mock_timer__return_pastdue(self):
        async with testutils.start_mockhost(
                script_root=self.timer_funcs_dir) as host:

            func_id, r = await host.load_function('return_pastdue')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            async def call_and_check(due: bool):
                _, r = await host.invoke_function(
                    'return_pastdue', [
                        protos.ParameterBinding(
                            name='timer',
                            data=protos.TypedData(
                                json=json.dumps({
                                    'IsPastDue': due
                                })))
                    ])
                self.assertEqual(r.response.result.status,
                                 protos.StatusResult.Success)
                self.assertEqual(
                    list(r.response.output_data), [
                        protos.ParameterBinding(
                            name='pastdue',
                            data=protos.TypedData(string=str(due)))
                    ])

            await call_and_check(True)
            await call_and_check(False)

    async def test_mock_timer__user_event_loop(self):
        async with testutils.start_mockhost(
                script_root=self.timer_funcs_dir) as host:

            func_id, r = await host.load_function('user_event_loop_timer')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            async def call_and_check():
                _, r = await host.invoke_function(
                    'user_event_loop_timer', [
                        protos.ParameterBinding(
                            name='timer',
                            data=protos.TypedData(
                                json=json.dumps({
                                    'IsPastDue': False
                                })))
                    ])
                self.assertEqual(r.response.result.status,
                                 protos.StatusResult.Success)

            await call_and_check()
