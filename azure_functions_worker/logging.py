import logging
import logging.handlers
import sys


logger = logging.getLogger('azure_functions_worker')
error_logger = logging.getLogger('azure_functions_worker_errors')

handler = None
error_handler = None


def setup(log_level, log_destination):
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

        handler = logging.StreamHandler(sys.stdout)

    elif log_destination in ('stdout', 'stderr'):
        handler = logging.StreamHandler(getattr(sys, log_destination))

    elif log_destination == 'syslog':
        handler = logging.handlers.SysLogHandler()

    else:
        handler = logging.FileHandler(log_destination)

    if error_handler is None:
        error_handler = handler

    handler.setFormatter(formatter)
    handler.setLevel(getattr(logging, log_level))

    logger.addHandler(handler)
    logger.setLevel(getattr(logging, log_level))

    error_logger.addHandler(error_handler)
    error_logger.setLevel(getattr(logging, log_level))


def disable_console_logging():
    if logger and handler:
        logger.removeHandler(handler)

    if error_logger and error_handler:
        error_logger.removeHandler(error_handler)


def enable_console_logging():
    if logger and handler:
        logger.addHandler(handler)

    if error_logger and error_handler:
        error_logger.addHandler(error_handler)


def is_system_log_category(ctg: str):
    return any(
        [ctg.lower().startswith(c) for c in (
            'azure_functions_worker',
            'azure_functions_worker_errors'
        )]
    )
