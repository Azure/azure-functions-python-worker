# # Copyright (c) Microsoft Corporation. All rights reserved.
# # Licensed under the MIT License.
# import time
#
# from requests import JSONDecodeError
#
# from tests.utils import testutils
#
#
# class TestSdkBlobFunctions(testutils.WebHostTestCase):
#
#     @classmethod
#     def get_script_dir(cls):
#         return testutils.E2E_TESTS_FOLDER / 'sdk_functions' / "blob_functions"
#
#     @testutils.retryable_test(3, 5)
#     def test_blob_str(self):
#         r = self.webhost.request('POST', 'put_blob_str2', data='test-data')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         r = self.webhost.request('GET', 'get_bc_str')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'test-data')
#
#         r = self.webhost.request('GET', 'get_cc_str')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'test-data')
#
#         r = self.webhost.request('GET', 'get_ssd_str')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'test-data')
#
#     def test_blob_large_str(self):
#         large_string = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB
#
#         r = self.webhost.request('POST', 'put_blob_str', data=large_string)
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         r = self.webhost.request('GET', 'get_bc_str')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, large_string)
#
#         r = self.webhost.request('GET', 'get_cc_str')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, large_string)
#
#         r = self.webhost.request('GET', 'get_ssd_str')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, large_string)
#
#     def test_blob_bytes(self):
#         r = self.webhost.request('POST', 'put_blob_bytes',
#                                  data='test-dată'.encode('utf-8'))
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         r = self.webhost.request('POST', 'get_bc_bytes')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'test-dată')
#
#         r = self.webhost.request('POST', 'get_cc_bytes')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'test-dată')
#
#         r = self.webhost.request('POST', 'get_ssd_bytes')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'test-dată')
#
#     def test_blob_large_bytes(self):
#         large_string = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB
#
#         r = self.webhost.request('POST', 'put_blob_bytes',
#                                  data=large_string.encode('utf-8'))
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         r = self.webhost.request('GET', 'get_bc_bytes')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, large_string)
#
#         r = self.webhost.request('GET', 'get_cc_bytes')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, large_string)
#
#         r = self.webhost.request('GET', 'get_ssd_bytes')
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, large_string)
#
#     def test_blob_trigger(self):
#         data = "DummyData"
#
#         r = self.webhost.request('POST', 'put_blob_trigger',
#                                  data=data.encode('utf-8'))
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         # Blob trigger may be processed after some delay
#         # We check it every 2 seconds to allow the trigger to be fired
#         max_retries = 10
#         for try_no in range(max_retries):
#             time.sleep(2)
#
#             try:
#                 # Check that the trigger has fired
#                 r = self.webhost.request('GET', 'get_blob_triggered')
#                 self.assertEqual(r.status_code, 200)
#                 response = r.json()
#
#                 self.assertEqual(response['name'],
#                                  'python-worker-tests/test-blob-trigger.txt')
#                 self.assertEqual(response['content'], data)
#
#                 break
#             except AssertionError:
#                 if try_no == max_retries - 1:
#                     raise
#
#     def test_bc_blob_trigger_with_large_content(self):
#         data = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB
#
#         r = self.webhost.request('POST', 'put_blob_trigger',
#                                  data=data.encode('utf-8'))
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         # Blob trigger may be processed after some delay
#         # We check it every 2 seconds to allow the trigger to be fired
#         max_retries = 10
#         for try_no in range(max_retries):
#             try:
#                 # Check that the trigger has fired
#                 r = self.webhost.request('GET', 'get_bc_blob_triggered')
#
#                 # Waiting for blob to get updated
#                 time.sleep(2)
#
#                 self.assertEqual(r.status_code, 200)
#                 response = r.json()
#
#                 self.assertEqual(response['name'],
#                                  'python-worker-tests/test-blob-trigger.txt')
#                 self.assertEqual(response['content'], data)
#                 break
#             # JSONDecodeError will be thrown if the response is empty.
#             except AssertionError or JSONDecodeError:
#                 if try_no == max_retries - 1:
#                     raise
#
#     def test_cc_blob_trigger_with_large_content(self):
#         data = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB
#
#         r = self.webhost.request('POST', 'put_blob_trigger',
#                                  data=data.encode('utf-8'))
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         # Blob trigger may be processed after some delay
#         # We check it every 2 seconds to allow the trigger to be fired
#         max_retries = 10
#         for try_no in range(max_retries):
#             try:
#                 # Check that the trigger has fired
#                 r = self.webhost.request('GET', 'get_cc_blob_triggered')
#
#                 # Waiting for blob to get updated
#                 time.sleep(2)
#
#                 self.assertEqual(r.status_code, 200)
#                 response = r.json()
#
#                 self.assertEqual(response['name'],
#                                  'python-worker-tests')
#                 self.assertEqual(response['content'], data)
#                 break
#             # JSONDecodeError will be thrown if the response is empty.
#             except AssertionError or JSONDecodeError:
#                 if try_no == max_retries - 1:
#                     raise
#
#     # SSD
#     def test_ssd_blob_trigger_with_large_content(self):
#         data = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB
#
#         r = self.webhost.request('POST', 'put_blob_trigger',
#                                  data=data.encode('utf-8'))
#         self.assertEqual(r.status_code, 200)
#         self.assertEqual(r.text, 'OK')
#
#         # Blob trigger may be processed after some delay
#         # We check it every 2 seconds to allow the trigger to be fired
#         max_retries = 10
#         for try_no in range(max_retries):
#             try:
#                 # Check that the trigger has fired
#                 r = self.webhost.request('GET', 'get_ssd_blob_triggered')
#
#                 # Waiting for blob to get updated
#                 time.sleep(2)
#
#                 self.assertEqual(r.status_code, 200)
#                 response = r.json()
#
#                 self.assertEqual(response['content'], data)
#                 break
#             # JSONDecodeError will be thrown if the response is empty.
#             except AssertionError or JSONDecodeError:
#                 if try_no == max_retries - 1:
#                     raise
