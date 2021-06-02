# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import unittest

from azure_functions_worker import logging as flog


class TestLogging(unittest.TestCase):
    """This class is for testing the grpc logging behavior in Python Worker.
    Here's a list of expected behaviors:
                  local_console  customer_app_insight  functions_kusto_table
    system_log    false          false                 true
    customer_log  true           true                  false

    Please ensure the following unit test cases align with the expectations
    """

    def test_system_log_namespace(self):
        """Ensure the following list is part of the system's log
        """
        self.assertTrue(flog.is_system_log_category('azure_functions_worker'))
        self.assertTrue(
            flog.is_system_log_category('azure_functions_worker_error')
        )
        self.assertTrue(flog.is_system_log_category('azure.functions'))
        self.assertTrue(flog.is_system_log_category('azure.functions.module'))

    def test_customer_log_namespace(self):
        """Ensure the following list is part of the customer's log
        """
        self.assertFalse(flog.is_system_log_category('customer_logger'))
        self.assertFalse(flog.is_system_log_category('azure'))
        self.assertFalse(flog.is_system_log_category('protobuf'))
        self.assertFalse(flog.is_system_log_category('root'))
        self.assertFalse(flog.is_system_log_category(''))
