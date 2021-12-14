# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import os

import azure.functions as func
import certifi


# An HttpTrigger to generating Kafka event from confluent SDK.
# Events generated from confluent library contain the full metadata.
from confluent_kafka import Producer


async def main(req: func.HttpRequest):
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    message = req.params.get('message')
    if not message:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            message = req_body.get('message')

    producer = _build_producer()
    # Send out event into confluent hub
    await _write_on_topic(producer)

    return f'OK'


async def _write_on_topic(producer):
    topic = os.environ['ConfluentKafkaTopic']
    record_key = "1"
    record_value = "test"
    producer.produce(topic, key=record_key, value=record_value, on_delivery=acked)
    producer.poll(0)
    producer.flush()


def _build_producer():
    producer_conf = {}
    producer_conf['bootstrap.servers'] = os.environ['ConfluentKafkaBrokerList']
    producer_conf['security.protocol'] = 'SASL_SSL'
    producer_conf['sasl.mechanisms'] = 'PLAIN'
    producer_conf['sasl.username'] = os.environ['ConfluentKafkaUsername']
    producer_conf['sasl.password'] = os.environ['ConfluentKafkaPassword']
    producer_conf.pop('schema.registry.url', None)
    producer_conf.pop('basic.auth.user.info', None)
    producer_conf.pop('basic.auth.credentials.source', None)
    producer_conf['ssl.ca.location'] = certifi.where()
    producer = Producer(producer_conf)
    return producer

def acked(err, msg):
    if err is not None:
        logging.error("Failed to deliver message: {}".format(err))
    else:
        logging.info("Produced record to topic {} partition [{}] @ offset {}"
                  .format(msg.topic(), msg.partition(), msg.offset()))