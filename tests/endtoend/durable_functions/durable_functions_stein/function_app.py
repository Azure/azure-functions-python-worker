import logging

import azure.durable_functions as df
import azure.functions as func

app = df.DFApp()


@app.orchestration_trigger(context_name="context")
def durablefunctionsorchestrator(context):
    result1 = yield context.call_activity("Hello", "Tokyo")
    result2 = yield context.call_activity("Hello", "Seattle")
    result3 = yield context.call_activity("Hello", "London")
    return [result1, result2, result3]


@app.route(route="orchestrators/{functionName}", auth_level=func.AuthLevel.ANONYMOUS)
@app.durable_client_input(client_name="client")
async def durable_client(req: func.HttpRequest, client) -> func.HttpResponse:
    instance_id = await client.start_new(req.route_params["functionName"], None, None)
    logging.info(f"Started orchestration with ID = '{instance_id}'.")
    return client.create_check_status_response(req, instance_id)


@app.activity_trigger(input_name="name")
def hello(name: str) -> str:
    return f"Hello {name}!"
