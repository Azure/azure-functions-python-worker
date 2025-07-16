# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import os
import time

from azure.cosmos import CosmosClient, PartitionKey
from unittest import skip

from tests.utils import testutils

url = os.getenv("CosmosDBEmulatorUrl")
key = os.getenv("CosmosDBEmulatorKey")
client = CosmosClient(url, key)


# Create a database in the account using the CosmosClient
database_name = "test"
try:
    database = client.create_database(id=database_name)
except Exception:
    database = client.get_database_client(database=database_name)

# Create a container
container_name = "items"
try:
    container = database.create_container(
        id=container_name, partition_key=PartitionKey(path="/id")
    )
except Exception:
    container = database.get_container_client(container_name)

# Create a lease container
lease_container_name = "leases"
try:
    lease_container = database.create_container(
        id=lease_container_name, partition_key=PartitionKey(path="/id")
    )
except Exception:
    lease_container = database.get_container_client(lease_container_name)


class TestCosmosDBFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'cosmosdb_functions'

    def test_cosmosdb_trigger(self):
        data = str(round(time.time()))
        doc = {'id': 'cosmosdb-trigger-test',
               'data': data}
        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        time.sleep(5)  # Wait for the trigger to execute

        r = self.webhost.request('GET', 'get_cosmosdb_triggered')
        self.assertEqual(r.status_code, 200)
        response = r.json()
        response.pop('_metadata', None)

        self.assertEqual(response['id'], doc['id'])
        self.assertTrue('_etag' in response)
        self.assertTrue('_lsn' in response)
        self.assertTrue('_rid' in response)
        self.assertTrue('_ts' in response)

    @skip("Waiting for 'Read collection feed' support in CosmosDB Emulator")
    def test_cosmosdb_input(self):
        data = str(round(time.time()))
        doc = {'id': 'cosmosdb-input-test',
               'data': data}
        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        time.sleep(5)  # Wait for the trigger to execute

        r = self.webhost.request('GET', 'cosmosdb_input')
        self.assertEqual(r.status_code, 200)
        response = r.json()

        # _lsn is present for cosmosdb change feed only,
        # ref https://aka.ms/cosmos-change-feed
        self.assertEqual(response['id'], doc['id'])
        self.assertEqual(response['data'], doc['data'])
        self.assertTrue('_etag' in response)
        self.assertTrue('_rid' in response)
        self.assertTrue('_self' in response)
        self.assertTrue('_ts' in response)


class TestCosmosDBFunctionsStein(TestCosmosDBFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'cosmosdb_functions' / \
            'cosmosdb_functions_stein'


class TestCosmosDBFunctionsSteinGeneric(TestCosmosDBFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'cosmosdb_functions' / \
            'cosmosdb_functions_stein' / 'generic'
