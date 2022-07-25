---
title: "(Private Preview) PyStein: New Python Programming Model"
date: 2022-07-19T22:58:54-08:00
draft: false
---

## Getting Started

Currently, the Python programming model is in the alpha release.

To try out the new programming model, download PyStein Custom Core Tools and follow the instructions below. Note that downloading the file will not overwrite the existing core tools in your device.

## Installation & Setup

- Download PyStein Custom Core Tools 
  - [Windows](https://functionsintegclibuilds.blob.core.windows.net/builds/4/latest/Azure.Functions.Cli.win-x64.zip)
  - [Linux](https://functionsintegclibuilds.blob.core.windows.net/builds/4/latest/Azure.Functions.Cli.linux-x64.zip)
  - [macOS](https://functionsintegclibuilds.blob.core.windows.net/builds/4/latest/Azure.Functions.Cli.osx-x64.zip)
- Unzip the folder to extract the files.
- If you are using a Mac, and get a notification that '<file name> cannot be opened because teh developer cannnot be verified', go to Settings and click 'Allow <file name>' to proceed.
- Clone the [starter repository](https://github.com/YunchuWang/python-functions-new-prg-model-starter) to set up the function app.
  - Note, in `local.settings.json`, the flag for `AzureWebJobsFeatureFlags` is set to `EnableWorkerIndexing`.
- Run `func` from the unzipped path directly
  - `<path_to_core_tools>/func host start`
  - Please update the storage account connection string in the `local.settings.json`.
- For reference, view [examples for the new programming model](https://github.com/gavin-aguiar/python-functions-new-prg-model).
- Let us know your feedback in the [GitHub discussion](https://github.com/Azure/azure-functions-python-worker/discussions/959).

E.g. For Windows:
- Option 1: Referencing the func in this folder when running `func host start`.
  - `C:\Users\test_user\Downloads\CoreTools-PyStein-win\CoreTools-New-Prg-Model\func`
- Option 2: Alias (using `Set-Alias` in Powershell) the func to this folder. Note that this will impact your existing core tools if you don't reset it when you are done testing.
  - `Set-Alias -Name func -Value C:\Users\test_user\Downloads\CoreTools-PyStein-win\CoreTools-New-Prg-Model\func`

## Notes & Limitations

- At this time, when using the attached core tools, only the new programming model will be supported.
- HTTP annotation is taken as an argument
- The name of the function script file must be 'function_app.py'. In the case that this file is not found, the worker will fall back to legacy indexing which is not supported when using this version of core tools.
- Mix and match of the legacy and new programming model is not supported
- If the function app is configured with Flask framework, the HTTP bindings will not work as expected. Other configured HTTP triggers also will not work, note that this is a behavior present today as well.
- At this time, all testing will be local as the new programming model is not available in production.

View [http-only-example](https://github.com/gavin-aguiar/python-functions-new-prg-model-http),  [examples-non-http](https://github.com/gavin-aguiar/python-functions-new-prg-model) for the new programming model.

## Specification

Reference specification of the decorator is available at [ProgModelSpec.pyi at Azure library repo](https://github.com/Azure/azure-functions-python-library/blob/dev/docs/ProgModelSpec.pyi).

The reference documentation including design is available in this [document](https://microsoft-my.sharepoint.com/:w:/p/vameru/EXcVUDxPjn9Pu-1WWCHppbcBW_QrppTx7jjf0Zuy1zTZOg?e=3Ql5LN).

## Our Goals

The current Python programming model in Azure Functions has limitations that sometimes prevents a customer from having a smooth onboarding experience. This includes the facts that there are too many files present, that the Function App structure can be confusing, and that file configuration follows Azure specific concepts rather than what Python frameworks.

To overcome these challenges, the Azure Functions Python team ideated a new programming model which eases the learning experience for new and existing customers. Specifically, the new programming model involves a single .py file (`function_app.py`) and will no longer require the `function.json` file. Furthermore, the triggers and bindings usage will be decorators, simulating an experience similar to Flask.

# Help us Test

Interesting in helping us test the new programming model? Sign up for a scenario [here](https://microsoft-my.sharepoint.com/:x:/p/shbatr/EZR02oGmw-9AjI8AALS3Ye0B0_cBJ8b5AzDEJBhHjAe5jw?e=zuFPet)

## Triggers & Bindings

At this time, the new Programming model supports HTTP, Timer, Event Hub, Queue, Service Bus, and Cosmos DB. The following are examples of the implementation with the new programming model.

### HTTP

```python
import azure.functions as func

app = func.FunctionApp(auth_level=func.AuthLevel.ANONYMOUS)

@app.function_name(name="HttpTrigger1")
@app.route(route="hello") # HTTP Trigger
def test_function(req: func.HttpRequest) -> func.HttpResponse:
     return func.HttpResponse("HttpTrigger1 function processed a request!!!")


@app.function_name(name="HttpTrigger2")
@app.route(route="hello2") # HTTP Trigger
def test_function2(req: func.HttpRequest) -> func.HttpResponse:
     return func.HttpResponse("HttpTrigger2 function processed a request!!!")
```
### Timer
```python
@app.function_name(name="timertest")
@app.schedule(schedule="*/10 * * * * *", arg_name="dummy", run_on_startup=False,use_monitor=False) # Timer Trigger
def timer_function(dummy: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if dummy.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)
```

### Event Hub

```python
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="EventHubFunc")
@app.event_hub_message_trigger(arg_name="myhub", event_hub_name="testhub", connection="EHConnectionString") # Eventhub trigger
@app.write_event_hub_message(arg_name="outputhub", event_hub_name="testhub", connection="EHConnectionString") # Eventhub output binding
def eventhub_trigger(myhub: func.EventHubEvent, outputhub: func.Out[str]):
    outputhub.set("hello")
```

### Queue

```python
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="QueueFunc")
@app.queue_trigger(arg_name="msg", queue_name="js-queue-items", connection="storageAccountConnectionString") # Queue trigger
@app.write_queue(arg_name="outputQueueItem", queue_name="outqueue", connection="storageAccountConnectionString") # Queue output binding
def test_function(msg: func.QueueMessage, outputQueueItem: func.Out[str]) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))
    outputQueueItem.set('hello')
```    

### Service Bus

```python
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="ServiceBusTopicFunc")
@app.service_bus_topic_trigger(arg_name="serbustopictrigger", topic_name="testtopic", connection="topicConnectionString", subscription_name="testsub") # service bus topic trigger
@app.write_service_bus_topic(arg_name="serbustopicbinding", connection="outputtopicConnectionString",  topic_name="outputtopic", subscription_name="testsub") # service bus topic output binding 
def main(serbustopictrigger: func.ServiceBusMessage, serbustopicbinding: func.Out[str]) -> None:
    logging.info('Python ServiceBus queue trigger processed message.')

    result = json.dumps({
        'message_id': serbustopictrigger.message_id,
        'body': serbustopictrigger.get_body().decode('utf-8'),
        'content_type': serbustopictrigger.content_type,
        'expiration_time': serbustopictrigger.expiration_time,
        'label': serbustopictrigger.label,
        'partition_key': serbustopictrigger.partition_key,
        'reply_to': serbustopictrigger.reply_to,
        'reply_to_session_id': serbustopictrigger.reply_to_session_id,
        'scheduled_enqueue_time': serbustopictrigger.scheduled_enqueue_time,
        'session_id': serbustopictrigger.session_id,
        'time_to_live': serbustopictrigger.time_to_live
    }, default=str)

    logging.info(result)
    serbustopicbinding.set("topic works!!")
```

```python
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="ServiceBusQueueFunc")
@app.service_bus_queue_trigger(arg_name="serbustopictrigger", queue_name="inputqueue", connection="queueConnectionString") # service bus queue trigger
@app.write_service_bus_queue(arg_name="serbustopicbinding", connection="queueConnectionString",  queue_name="outputqueue")  # service bus queue output binding 
def main(serbustopictrigger: func.ServiceBusMessage, serbustopicbinding: func.Out[str]) -> None:
    logging.info('Python ServiceBus queue trigger processed message.')

    result = json.dumps({
        'message_id': serbustopictrigger.message_id,
        'body': serbustopictrigger.get_body().decode('utf-8'),
        'content_type': serbustopictrigger.content_type,
        'expiration_time': serbustopictrigger.expiration_time,
        'label': serbustopictrigger.label,
        'partition_key': serbustopictrigger.partition_key,
        'reply_to': serbustopictrigger.reply_to,
        'reply_to_session_id': serbustopictrigger.reply_to_session_id,
        'scheduled_enqueue_time': serbustopictrigger.scheduled_enqueue_time,
        'session_id': serbustopictrigger.session_id,
        'time_to_live': serbustopictrigger.time_to_live
    }, default=str)

    logging.info(result)
    serbustopicbinding.set("queue works!!")
```

### Cosmos DB

```python
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="Cosmos1")
@app.cosmos_db_trigger(arg_name="triggerDocs", database_name="billdb", collection_name="billcollection", connection_string_setting="CosmosDBConnectionString",
 lease_collection_name="leasesstuff", create_lease_collection_if_not_exists="true") # Cosmos DB Trigger
@app.write_cosmos_db_documents(arg_name="outDoc", database_name="billdb", collection_name="outColl", connection_string_setting="CosmosDBConnectionString") # Cosmos DB input binding
@app.read_cosmos_db_documents(arg_name="inDocs", database_name="billdb", collection_name="incoll", connection_string_setting="CosmosDBConnectionString") # Cosmos DB output binding
def main(triggerDocs: func.DocumentList, inDocs: func.DocumentList, outDoc: func.Out[func.Document]) -> str:
    if triggerDocs:
        triggerDoc = triggerDocs[0]
        logging.info(inDocs[0]['text'])
        triggerDoc['ssss'] = 'Hello updated2!'
        outDoc.set(triggerDoc)
```

### Storage Blobs

```python
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="BlobFunc")
@app.blob_trigger(arg_name="triggerBlob", path="input-container/{name}", connection="AzureWebJobsStorage")
@app.write_blob(arg_name="outputBlob", path="output-container/{name}", connection="AzureWebJobsStorage")
@app.read_blob(arg_name="readBlob", path="output-container/{name}", connection="AzureWebJobsStorage")
def test_function(triggerBlob: func.InputStream , readBlob : func.InputStream, outputBlob: func.Out[str]) -> None:
    logging.info(f"Blob trigger executed!")
    logging.info(f"Blob Name: {triggerBlob.name} ({triggerBlob.length}) bytes")
    logging.info(f"Full Blob URI: {triggerBlob.uri}")
    outputBlob.set('hello')
    logging.info(f"Output blob: {readBlob.read()}")
```
  
### Event Grid
```python
import azure.functions as func

app = func.FunctionApp()
  
@app.function_name(name="eventGridTrigger")
@app.event_grid_trigger(arg_name="eventGridEvent")
@app.write_event_grid(
    arg_name="outputEvent",
    topic_endpoint_uri="MyEventGridTopicUriSetting",
    topic_key_setting="MyEventGridTopicKeySetting")
def main(eventGridEvent: func.EventGridEvent,
         outputEvent: func.Out[func.EventGridOutputEvent]) -> None:
    logging.info("eventGridEvent: ", eventGridEvent)

    outputEvent.set(
        func.EventGridOutputEvent(
            id="test-id",
            data={"tag1": "value1", "tag2": "value2"},
            subject="test-subject",
            event_type="test-event-1",
            event_time=datetime.datetime.utcnow(),
            data_version="1.0"))
```

## What's Next

View  [http-only-example](https://github.com/gavin-aguiar/python-functions-new-prg-model-http),  [examples-non-http](https://github.com/gavin-aguiar/python-functions-new-prg-model) for the new programming model.
Let us know your feedback in the [GitHub discussion](https://github.com/Azure/azure-functions-python-worker/discussions/959).

## Upcoming Features

- Additional trigger and binding support for Durable functions
- Event Grid
- Kafka
- SQL
- Visual Studio Code support
