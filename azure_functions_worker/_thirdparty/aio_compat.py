"""Backport of asyncio.run() function from Python 3.7.

Source: https://github.com/python/cpython/blob/
        bd093355a6aaf2f4ca3ed153e195da57870a55eb/Lib/asyncio/runners.py
"""


import asyncio


def get_running_loop():
    """Return the running event loop.  Raise a RuntimeError if there is none.

    This function is thread-specific.
    """
    loop = asyncio._get_running_loop()
    if loop is None:
        raise RuntimeError('no running event loop')
    return loop


def run(main, *, debug=False):
    """Run a coroutine.

    This function runs the passed coroutine, taking care of
    managing the asyncio event loop and finalizing asynchronous
    generators.

    This function cannot be called when another asyncio event loop is
    running in the same thread.

    If debug is True, the event loop will be run in debug mode.
    This function always creates a new event loop and closes it at the end.

    It should be used as a main entry point for asyncio programs, and should
    ideally only be called once.
    """
    if asyncio._get_running_loop() is not None:
        raise RuntimeError(
            "asyncio.run() cannot be called from a running event loop")

    if not asyncio.iscoroutine(main):
        raise ValueError("a coroutine was expected, got {!r}".format(main))

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.set_debug(debug)
        return loop.run_until_complete(main)
    finally:
        try:
            _cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


def _cancel_all_tasks(loop):
    to_cancel = [task for task in asyncio.Task.all_tasks(loop)
                 if not task.done()]
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(
        asyncio.gather(*to_cancel, loop=loop, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'unhandled exception during asyncio.run() shutdown',
                'exception': task.exception(),
                'task': task,
            })


try:
    # Try to import the 'run' function from asyncio.
    from asyncio import run, get_running_loop  # NoQA
except ImportError:
    # Python <= 3.6
    pass
