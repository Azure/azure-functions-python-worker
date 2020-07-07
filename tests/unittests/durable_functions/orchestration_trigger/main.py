# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# import azure.durable_functions as df


def generator_function(context):
    final_result = yield context.call_activity('activity_trigger', 'foobar')
    return final_result


def main(context):
    # orchestrate = df.Orchestrator.create(generator_function)
    # result = orchestrate(context)
    # return result
    return f'{context} :)'
