import logging
import logging.handlers
import sys


logger = logging.getLogger('azure.functions_worker')
error_logger = logger


def setup(log_level, log_destination):
    global error_logger

    if log_level == 'TRACE':
        log_level = 'DEBUG'

    formatter = logging.Formatter(
        'LanguageWorkerConsoleLog %(levelname)s: %(message)s')

    if log_destination is None:
        # With no explicit log destination we do split logging,
        # errors go into stderr, everything else -- to stdout.
        error_handler = logging.StreamHandler(sys.stderr)
        error_handler.setFormatter(formatter)
        error_handler.setLevel(getattr(logging, log_level))

        error_logger = logging.getLogger('azure.functions_worker_errors')
        error_logger.addHandler(error_handler)

        handler = logging.StreamHandler(sys.stdout)

    elif log_destination in ('stdout', 'stderr'):
        handler = logging.StreamHandler(getattr(sys, log_destination))

    elif log_destination == 'syslog':
        handler = logging.handlers.SysLogHandler()

    else:
        handler = logging.FileHandler(log_destination)

    handler.setFormatter(formatter)
    handler.setLevel(getattr(logging, log_level))

    logger.addHandler(handler)
    logger.setLevel(getattr(logging, log_level))
