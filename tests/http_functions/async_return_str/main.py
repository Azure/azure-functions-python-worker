import asyncio
import azure.functions


async def main(req: azure.functions.HttpRequest, context):
    await asyncio.sleep(0.1)
    return 'Hello Async World!'
