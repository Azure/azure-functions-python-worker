# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import hashlib
from azure_functions_worker.shared_memory_data_transfer import SharedMemoryMap
from azure_functions_worker.shared_memory_data_transfer \
    import SharedMemoryConstants as consts
from azure_functions_worker import protos
from azure_functions_worker import testutils


class TestMockBlobSharedMemoryFunctions(testutils.SharedMemoryTestCase,
                                        testutils.AsyncTestCase):
    def setUp(self):
        super().setUp()
        self.blob_funcs_dir = testutils.E2E_TESTS_FOLDER / 'blob_functions'

    async def test_binary_blob_read_function(self):
        func_name = 'get_blob_as_bytes_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            # Write binary content into shared memory
            mem_map_name = self.get_new_mem_map_name()
            content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
            content = self.get_random_bytes(content_size)
            content_md5 = hashlib.md5(content).hexdigest()
            mem_map_size = consts.CONTENT_HEADER_TOTAL_BYTES + content_size
            mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                        mem_map_size)
            shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                             mem_map)
            num_bytes_written = shared_mem_map.put_bytes(content)

            # Create a message to send to the worker containing info about the
            # shared memory region to read input from
            value = protos.RpcSharedMemory(
                name=mem_map_name,
                offset=0,
                count=num_bytes_written,
                type=protos.RpcDataType.bytes
            )

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, r = await host.invoke_function(
                func_name, [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))),
                    protos.ParameterBinding(
                        name='file',
                        rpc_shared_memory=value
                    )
                ])

            # Dispose the shared memory map since the function is done using it
            shared_mem_map.dispose()

            # Verify if the function executed successfully
            self.assertEqual(protos.StatusResult.Success,
                             r.response.result.status)

            json_response = json.loads(r.response.return_value.http.body.bytes)
            func_received_content_size = json_response['content_size']
            func_received_content_md5 = json_response['content_md5']

            # Check the function response to ensure that it read the complete
            # input that we provided and the md5 matches
            self.assertEqual(content_size, func_received_content_size)
            self.assertEqual(content_md5, func_received_content_md5)

    async def test_binary_blob_write_function(self):
        func_name = 'put_blob_as_bytes_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
            http_params = {'content_size': str(content_size)}

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, r = await host.invoke_function(
                func_name, [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET',
                                query=http_params))),
                ])

            # Verify if the function executed successfully
            self.assertEqual(protos.StatusResult.Success,
                             r.response.result.status)

            # The function responds back in the HTTP body with the md5 digest of
            # the output it created along with its size
            json_response = json.loads(r.response.return_value.http.body.bytes)
            func_created_content_size = json_response['content_size']
            func_created_content_md5 = json_response['content_md5']

            # Verify if the worker produced an output blob which was written
            # in shared memory
            output_data = r.response.output_data
            self.assertEqual(1, len(output_data))

            output_binding = output_data[0]
            binding_type = output_binding.WhichOneof('rpc_data')
            self.assertEqual('rpc_shared_memory', binding_type)

            # Get the information about the shared memory region in which the
            # worker wrote the function's output blob
            shmem = output_binding.rpc_shared_memory
            mem_map_name = shmem.name
            offset = shmem.offset
            count = shmem.count
            data_type = shmem.type

            # Verify if the shared memory region's information makes sense
            self.assertTrue(self.is_valid_uuid(mem_map_name))
            self.assertEqual(0, offset)
            self.assertEqual(func_created_content_size, count)
            self.assertEqual(protos.RpcDataType.bytes, data_type)

            # Read data from the shared memory region
            mem_map_size = consts.CONTENT_HEADER_TOTAL_BYTES + count
            mem_map = self.file_accessor.open_mem_map(mem_map_name,
                                                      mem_map_size)
            shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                             mem_map)
            read_content = shared_mem_map.get_bytes()

            # Dispose the shared memory map since we have read the function's
            # output now
            shared_mem_map.dispose()

            # Verify if we were able to read the correct output that the
            # function has produced
            read_content_md5 = hashlib.md5(read_content).hexdigest()
            self.assertEqual(func_created_content_md5, read_content_md5)
            self.assertEqual(len(read_content), func_created_content_size)

    async def test_str_blob_read_function(self):
        pass

    async def test_str_blob_write_function(self):
        pass

    def test_close_shared_memory_maps(self):
        pass
