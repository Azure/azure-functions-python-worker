import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Global counter to track retry attempts
retry_attempts = {}


# An HttpTrigger to generate EventHub event from EventHub Output Binding
@app.function_name(name="eventhub_retry_output")
@app.route(route="eventhub_retry_output")
@app.event_hub_output(arg_name="event",
                      event_hub_name="python-worker-ci-eventhub-retry",
                      connection="AzureWebJobsEventHubConnectionString")
def eventhub_retry_output(req: func.HttpRequest, event: func.Out[str]):
    event.set(req.get_body().decode('utf-8'))
    return 'OK'


# EventHub trigger with exponential backoff retry policy (no explicit intervals)
@app.function_name(name="eventhub_retry_trigger")
@app.retry(strategy="exponential_backoff", max_retry_count="3",
           minimum_interval="00:00:01",
           maximum_interval="00:00:02")
@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="python-worker-ci-eventhub-retry",
    connection="AzureWebJobsEventHubConnectionString"
)
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventhub-retry-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventhub_retry_trigger(event: func.EventHubEvent, context: func.Context) -> bytes:
    event_id = event.get_body().decode('utf-8')
    retry_count = context.retry_context.retry_count if context.retry_context else 0
    max_retry = context.retry_context.max_retry_count if context.retry_context else 0

    logging.info(f'EventHub retry trigger processed event: {event_id}, '
                 f'retry count: {retry_count}, max retry: {max_retry}')

    # Track retry attempts
    if event_id not in retry_attempts:
        retry_attempts[event_id] = []
    retry_attempts[event_id].append(retry_count)

    # Create result dictionary
    result = {
        'event_id': event_id,
        'retry_count': retry_count,
        'max_retry_count': max_retry,
        'all_attempts': retry_attempts[event_id]
    }

    # Fail on first two attempts to test retry
    if retry_count < 2:
        logging.warning(f'Simulating failure for retry test (attempt {retry_count})')
        raise Exception(f"Simulated failure for retry testing (attempt {retry_count})")

    # Success on third attempt
    logging.info(f'Success on attempt {retry_count}')
    return json.dumps(result).encode('utf-8')


# Retrieve the event data from storage blob and return it as Http response
@app.function_name(name="get_eventhub_retry_triggered")
@app.route(route="get_eventhub_retry_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventhub-retry-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventhub_retry_triggered(req: func.HttpRequest,
                                 file: func.InputStream) -> str:
    return file.read().decode('utf-8')


# HTTP endpoint to check retry state (for testing)
@app.function_name(name="get_retry_state")
@app.route(route="get_retry_state")
def get_retry_state(req: func.HttpRequest) -> str:
    return json.dumps(retry_attempts)


# HTTP endpoint to reset retry state
@app.function_name(name="reset_retry_state")
@app.route(route="reset_retry_state")
def reset_retry_state(req: func.HttpRequest) -> str:
    global retry_attempts
    retry_attempts = {}
    return 'Reset complete'
