# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import hashlib
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryMap
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryConstants as consts
from azure_functions_worker import protos
from azure_functions_worker import testutils


class TestMockBlobSharedMemoryFunctions(testutils.SharedMemoryTestCase,
                                        testutils.AsyncTestCase):
    """
    Test the use of shared memory to transfer input and output data to and from
    the host/worker.
    """
    def setUp(self):
        super().setUp()
        self.blob_funcs_dir = testutils.E2E_TESTS_FOLDER / 'blob_functions'

    async def test_binary_blob_read_as_bytes_function(self):
        """
        Read a blob with binary input that was transferred between the host and
        worker over shared memory.
        The function's input data type will be bytes.
        """
        func_name = 'get_blob_as_bytes_return_http_response'
        await self._test_binary_blob_read_function(func_name)

    async def test_binary_blob_read_as_stream_function(self):
        """
        Read a blob with binary input that was transferred between the host and
        worker over shared memory.
        The function's input data type will be InputStream.
        """
        func_name = 'get_blob_as_bytes_stream_return_http_response'
        await self._test_binary_blob_read_function(func_name)

    async def test_binary_blob_write_function(self):
        """
        Write a blob with binary output that was transferred between the worker
        and host over shared memory.
        """
        func_name = 'put_blob_as_bytes_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
            http_params = {'content_size': str(content_size)}

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, response_msg = await host.invoke_function(
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
                             response_msg.response.result.status)

            # The function responds back in the HTTP body with the md5 digest of
            # the output it created along with its size
            response_bytes = response_msg.response.return_value.http.body.bytes
            json_response = json.loads(response_bytes)
            func_created_content_size = json_response['content_size']
            func_created_content_md5 = json_response['content_md5']

            # Verify if the worker produced an output blob which was written
            # in shared memory
            output_data = response_msg.response.output_data
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

            # Verify if the shared memory region's information is valid
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
        """
        Read a blob with binary input that was transferred between the host and
        worker over shared memory.
        The function's input data type will be str.
        """
        func_name = 'get_blob_as_str_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            # Write binary content into shared memory
            mem_map_name = self.get_new_mem_map_name()
            content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
            num_chars = int(content_size / consts.SIZE_OF_CHAR_BYTES)
            content = self.get_random_string(num_chars)
            content_bytes = content.encode('utf-8')
            content_md5 = hashlib.md5(content_bytes).hexdigest()
            mem_map_size = consts.CONTENT_HEADER_TOTAL_BYTES + content_size
            mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                        mem_map_size)
            shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                             mem_map)
            num_bytes_written = shared_mem_map.put_bytes(content_bytes)

            # Create a message to send to the worker containing info about the
            # shared memory region to read input from
            value = protos.RpcSharedMemory(
                name=mem_map_name,
                offset=0,
                count=num_bytes_written,
                type=protos.RpcDataType.string
            )

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, response_msg = await host.invoke_function(
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
                             response_msg.response.result.status)

            response_bytes = response_msg.response.return_value.http.body.bytes
            json_response = json.loads(response_bytes)
            func_received_num_chars = json_response['num_chars']
            func_received_content_md5 = json_response['content_md5']

            # Check the function response to ensure that it read the complete
            # input that we provided and the md5 matches
            self.assertEqual(num_chars, func_received_num_chars)
            self.assertEqual(content_md5, func_received_content_md5)

    async def test_str_blob_write_function(self):
        """
        Write a blob with string output that was transferred between the worker
        and host over shared memory.
        """
        func_name = 'put_blob_as_str_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
            num_chars = int(content_size / consts.SIZE_OF_CHAR_BYTES)
            http_params = {'num_chars': str(num_chars)}

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, response_msg = await host.invoke_function(
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
                             response_msg.response.result.status)

            # The function responds back in the HTTP body with the md5 digest of
            # the output it created along with its size
            response_bytes = response_msg.response.return_value.http.body.bytes
            json_response = json.loads(response_bytes)
            func_created_num_chars = json_response['num_chars']
            func_created_content_md5 = json_response['content_md5']

            # Verify if the worker produced an output blob which was written
            # in shared memory
            output_data = response_msg.response.output_data
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

            # Verify if the shared memory region's information is valid
            self.assertTrue(self.is_valid_uuid(mem_map_name))
            self.assertEqual(0, offset)
            self.assertEqual(func_created_num_chars, count)
            self.assertEqual(protos.RpcDataType.string, data_type)

            # Read data from the shared memory region
            mem_map_size = consts.CONTENT_HEADER_TOTAL_BYTES + count
            mem_map = self.file_accessor.open_mem_map(mem_map_name,
                                                      mem_map_size)
            shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                             mem_map)
            read_content_bytes = shared_mem_map.get_bytes()

            # Dispose the shared memory map since we have read the function's
            # output now
            shared_mem_map.dispose()

            # Verify if we were able to read the correct output that the
            # function has produced
            read_content_md5 = hashlib.md5(read_content_bytes).hexdigest()
            self.assertEqual(func_created_content_md5, read_content_md5)
            read_content = read_content_bytes.decode('utf-8')
            self.assertEqual(len(read_content), func_created_num_chars)

    async def test_close_shared_memory_maps(self):
        """
        Close the shared memory maps created by the worker to transfer output
        blob to the host after the host is done processing the response.
        """
        func_name = 'put_blob_as_bytes_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
            http_params = {'content_size': str(content_size)}

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, response_msg = await host.invoke_function(
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
                             response_msg.response.result.status)

            # Verify if the worker produced an output blob which was written
            # in shared memory
            output_data = response_msg.response.output_data
            output_binding = output_data[0]

            # Get the information about the shared memory region in which the
            # worker wrote the function's output blob
            shmem = output_binding.rpc_shared_memory
            mem_map_name = shmem.name

            # Request the worker to close the memory maps
            mem_map_names = [mem_map_name]
            response_msg = \
                await host.close_shared_memory_resources(mem_map_names)

            # Verify that the worker responds with a successful status after
            # closing the requested memory map
            mem_map_statuses = response_msg.response.close_map_results
            self.assertEqual(len(mem_map_names), len(mem_map_statuses.keys()))
            for mem_map_name in mem_map_names:
                self.assertTrue(mem_map_name in mem_map_statuses)
                status = mem_map_statuses[mem_map_name]
                self.assertTrue(status)

    async def test_shared_memory_not_used_with_small_output(self):
        """
        Even though shared memory is enabled, small inputs will not be
        transferred over shared memory (in this case from the worker to the
        host.)
        """
        func_name = 'put_blob_as_bytes_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER - 10
            http_params = {'content_size': str(content_size)}

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, response_msg = await host.invoke_function(
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
                             response_msg.response.result.status)

            # Verify if the worker produced an output blob which was sent over
            # RPC instead of shared memory
            output_data = response_msg.response.output_data
            self.assertEqual(1, len(output_data))

            output_binding = output_data[0]
            binding_type = output_binding.WhichOneof('rpc_data')
            self.assertEqual('data', binding_type)

    async def test_multiple_input_output_blobs(self):
        """
        Read two blobs and write two blobs, all over shared memory.
        """
        func_name = 'put_get_multiple_blobs_as_bytes_return_http_response'
        async with testutils.start_mockhost(script_root=self.blob_funcs_dir) \
                as host:
            await host.load_function(func_name)

            # Input 1
            # Write binary content into shared memory
            mem_map_name_1 = self.get_new_mem_map_name()
            input_content_size_1 = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
            input_content_1 = self.get_random_bytes(input_content_size_1)
            input_content_md5_1 = hashlib.md5(input_content_1).hexdigest()
            input_mem_map_size_1 = \
                consts.CONTENT_HEADER_TOTAL_BYTES + input_content_size_1
            input_mem_map_1 = \
                self.file_accessor.create_mem_map(mem_map_name_1,
                                                  input_mem_map_size_1)
            input_shared_mem_map_1 = \
                SharedMemoryMap(self.file_accessor, mem_map_name_1,
                                input_mem_map_1)
            input_num_bytes_written_1 = \
                input_shared_mem_map_1.put_bytes(input_content_1)

            # Create a message to send to the worker containing info about the
            # shared memory region to read input from
            input_value_1 = protos.RpcSharedMemory(
                name=mem_map_name_1,
                offset=0,
                count=input_num_bytes_written_1,
                type=protos.RpcDataType.bytes
            )

            # Input 2
            # Write binary content into shared memory
            mem_map_name_2 = self.get_new_mem_map_name()
            input_content_size_2 = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 20
            input_content_2 = self.get_random_bytes(input_content_size_2)
            input_content_md5_2 = hashlib.md5(input_content_2).hexdigest()
            input_mem_map_size_2 = \
                consts.CONTENT_HEADER_TOTAL_BYTES + input_content_size_2
            input_mem_map_2 = \
                self.file_accessor.create_mem_map(mem_map_name_2,
                                                  input_mem_map_size_2)
            input_shared_mem_map_2 = \
                SharedMemoryMap(self.file_accessor, mem_map_name_2,
                                input_mem_map_2)
            input_num_bytes_written_2 = \
                input_shared_mem_map_2.put_bytes(input_content_2)

            # Outputs
            output_content_size_1 = \
                consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 11
            output_content_size_2 = \
                consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 22
            http_params = {
                'output_content_size_1': str(output_content_size_1),
                'output_content_size_2': str(output_content_size_2)}

            # Create a message to send to the worker containing info about the
            # shared memory region to read input from
            input_value_2 = protos.RpcSharedMemory(
                name=mem_map_name_2,
                offset=0,
                count=input_num_bytes_written_2,
                type=protos.RpcDataType.bytes
            )

            # Invoke the function; it should read the input blob from shared
            # memory and respond back in the HTTP body with the number of bytes
            # it read in the input
            _, response_msg = await host.invoke_function(
                func_name, [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET',
                                query=http_params))),
                    protos.ParameterBinding(
                        name='input_file_1',
                        rpc_shared_memory=input_value_1
                    ),
                    protos.ParameterBinding(
                        name='input_file_2',
                        rpc_shared_memory=input_value_2
                    )
                ])

            # Dispose the shared memory map since the function is done using it
            input_shared_mem_map_1.dispose()
            input_shared_mem_map_2.dispose()

            # Verify if the function executed successfully
            self.assertEqual(protos.StatusResult.Success,
                             response_msg.response.result.status)

            response_bytes = response_msg.response.return_value.http.body.bytes
            json_response = json.loads(response_bytes)

            func_received_content_size_1 = json_response['input_content_size_1']
            func_received_content_md5_1 = json_response['input_content_md5_1']
            func_received_content_size_2 = json_response['input_content_size_2']
            func_received_content_md5_2 = json_response['input_content_md5_2']
            func_created_content_size_1 = json_response['output_content_size_1']
            func_created_content_size_2 = json_response['output_content_size_2']
            func_created_content_md5_1 = json_response['output_content_md5_1']
            func_created_content_md5_2 = json_response['output_content_md5_2']

            # Check the function response to ensure that it read the complete
            # input that we provided and the md5 matches
            self.assertEqual(input_content_size_1, func_received_content_size_1)
            self.assertEqual(input_content_md5_1, func_received_content_md5_1)
            self.assertEqual(input_content_size_2, func_received_content_size_2)
            self.assertEqual(input_content_md5_2, func_received_content_md5_2)

            # Verify if the worker produced two output blobs which were written
            # in shared memory
            output_data = response_msg.response.output_data
            self.assertEqual(2, len(output_data))

            # Output 1
            output_binding_1 = output_data[0]
            binding_type = output_binding_1.WhichOneof('rpc_data')
            self.assertEqual('rpc_shared_memory', binding_type)

            shmem_1 = output_binding_1.rpc_shared_memory
            self._verify_function_output(shmem_1, func_created_content_size_1,
                                         func_created_content_md5_1)

            # Output 2
            output_binding_2 = output_data[1]
            binding_type = output_binding_2.WhichOneof('rpc_data')
            self.assertEqual('rpc_shared_memory', binding_type)

            shmem_2 = output_binding_2.rpc_shared_memory
            self._verify_function_output(shmem_2, func_created_content_size_2,
                                         func_created_content_md5_2)

    async def _test_binary_blob_read_function(self, func_name):
        """
        Verify that the function executed successfully when the worker received
        inputs for the function over shared memory.
        """
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
            _, response_msg = await host.invoke_function(
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
                             response_msg.response.result.status)

            response_bytes = response_msg.response.return_value.http.body.bytes
            json_response = json.loads(response_bytes)
            func_received_content_size = json_response['content_size']
            func_received_content_md5 = json_response['content_md5']

            # Check the function response to ensure that it read the complete
            # input that we provided and the md5 matches
            self.assertEqual(content_size, func_received_content_size)
            self.assertEqual(content_md5, func_received_content_md5)

    def _verify_function_output(
            self,
            shmem: protos.RpcSharedMemory,
            expected_size: int,
            expected_md5: str):
        """
        Verify if the output produced by the worker is what we expect it to be
        based on the size and MD5 digest.
        """
        output_mem_map_name = shmem.name
        output_offset = shmem.offset
        output_count = shmem.count
        output_data_type = shmem.type

        # Verify if the shared memory region's information is valid
        self.assertTrue(self.is_valid_uuid(output_mem_map_name))
        self.assertEqual(0, output_offset)
        self.assertEqual(expected_size, output_count)
        self.assertEqual(protos.RpcDataType.bytes, output_data_type)

        # Read data from the shared memory region
        output_mem_map_size = \
            consts.CONTENT_HEADER_TOTAL_BYTES + output_count
        output_mem_map = \
            self.file_accessor.open_mem_map(output_mem_map_name,
                                            output_mem_map_size)
        output_shared_mem_map = \
            SharedMemoryMap(self.file_accessor, output_mem_map_name,
                            output_mem_map)
        output_read_content = output_shared_mem_map.get_bytes()

        # Dispose the shared memory map since we have read the function's
        # output now
        output_shared_mem_map.dispose()

        # Verify if we were able to read the correct output that the
        # function has produced
        output_read_content_md5 = hashlib.md5(output_read_content).hexdigest()
        self.assertEqual(expected_md5, output_read_content_md5)
        self.assertEqual(len(output_read_content), expected_size)
