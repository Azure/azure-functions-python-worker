# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Protobuf-free invocation entry for the v2 runtime (used by the Rust proxy worker).

The classic ``handle_event.invocation_request`` is coupled to protobuf: it reads
fields off an ``InvocationRequest`` protobuf object and builds the response with
the injected ``protos`` module (``from_incoming_proto`` -> ``Datum.from_typed_data``
and ``to_outgoing_proto`` -> ``datum_as_proto``). When the Rust worker owns the
wire (prost), the hot path should never touch Python protobuf.

This module provides that native seam. It takes/returns the runtime's own
protobuf-free intermediate type -- ``Datum`` -- and reuses the exact same
binding/execution helpers that ``invocation_request`` uses, so behaviour is
identical minus the protobuf edges. The wire<->Datum conversion is done in Rust.

Contract:
    invocation_request_native(
        invocation_id: str,
        function_id: str,
        inputs: list[tuple[str, Datum]],          # (param name, decoded Datum)
        trigger_metadata: dict[str, Datum],
    ) -> tuple[bool, Optional[Datum], list[tuple[str, Datum]], Optional[str]]
        # (ok, return_datum, output_data, exception_text)

Scope: this native path supports the classic (non http-v2) binding path,
sync and async functions, input/output bindings and $return. Deferred (SDK-type)
bindings and the http-v2 streaming path are intentionally out of scope here and
fall back through the protobuf control path if ever needed.
"""
import sys

from .bindings.context import get_context
from .bindings.meta import get_binding, get_datum, is_trigger_binding
from .bindings.out import Out
from .handle_event import _functions
from .logging import logger
from .utils.executor import (execute_async, get_current_loop,
                             invocation_id_cv, run_sync_func)
from .utils.threadpool import get_threadpool_executor


class _TraceCtx:
    trace_parent = ""
    trace_state = ""
    attributes: dict = {}


class _RetryCtx:
    retry_count = 0
    max_retry_count = 0
    exception = None


class _InvocShim:
    """Minimal stand-in for the InvocationRequest proto that ``get_context`` reads."""
    __slots__ = ("invocation_id", "trace_context", "retry_context")

    def __init__(self, invocation_id):
        self.invocation_id = invocation_id
        self.trace_context = _TraceCtx()
        self.retry_context = _RetryCtx()


# --- Shared Datum-currency helpers -------------------------------------------
#
# The sync and async native paths differ ONLY in how the handler is executed
# (directly on the calling thread vs. on the event loop / threadpool). Decoding
# inputs, preparing the invocation context, validating the return, and encoding
# outputs are identical and protobuf-free, so they live here and are reused by
# both entries below. Keeping them here (not in ``handle_event``) preserves the
# "no Python protobuf on the hot path" boundary.


def _decode_inputs(fi, inputs, trigger_metadata):
    """Rust-provided ``(name, Datum)`` inputs -> decoded handler args dict."""
    metadata = trigger_metadata or {}
    args = {}
    for name, datum in inputs:
        pb_type_info = fi.input_types[name]
        tm = metadata if is_trigger_binding(pb_type_info.binding_name) else {}
        binding_obj = get_binding(
            pb_type_info.binding_name,
            pb_type_info.deferred_bindings_enabled)
        args[name] = binding_obj.decode(datum, trigger_metadata=tm)
    return args


def _prepare_context(fi, invocation_id, args):
    """Build the invocation context and scaffold ``Out`` params into *args*.

    Does NOT stamp ``thread_local_storage.invocation_id`` -- the sync path lets
    ``run_sync_func`` do that on the executing thread, while the async path sets
    it explicitly on the caller's context (see below)."""
    fi_context = get_context(_InvocShim(invocation_id), fi.name, fi.directory)
    if fi.requires_context:
        args['context'] = fi_context
    if fi.output_types:
        for name in fi.output_types:
            args[name] = Out()
    return fi_context


def _check_return(fi, call_result):
    if call_result is not None and not fi.has_return:
        raise RuntimeError(
            'function %s without a $return binding returned a non-None value'
            % repr(fi.name))


def _collect_output(fi, args):
    """Decoded ``Out`` params -> ``[(name, Datum)]`` for Rust to prost-encode."""
    output_data = []
    if fi.output_types:
        for out_name, out_type_info in fi.output_types.items():
            val = args[out_name].get()
            if val is None:
                continue
            datum = get_datum(out_type_info.binding_name, val,
                              out_type_info.pytype)
            output_data.append((out_name, datum))
    return output_data


def _encode_return(fi, call_result):
    if fi.return_type is not None:
        return get_datum(fi.return_type.binding_name, call_result,
                         fi.return_type.pytype)
    return None


async def invocation_request_native(invocation_id, function_id, inputs,
                                    trigger_metadata):
    threadpool = get_threadpool_executor()
    fi = _functions.get_function(function_id)
    if fi is None:
        return (False, None, [], "function %s not loaded" % function_id)

    try:
        args = _decode_inputs(fi, inputs, trigger_metadata)
        fi_context = _prepare_context(fi, invocation_id, args)
        fi_context.thread_local_storage.invocation_id = invocation_id

        if fi.is_async:
            # Correlate user logs emitted from async handlers with this
            # invocation. The sync path sets invocation_id_cv inside
            # run_sync_func; the async handler runs on the caller's context, so
            # set/reset it here. Each invocation is its own asyncio Task (the
            # Rust bridge submits via run_coroutine_threadsafe, which copies the
            # context), so concurrent invocations don't clobber each other.
            token = invocation_id_cv.set(invocation_id)
            try:
                call_result = await execute_async(fi.func, args)
            finally:
                invocation_id_cv.reset(token)
        else:
            _loop = get_current_loop()
            call_result = await _loop.run_in_executor(
                threadpool, run_sync_func,
                invocation_id, fi_context, fi.func, args)

        _check_return(fi, call_result)
        output_data = _collect_output(fi, args)
        return_datum = _encode_return(fi, call_result)

        sys.stdout.flush()
        return (True, return_datum, output_data, None)

    except Exception as ex:  # noqa - surfaced to the Host as a failed invocation
        logger.exception("Native invocation failed")
        return (False, None, [], repr(ex))


def run_invocation_sync(invocation_id, function_id, inputs, trigger_metadata):
    """Synchronous native invocation for *sync* customer functions.

    Runs the handler directly on the calling thread (no asyncio loop, no
    ``run_in_executor`` bounce). With the Rust transport dispatching each call
    on its own thread, this avoids funneling sync handlers through a single
    event loop, trimming per-invocation overhead on the hot path.

    Returns ``(handled, ok, return_datum, output_data, exception_text)``.
    ``handled=False`` means the function is ``async`` and the caller should use
    the coroutine path (:func:`invocation_request_native`) instead.
    """
    fi = _functions.get_function(function_id)
    if fi is None:
        return (True, False, None, [], "function %s not loaded" % function_id)
    if fi.is_async:
        return (False, None, None, [], None)

    try:
        args = _decode_inputs(fi, inputs, trigger_metadata)
        fi_context = _prepare_context(fi, invocation_id, args)

        call_result = run_sync_func(invocation_id, fi_context, fi.func, args)

        _check_return(fi, call_result)
        output_data = _collect_output(fi, args)
        return_datum = _encode_return(fi, call_result)

        return (True, True, return_datum, output_data, None)

    except Exception as ex:  # noqa - surfaced to the Host as a failed invocation
        logger.exception("Native sync invocation failed")
        return (True, False, None, [], repr(ex))
