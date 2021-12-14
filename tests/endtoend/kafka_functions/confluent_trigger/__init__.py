# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
from azure.functions import KafkaEvent


# This is an actual Kafka trigger which will convert the event data
# into a storage blob.
def main(kevent: KafkaEvent) -> bytes:
    logging.info(kevent.get_body().decode('utf-8'))
    return kevent.get_body()
