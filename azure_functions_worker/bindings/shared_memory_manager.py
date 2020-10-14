# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from .. import protos
from ..logging import logger

class SharedMemoryManager:
    def __init__(self):
        pass

    def get(self, td: protos.SharedMemoryData):
        logger.info('Reading from Shared Memory: %s', td)
        print('Reading from Shared Memory: %s' % td)
        return 'foo'.encode('utf-8'), td.type
