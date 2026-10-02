# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Pure-Python, protobuf-free stand-in for the ``protos`` module the Azure
Functions Python runtime expects.

The shared runtime handlers (``handle_event``, ``loader``, ``functions``,
``meta``, ``tracing``, ``helpers``) are transport-agnostic: they never import
protobuf directly. They read request fields off ``request.request.<verb>`` and
build responses through a ``protos`` object injected at ``worker_init``. The
classic worker injects the ``google.protobuf`` gencode; the R2P2 injects
THIS module instead.

Nothing here touches ``google.protobuf``. Each message is a light data holder
whose constructor accepts the same keyword arguments the runtime passes to the
real protobuf types, plus:

  * promoted enum constants (e.g. ``StatusResult.Success``,
    ``BindingInfo.inout``, ``RpcLog.Critical``) with the SAME integer values as
    the ``.proto`` -- the runtime compares against these, so they must match.
  * ``to_dict()`` on the response messages, producing a plain ``dict`` of
    primitives that the Rust side maps to a prost message and encodes on the
    wire. Rust owns all protobuf encoding; Python owns only the object shapes.

Only the surface the runtime actually uses is implemented. Values default to the
proto defaults so partially-constructed messages behave like the real ones.
"""
from datetime import timedelta


# ---------------------------------------------------------------------------
# Enums (integer values pinned to proto/FunctionRpc.proto)
# ---------------------------------------------------------------------------
class _EnumWrapper:
    """Mimics protobuf's nested EnumTypeWrapper: supports ``.Value(name)`` and
    attribute access (``Cat.System``)."""

    def __init__(self, values):
        self._values = dict(values)
        for name, num in values:
            setattr(self, name, num)

    def Value(self, name):  # noqa: N802 (protobuf API name)
        return self._values[name]

    def Name(self, num):  # noqa: N802 (protobuf API name)
        for n, v in self._values.items():
            if v == num:
                return n
        raise ValueError(num)


class StatusResult:
    # StatusResult.Status
    Failure = 0
    Success = 1
    Cancelled = 2

    Status = _EnumWrapper([("Failure", 0), ("Success", 1), ("Cancelled", 2)])

    __slots__ = ("status", "exception", "result", "logs")

    def __init__(self, status=0, exception=None, result="", logs=None):
        self.status = status
        self.exception = exception
        self.result = result
        self.logs = logs

    def to_dict(self):
        return {
            "status": int(self.status or 0),
            "exception": self.exception.to_dict() if self.exception else None,
        }


class RpcException:
    __slots__ = ("message", "stack_trace", "source", "type")

    def __init__(self, message="", stack_trace="", source="", type=""):
        self.message = message
        self.stack_trace = stack_trace
        self.source = source
        self.type = type

    def to_dict(self):
        return {
            "message": self.message or "",
            "stack_trace": self.stack_trace or "",
            "source": self.source or "",
            "type": self.type or "",
        }


class WorkerMetadata:
    __slots__ = ("runtime_name", "runtime_version", "worker_version",
                 "worker_bitness", "custom_properties")

    def __init__(self, runtime_name="", runtime_version="", worker_version="",
                 worker_bitness="", custom_properties=None):
        self.runtime_name = runtime_name
        self.runtime_version = runtime_version
        self.worker_version = worker_version
        self.worker_bitness = worker_bitness
        self.custom_properties = custom_properties or {}

    def to_dict(self):
        return {
            "runtime_name": self.runtime_name or "",
            "runtime_version": self.runtime_version or "",
            "worker_version": self.worker_version or "",
            "worker_bitness": self.worker_bitness or "",
            "custom_properties": dict(self.custom_properties or {}),
        }


class BindingInfo:
    # BindingInfo.Direction
    in_ = 0
    out = 1
    inout = 2
    # BindingInfo.DataType
    undefined = 0
    string = 1
    binary = 2
    stream = 3

    Direction = _EnumWrapper([("in", 0), ("out", 1), ("inout", 2)])
    DataType = _EnumWrapper(
        [("undefined", 0), ("string", 1), ("binary", 2), ("stream", 3)])

    __slots__ = ("type", "data_type", "direction")

    def __init__(self, type="", data_type=0, direction=0):
        self.type = type
        # protobuf treats a None scalar kwarg as "unset" -> proto default (0);
        # the SDK passes data_type/direction=None for unspecified bindings.
        self.data_type = 0 if data_type is None else data_type
        self.direction = 0 if direction is None else direction

    def to_dict(self):
        return {
            "type": self.type or "",
            "data_type": int(self.data_type),
            "direction": int(self.direction),
        }


def _duration_seconds(value):
    """timedelta (what loader.py passes) -> whole seconds int for a
    prost/protobuf Duration. ``None`` stays ``None``."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return int(value)


class RpcRetryOptions:
    # RpcRetryOptions.RetryStrategy
    exponential_backoff = 0
    fixed_delay = 1

    RetryStrategy = _EnumWrapper(
        [("exponential_backoff", 0), ("fixed_delay", 1)])

    __slots__ = ("max_retry_count", "retry_strategy", "delay_interval",
                 "minimum_interval", "maximum_interval")

    def __init__(self, max_retry_count=0, retry_strategy=0,
                 delay_interval=None, minimum_interval=None,
                 maximum_interval=None):
        self.max_retry_count = max_retry_count
        # Runtime passes the strategy as its string name ("fixed_delay"); the
        # wire wants the enum int. Accept either (None -> proto default 0).
        if isinstance(retry_strategy, str):
            retry_strategy = self.RetryStrategy.Value(retry_strategy)
        self.retry_strategy = 0 if retry_strategy is None else retry_strategy
        self.delay_interval = delay_interval
        self.minimum_interval = minimum_interval
        self.maximum_interval = maximum_interval

    def to_dict(self):
        return {
            "max_retry_count": int(self.max_retry_count or 0),
            "retry_strategy": int(self.retry_strategy or 0),
            "delay_interval_seconds": _duration_seconds(self.delay_interval),
            "minimum_interval_seconds": _duration_seconds(
                self.minimum_interval),
            "maximum_interval_seconds": _duration_seconds(
                self.maximum_interval),
        }


class RpcFunctionMetadata:
    __slots__ = ("name", "function_id", "managed_dependency_enabled",
                 "directory", "script_file", "entry_point", "is_proxy",
                 "language", "bindings", "raw_bindings", "retry_options",
                 "properties")

    def __init__(self, name="", function_id="",
                 managed_dependency_enabled=False, directory="",
                 script_file="", entry_point="", is_proxy=False, language="",
                 bindings=None, raw_bindings=None, retry_options=None,
                 properties=None):
        self.name = name
        self.function_id = function_id
        self.managed_dependency_enabled = managed_dependency_enabled
        self.directory = directory
        self.script_file = script_file
        self.entry_point = entry_point
        self.is_proxy = is_proxy
        self.language = language
        self.bindings = bindings or {}
        self.raw_bindings = raw_bindings or []
        self.retry_options = retry_options
        self.properties = properties or {}

    def to_dict(self):
        return {
            "name": self.name or "",
            "function_id": self.function_id or "",
            "managed_dependency_enabled": bool(
                self.managed_dependency_enabled),
            "directory": self.directory or "",
            "script_file": self.script_file or "",
            "entry_point": self.entry_point or "",
            "is_proxy": bool(self.is_proxy),
            "language": self.language or "",
            "bindings": {k: v.to_dict() for k, v in
                         (self.bindings or {}).items()},
            "raw_bindings": list(self.raw_bindings or []),
            "retry_options": (self.retry_options.to_dict()
                              if self.retry_options else None),
            "properties": dict(self.properties or {}),
        }


class WorkerInitResponse:
    __slots__ = ("capabilities", "worker_metadata", "result")

    def __init__(self, capabilities=None, worker_metadata=None, result=None):
        self.capabilities = capabilities or {}
        self.worker_metadata = worker_metadata
        self.result = result

    def to_dict(self):
        return {
            "capabilities": dict(self.capabilities or {}),
            "worker_metadata": (self.worker_metadata.to_dict()
                                if self.worker_metadata else None),
            "result": self.result.to_dict() if self.result else None,
        }


class FunctionMetadataResponse:
    __slots__ = ("use_default_metadata_indexing", "function_metadata_results",
                 "result")

    def __init__(self, use_default_metadata_indexing=False,
                 function_metadata_results=None, result=None):
        self.use_default_metadata_indexing = use_default_metadata_indexing
        self.function_metadata_results = function_metadata_results
        self.result = result

    def to_dict(self):
        results = self.function_metadata_results
        return {
            "use_default_metadata_indexing": bool(
                self.use_default_metadata_indexing),
            "function_metadata_results": (
                [m.to_dict() for m in results] if results else []),
            "result": self.result.to_dict() if self.result else None,
        }


class FunctionLoadResponse:
    __slots__ = ("function_id", "result")

    def __init__(self, function_id="", result=None):
        self.function_id = function_id
        self.result = result

    def to_dict(self):
        return {
            "function_id": self.function_id or "",
            "result": self.result.to_dict() if self.result else None,
        }


class FunctionEnvironmentReloadResponse:
    __slots__ = ("capabilities", "worker_metadata", "result")

    def __init__(self, capabilities=None, worker_metadata=None, result=None):
        self.capabilities = capabilities or {}
        self.worker_metadata = worker_metadata
        self.result = result

    def to_dict(self):
        return {
            "capabilities": dict(self.capabilities or {}),
            "worker_metadata": (self.worker_metadata.to_dict()
                                if self.worker_metadata else None),
            "result": self.result.to_dict() if self.result else None,
        }


class WorkerStatusResponse:
    __slots__ = ()

    def to_dict(self):
        return {}


# ---------------------------------------------------------------------------
# Logging (RpcLog). Built by the bridge log handler; flattened for LogSink.
# ---------------------------------------------------------------------------
class RpcLog:
    # RpcLog.Level
    Trace = 0
    Debug = 1
    Information = 2
    Warning = 3
    Error = 4
    Critical = 5
    # "None" is a proto value (6) but a Python keyword; exposed via Level only.

    Level = _EnumWrapper([
        ("Trace", 0), ("Debug", 1), ("Information", 2), ("Warning", 3),
        ("Error", 4), ("Critical", 5), ("None", 6)])
    RpcLogCategory = _EnumWrapper(
        [("User", 0), ("System", 1), ("CustomMetric", 2)])

    __slots__ = ("level", "message", "category", "log_category",
                 "invocation_id", "event_id", "properties")

    def __init__(self, level=0, message="", category="", log_category=0,
                 invocation_id="", event_id="", properties=None):
        self.level = level
        self.message = message
        self.category = category
        self.log_category = log_category
        self.invocation_id = invocation_id
        self.event_id = event_id
        self.properties = properties or {}


# ---------------------------------------------------------------------------
# Invocation surface (TypedData & friends).
#
# The invocation *control path* (deferred / SDK-type bindings and http-v2
# streaming) runs the runtime's standard ``invocation_request`` handler, which
# reads inputs off ``protos.TypedData``/``ParameterBinding`` and builds outputs
# through the same types (see bindings/datumdef.py + bindings/meta.py). The
# native prost path (native_invocation.py) bypasses all of this, so these types
# are ONLY exercised on the control path.
#
# For the FFI boundary we exchange the same compact "datum tuple" the native
# path uses (see workers/r2p2/src/convert.rs):
#   scalar  -> ("string"|"json"|"int"|"double"|"bytes", <primitive>)
#   http in -> ("http", {method,url,headers,params,query,body:<tuple|None>})
#   http out-> ("http", {status_code:str, headers:{..}, body:<tuple|None>, ...})
#   mbd in  -> ("model_binding_data", {version,source,content_type,content})
#   coll in -> ("collection_string"|..., [values])
#   empty   -> None
# Rust builds the inbound tuples with prost; ``TypedData.from_tuple`` turns them
# into read-shaped adapter objects the runtime can decode. Outbound, the runtime
# builds adapter objects and ``.to_dict()`` flattens them back to tuples/dicts
# that Rust (prost) encodes on the wire.
# ---------------------------------------------------------------------------
class ModelBindingData:
    """Deferred (SDK-type) binding payload; read by the extension's decoder."""
    __slots__ = ("version", "source", "content_type", "content")

    def __init__(self, version="", source="", content_type="", content=b""):
        self.version = version
        self.source = source
        self.content_type = content_type
        self.content = content


class _Collection:
    """collection_* wrapper. Exposes the repeated field under its proto name
    (``.string``/``.bytes``/``.sint64``/``.double``) so ``Datum.python_value``
    can iterate it."""
    __slots__ = ("string", "bytes", "sint64", "double")

    def __init__(self, field, values):
        for f in self.__slots__:
            setattr(self, f, list(values) if f == field else [])


class NullableString:
    __slots__ = ("value",)

    def __init__(self, value=""):
        self.value = value

    def to_dict(self):
        return {"value": self.value or ""}


class NullableBool:
    __slots__ = ("value",)

    def __init__(self, value=False):
        self.value = value

    def to_dict(self):
        return {"value": bool(self.value)}


class NullableDouble:
    __slots__ = ("value",)

    def __init__(self, value=0.0):
        self.value = value

    def to_dict(self):
        return {"value": float(self.value)}


class NullableTimestamp:
    """Wraps a ``google.protobuf.Timestamp``-shaped object (``.seconds``). The
    runtime builds ``value=Timestamp(seconds=...)``; we only need the seconds."""
    __slots__ = ("value",)

    def __init__(self, value=None):
        self.value = value

    def to_dict(self):
        secs = int(getattr(self.value, "seconds", 0) or 0)
        return {"seconds": secs}


class RpcHttpCookie:
    # RpcHttpCookie.SameSite
    SameSite = _EnumWrapper(
        [("None", 0), ("Lax", 1), ("Strict", 2), ("ExplicitNone", 3)])

    __slots__ = ("name", "value", "domain", "path", "expires", "secure",
                 "http_only", "same_site", "max_age")

    def __init__(self, name="", value="", domain=None, path=None, expires=None,
                 secure=None, http_only=None, same_site=0, max_age=None):
        self.name = name
        self.value = value
        self.domain = domain
        self.path = path
        self.expires = expires
        self.secure = secure
        self.http_only = http_only
        self.same_site = same_site
        self.max_age = max_age

    def to_dict(self):
        def _nd(x):
            return x.to_dict() if x is not None else None
        return {
            "name": self.name or "",
            "value": self.value or "",
            "domain": _nd(self.domain),
            "path": _nd(self.path),
            "expires": _nd(self.expires),
            "secure": _nd(self.secure),
            "http_only": _nd(self.http_only),
            "same_site": int(self.same_site),
            "max_age": _nd(self.max_age),
        }


class RpcHttp:
    """RpcHttp stand-in. Supports INPUT reads
    (``method``/``url``/``headers``/``params``/``query``/``body``) and OUTPUT
    construction (``status_code``/``headers``/``cookies``/``body``/...)."""

    def __init__(self, method="", url="", headers=None, params=None,
                 query=None, body=None, status_code=None, cookies=None,
                 enable_content_negotiation=False):
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.params = params or {}
        self.query = query or {}
        self.body = body
        self.status_code = status_code
        self.cookies = cookies
        self.enable_content_negotiation = enable_content_negotiation

    def to_dict(self):
        return {
            "status_code": ("" if self.status_code is None
                            else str(self.status_code)),
            "headers": {k: str(v) for k, v in (self.headers or {}).items()},
            "body": self.body.to_dict() if self.body is not None else None,
            "cookies": [c.to_dict() for c in (self.cookies or [])],
            "enable_content_negotiation": bool(
                self.enable_content_negotiation),
        }


class TypedData:
    """The runtime's TypedData oneof. Constructed with exactly one field set
    (output, e.g. ``TypedData(http=...)``) or via :meth:`from_tuple` (input).
    Read like protobuf: ``WhichOneof('data')`` + attribute access."""

    _KINDS = (
        "string", "json", "bytes", "stream", "http", "int", "double",
        "collection_bytes", "collection_string", "collection_double",
        "collection_sint64", "model_binding_data",
        "collection_model_binding_data",
    )

    def __init__(self, **kwargs):
        self._kind = None
        self._value = None
        for k in self._KINDS:
            if k in kwargs and kwargs[k] is not None:
                self._kind = k
                self._value = kwargs[k]
                break

    def WhichOneof(self, name):  # noqa: N802 (protobuf API name)
        return self._kind

    def __getattr__(self, name):
        # Only reached for missing attributes (``_kind``/``_value`` are set in
        # __init__ and resolve normally). Return the payload for the active
        # oneof field, else the proto default (None-ish) for other oneof names.
        if name in TypedData._KINDS:
            if self.__dict__.get("_kind") == name:
                return self.__dict__.get("_value")
            return None
        raise AttributeError(name)

    def to_dict(self):
        k = self._kind
        if k is None:
            return None
        if k == "http":
            return ("http", self._value.to_dict())
        return (k, self._value)

    @classmethod
    def from_tuple(cls, t):
        if t is None:
            return cls()
        kind, val = t
        if kind == "http":
            return cls(http=RpcHttp(
                method=val.get("method", ""),
                url=val.get("url", ""),
                headers=val.get("headers") or {},
                params=val.get("params") or {},
                query=val.get("query") or {},
                body=cls.from_tuple(val.get("body")),
            ))
        if kind == "model_binding_data":
            return cls(model_binding_data=ModelBindingData(
                version=val.get("version", ""),
                source=val.get("source", ""),
                content_type=val.get("content_type", ""),
                content=val.get("content", b""),
            ))
        if kind in ("collection_string", "collection_bytes",
                    "collection_sint64", "collection_double"):
            field = kind.split("_", 1)[1]
            return cls(**{kind: _Collection(field, val)})
        return cls(**{kind: val})


class ParameterBinding:
    """Invocation input/output binding: ``name`` + ``data`` (a TypedData)."""
    __slots__ = ("name", "data")

    def __init__(self, name="", data=None):
        self.name = name
        self.data = data

    def WhichOneof(self, name):  # noqa: N802 (protobuf API name)
        # oneof rpc_data { TypedData data = 2; ... }
        return "data" if self.data is not None else None

    def to_dict(self):
        return {
            "name": self.name or "",
            "data": self.data.to_dict() if self.data is not None else None,
        }


class InvocationResponse:
    __slots__ = ("invocation_id", "return_value", "result", "output_data")

    def __init__(self, invocation_id="", return_value=None, result=None,
                 output_data=None):
        self.invocation_id = invocation_id
        self.return_value = return_value
        self.result = result
        self.output_data = output_data or []

    def to_dict(self):
        return {
            "invocation_id": self.invocation_id or "",
            "return_value": (self.return_value.to_dict()
                             if self.return_value is not None else None),
            "result": self.result.to_dict() if self.result else None,
            "output_data": [pb.to_dict() for pb in (self.output_data or [])],
        }
