import json

import azure.functions


def main(req: azure.functions.HttpRequest, context: azure.functions.Context):
    return json.dumps({
        'method': req.method,
        'ctx_func_name': context.function_name,
        'ctx_func_dir': context.function_directory,
        'ctx_invocation_id': context.invocation_id,
    })
