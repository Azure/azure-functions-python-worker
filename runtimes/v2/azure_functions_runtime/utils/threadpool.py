from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .app_setting_manager import get_app_setting
from .constants import (
    PYTHON_THREADPOOL_THREAD_COUNT,
    PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT,
    PYTHON_THREADPOOL_THREAD_COUNT_MIN,
    PYTHON_THREADPOOL_THREAD_COUNT_MAX,
)
from ..logging import logger

_threadpool_executor: Optional[ThreadPoolExecutor] = None


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
    global _threadpool_executor
    max_workers = _get_max_workers()

    if _threadpool_executor is not None:
        try:
            _threadpool_executor.shutdown(wait=False)
        except Exception:
            pass

    _threadpool_executor = ThreadPoolExecutor(max_workers=max_workers)
    logger.debug(
        'Started threadpool executor (id=%s) with max_workers=%s',
        id(_threadpool_executor),
        max_workers,
    )


def stop_threadpool_executor() -> None:
    global _threadpool_executor
    if _threadpool_executor is not None:
        try:
            _threadpool_executor.shutdown(wait=True)
            logger.debug(
                'Stopped threadpool executor (id=%s)',
                id(_threadpool_executor)
            )
        finally:
            _threadpool_executor = None


def get_threadpool_executor() -> Optional[ThreadPoolExecutor]:
    return _threadpool_executor
