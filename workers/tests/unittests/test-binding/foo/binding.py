# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from azure.functions import meta


class Binding(meta.InConverter, meta.OutConverter,
              binding='fooType'):
    pass
