# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from datetime import datetime

import azure.functions as func


def main(req: func.HttpRequest,
         outputEvent: func.Out[func.EventGridOutputEvent]) -> func.HttpResponse:
    test_uuid = req.params.get('test_uuid')
    data_to_event_grid = func.EventGridOutputEvent(id="test-id",
                                                   data={
                                                       "test_uuid": test_uuid
                                                   },
                                                   subject="test-subject",
                                                   event_type="test-event-1",
                                                   event_time=datetime.utcnow(),
                                                   data_version="1.0")

    outputEvent.set(data_to_event_grid)
    r_value = "Sent event with subject: {}, id: {}, data: {}, event_type: {} " \
              "to EventGrid!".format(data_to_event_grid.subject,
                                     data_to_event_grid.id,
                                     data_to_event_grid.get_json(),
                                     data_to_event_grid.event_type)
    return func.HttpResponse(r_value)
