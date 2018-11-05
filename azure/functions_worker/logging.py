import logging
import logging.handlers
import sys


logger = logging.getLogger('azure.functions_worker')


def setup(log_level, log_destination):
    if log_level == 'TRACE':
        log_level = 'DEBUG'

    if log_destination in ('stdout', 'stderr'):
        handler = logging.StreamHandler(getattr(sys, log_destination))

    elif log_destination == 'syslog':
        handler = logging.handlers.SysLogHandler()

    else:
        handler = logging.FileHandler(log_destination)

    formatter = logging.Formatter(
        'LanguageWorkerConsoleLog %(levelname)s: %(message)s')

    handler.setFormatter(formatter)
    handler.setLevel(getattr(logging, log_level))

    logger.addHandler(handler)
    logger.setLevel(getattr(logging, log_level))
