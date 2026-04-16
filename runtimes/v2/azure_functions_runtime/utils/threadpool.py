from __future__ import annotations

import multiprocessing
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Optional, Union

from .app_setting_manager import get_app_setting
from .constants import (
    PYTHON_PROCESS_COUNT,
    PYTHON_PROCESS_COUNT_MIN,
    PYTHON_PROCESS_COUNT_MAX,
    PYTHON_THREADPOOL_THREAD_COUNT,
    PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT,
    PYTHON_THREADPOOL_THREAD_COUNT_MIN,
    PYTHON_THREADPOOL_THREAD_COUNT_MAX,
)
from ..logging import logger

_threadpool_executor: Optional[Union[ThreadPoolExecutor, ProcessPoolExecutor]] = None


def _validate_thread_count(value: str) -> bool:
    try:
        int_value = int(value)
    except ValueError:
        logger.warning('%s must be an integer', PYTHON_THREADPOOL_THREAD_COUNT)
        return False

    if (int_value < PYTHON_THREADPOOL_THREAD_COUNT_MIN
            or int_value > PYTHON_THREADPOOL_THREAD_COUNT_MAX):
        logger.warning(
            '%s must be set to a value between %s and %s. Reverting to '
            'default value (%s).',
            PYTHON_THREADPOOL_THREAD_COUNT,
            PYTHON_THREADPOOL_THREAD_COUNT_MIN,
            PYTHON_THREADPOOL_THREAD_COUNT_MAX,
            PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT,
        )
        return False
    return True


def _validate_process_count(value: str) -> bool:
    try:
        int_value = int(value)
    except ValueError:
        logger.warning('%s must be an integer', PYTHON_PROCESS_COUNT)
        return False

    if (int_value < PYTHON_PROCESS_COUNT_MIN
            or int_value > PYTHON_PROCESS_COUNT_MAX):
        logger.warning(
            '%s must be set to a value between %s and %s. Falling back to '
            'ThreadPoolExecutor.',
            PYTHON_PROCESS_COUNT,
            PYTHON_PROCESS_COUNT_MIN,
            PYTHON_PROCESS_COUNT_MAX,
        )
        return False
    return True


def _get_max_workers() -> Optional[int]:
    threadpool_count = get_app_setting(
        setting=PYTHON_THREADPOOL_THREAD_COUNT,
        validator=_validate_thread_count,
    )
    if threadpool_count is None:
        return None
    try:
        return int(threadpool_count)
    except (TypeError, ValueError) as e:
        logger.warning(
            'Failed to convert %s value "%s" to integer: %s',
            PYTHON_THREADPOOL_THREAD_COUNT, threadpool_count, e
        )
        return None


def start_threadpool_executor() -> None:
    """Start thread or process pool executor based on configuration.
    
    If PYTHON_PROCESS_COUNT is set, creates a ProcessPoolExecutor with the
    specified number of worker processes. Otherwise, creates a ThreadPoolExecutor
    with the number of threads specified by PYTHON_THREADPOOL_THREAD_COUNT.
    """
    global _threadpool_executor

    if _threadpool_executor is not None:
        try:
            _threadpool_executor.shutdown(wait=False)
        except Exception:
            pass

    # Check if process pool is requested
    process_count_str = get_app_setting(
        setting=PYTHON_PROCESS_COUNT,
        validator=_validate_process_count,
    )

    if process_count_str:
        # Use ProcessPoolExecutor
        try:
            process_count = int(process_count_str)
            # Use 'spawn' context for Windows compatibility
            mp_context = multiprocessing.get_context('spawn')
            _threadpool_executor = ProcessPoolExecutor(
                max_workers=process_count,
                mp_context=mp_context
            )
            logger.info(
                'Started ProcessPoolExecutor (id=%s) with %s worker processes',
                id(_threadpool_executor),
                process_count,
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                'Failed to create ProcessPoolExecutor with %s=%s: %s. '
                'Falling back to ThreadPoolExecutor.',
                PYTHON_PROCESS_COUNT,
                process_count_str,
                e
            )
            # Fall through to create ThreadPoolExecutor
            process_count_str = None

    if not process_count_str:
        # Use ThreadPoolExecutor (default)
        max_workers = _get_max_workers()
        _threadpool_executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(
            'Started ThreadPoolExecutor (id=%s) with max_workers=%s',
            id(_threadpool_executor),
            max_workers if max_workers else 'default',
        )


def stop_threadpool_executor() -> None:
    """Stop the current executor (ThreadPoolExecutor or ProcessPoolExecutor)."""
    global _threadpool_executor
    if _threadpool_executor is not None:
        executor_type = type(_threadpool_executor).__name__
        executor_id = id(_threadpool_executor)
        try:
            _threadpool_executor.shutdown(wait=True)
            logger.info(
                'Stopped %s (id=%s)',
                executor_type,
                executor_id
            )
        finally:
            _threadpool_executor = None


def get_threadpool_executor() -> Optional[Union[ThreadPoolExecutor, ProcessPoolExecutor]]:
    """Get the current executor instance.
    
    Returns either a ThreadPoolExecutor or ProcessPoolExecutor depending on
    the configuration (PYTHON_PROCESS_COUNT setting).
    """
    return _threadpool_executor
