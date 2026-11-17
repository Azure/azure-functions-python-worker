# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Annotation registration tests independent of the installed SDK version.

Converter spies test delegation; HTTP and generic fallback guards remain real.
Python below 3.13 tests the worker; Python 3.13+ tests the runtime libraries.
AZURE_FUNCTIONS_TEST_LEGACY_REGISTRY=1 adds legacy worker coverage on 3.13+.
"""

import collections.abc
import importlib
import inspect
import os
from pathlib import Path
import sys
from types import GenericAlias, SimpleNamespace
import typing
from unittest.mock import Mock

import azure.functions as azf
import pytest


ROOT = Path(__file__).resolve().parents[3]
INCLUDE_LEGACY = (
    sys.version_info < (3, 13)
    or os.environ.get("AZURE_FUNCTIONS_TEST_LEGACY_REGISTRY") == "1"
)
COPIES = []
if INCLUDE_LEGACY:
    COPIES.append(pytest.param(
        ("workers", "azure_functions_worker"), id="worker"))
if sys.version_info >= (3, 13):
    COPIES.extend([
        pytest.param(("runtimes/v1", "azure_functions_runtime_v1"),
                     id="runtime-v1"),
        pytest.param(("runtimes/v2", "azure_functions_runtime"),
                     id="runtime-v2"),
    ])


@pytest.fixture(params=COPIES)
def implementation(request, monkeypatch):
    source, package = request.param
    for relative in ("workers", "runtimes/v1", "runtimes/v2"):
        monkeypatch.syspath_prepend(str(ROOT / relative))
    functions = importlib.import_module(f"{package}.functions")
    meta = importlib.import_module(f"{package}.bindings.meta")
    generic = importlib.import_module(f"{package}.bindings.generic")
    for module, relative in (
        (functions, "functions.py"),
        (meta, "bindings/meta.py"),
        (generic, "bindings/generic.py"),
    ):
        expected = ROOT / source / package / relative
        assert Path(module.__file__).resolve() == expected.resolve()
    monkeypatch.setattr(meta, "BINDING_REGISTRY", azf.get_binding_registry(),
                        raising=False)
    if hasattr(meta, "DEFERRED_BINDING_REGISTRY"):
        monkeypatch.setattr(meta, "DEFERRED_BINDING_REGISTRY", None)
    if hasattr(meta, "_DEFERRED_BINDING_REGISTRY_LOADED"):
        monkeypatch.setattr(meta, "_DEFERRED_BINDING_REGISTRY_LOADED", True)
    # Use one generated protocol package per process: both copies register
    # FunctionRpc.proto in the same global protobuf descriptor pool.
    protocol_package = (
        "azure_functions_worker" if INCLUDE_LEGACY else "proxy_worker")
    protos = importlib.import_module(f"{protocol_package}.protos")
    return SimpleNamespace(
        functions=functions, meta=meta, protos=protos,
        generic=generic.GenericBinding,
    )


def validate_parameter(
        implementation, annotation=inspect.Parameter.empty, *,
        direction="in", binding_type="eventHubTrigger"):
    """Exercise validation, adapting only the implementation's signature."""
    registry = implementation.functions.Registry
    protos = implementation.protos
    parameter = inspect.Parameter(
        "value", inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=annotation,
    )
    annotations = {} if annotation is inspect.Parameter.empty else {
        "value": annotation
    }
    binding = SimpleNamespace(
        type=binding_type,
        direction=getattr(protos.BindingInfo, direction),
        data_type=protos.BindingInfo.undefined,
    )
    kwargs = {}
    signature = inspect.signature(registry.validate_function_params)
    if "protos" in signature.parameters:
        kwargs["protos"] = protos
    result = registry.validate_function_params(
        {"value": parameter}, {"value": binding}, annotations, "test", **kwargs
    )
    return result[:2]


def explicit_return(implementation, annotation, binding_type="eventHub"):
    return implementation.functions.Registry.get_function_return_type(
        {"return": annotation}, True, False, binding_type, "test"
    )


@pytest.mark.parametrize("annotation", [
    pytest.param(azf.EventHubEvent, id="event"),
    pytest.param(typing.List[azf.EventHubEvent], id="typing-list"),
    pytest.param(list[azf.EventHubEvent], id="builtin-list"),
    pytest.param(
        collections.abc.Sequence[azf.EventHubEvent], id="abc-sequence"
    ),
    # Element compatibility, including union membership, belongs to the SDK.
    pytest.param(
        list[typing.Union[azf.EventHubEvent, str]], id="typing-union-item"
    ),
    pytest.param(list[azf.EventHubEvent | str], id="pep604-union-item"),
])
def test_eventhub_input_preserves_sdk_accepted_annotation(
        implementation, annotation, monkeypatch):
    converter = azf.get_binding_registry().get("eventHubTrigger")
    validator = Mock(return_value=True)
    monkeypatch.setattr(converter, "check_input_type_annotation", validator)

    inputs, outputs = validate_parameter(implementation, annotation)

    validator.assert_called_once_with(annotation)
    assert outputs == {}
    assert inputs["value"].binding_name == "eventHubTrigger"
    assert inputs["value"].pytype is annotation


@pytest.mark.parametrize("annotation", [
    pytest.param(typing.List[str], id="typing-list"),
    pytest.param(list[str], id="builtin-list"),
    pytest.param(collections.abc.Sequence[str], id="abc-sequence"),
    pytest.param(list[typing.Union[str, bytes]], id="typing-union-item"),
    pytest.param(list[str | bytes], id="pep604-union-item"),
    pytest.param(typing.List[typing.Union[str, dict]], id="typing-str-dict"),
    pytest.param(list[str | dict], id="builtin-str-dict"),
])
def test_out_preserves_sdk_accepted_nested_annotation(
        implementation, annotation, monkeypatch):
    converter = azf.get_binding_registry().get("eventHub")
    validator = Mock(return_value=True)
    monkeypatch.setattr(converter, "check_output_type_annotation", validator)

    out_annotation = azf.Out[annotation]
    inputs, outputs = validate_parameter(
        implementation, out_annotation,
        direction="out", binding_type="eventHub",
    )

    validator.assert_called_once_with(typing.get_args(out_annotation)[0])
    assert inputs == {}
    assert outputs["value"].binding_name == "eventHub"
    # typing may cache Out[T] using an equal (but not identical) alias.
    assert outputs["value"].pytype is typing.get_args(out_annotation)[0]
    assert outputs["value"].pytype == annotation


@pytest.mark.parametrize("annotation", [
    pytest.param(typing.List[int], id="typing-list-int"),
    pytest.param(list[int], id="builtin-list-int"),
    pytest.param(collections.abc.Sequence[int], id="abc-sequence-int"),
    pytest.param(list[list[azf.EventHubEvent]], id="nested-list"),
    pytest.param(list["EventHubEvent"], id="forward-item"),
    pytest.param(list[typing.Union[int, str]], id="incompatible-union-item"),
    pytest.param(list[typing.Union[int, list[str]]], id="nonclass-union-item"),
])
def test_eventhub_input_delegates_element_rejection_to_sdk(
        implementation, annotation, monkeypatch):
    converter = azf.get_binding_registry().get("eventHubTrigger")
    validator = Mock(return_value=False)
    monkeypatch.setattr(converter, "check_input_type_annotation", validator)

    # Assert delegation of the SDK decision, not SDK element policy.
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match="does not match") as exc_info:
        validate_parameter(implementation, annotation)
    validator.assert_called_once_with(annotation)
    assert repr(annotation) in str(exc_info.value)


@pytest.mark.parametrize("annotation", [
    pytest.param(typing.List[int], id="typing-list-int"),
    pytest.param(list[int], id="builtin-list-int"),
    pytest.param(list[bytes], id="list-bytes"),
    pytest.param(list[list[str]], id="nested-list"),
    pytest.param(list["str"], id="forward-item"),
    pytest.param(list[int | bytes], id="incompatible-union-item"),
])
def test_out_delegates_element_rejection_to_sdk(
        implementation, annotation, monkeypatch):
    converter = azf.get_binding_registry().get("eventHub")
    validator = Mock(return_value=False)
    monkeypatch.setattr(converter, "check_output_type_annotation", validator)
    out_annotation = azf.Out[annotation]
    nested_annotation = typing.get_args(out_annotation)[0]

    # Out[T] may cache an equal alias; delegate its actual inner annotation.
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match="does not match") as exc_info:
        validate_parameter(
            implementation, out_annotation,
            direction="out", binding_type="eventHub",
        )
    validator.assert_called_once_with(nested_annotation)
    assert repr(nested_annotation) in str(exc_info.value)


UNSUPPORTED = [
    pytest.param(typing.Tuple[azf.EventHubEvent, ...], id="typing-tuple"),
    pytest.param(tuple[azf.EventHubEvent, ...], id="builtin-tuple"),
    pytest.param(typing.Union[azf.EventHubEvent, str], id="typing-union"),
    pytest.param(azf.EventHubEvent | str, id="pep604-union"),
    pytest.param(typing.ClassVar[azf.EventHubEvent], id="classvar"),
    pytest.param(typing.Callable[..., azf.EventHubEvent], id="typing-callable"),
    pytest.param(
        collections.abc.Callable[..., azf.EventHubEvent], id="abc-callable"
    ),
    pytest.param(typing.Annotated[azf.EventHubEvent, "metadata"], id="annotated"),
    pytest.param(typing.Literal["event"], id="literal"),
    pytest.param("EventHubEvent", id="forward-string"),
    pytest.param(typing.ForwardRef("EventHubEvent"), id="forward-ref"),
]


@pytest.mark.parametrize("annotation", UNSUPPORTED)
@pytest.mark.parametrize("is_out", [False, True], ids=["input", "out"])
def test_parameter_rejects_unsupported_annotation(
        implementation, annotation, is_out):
    # Pass raw annotations directly: get_type_hints at the loader boundary may
    # resolve strings or strip Annotated before this validation layer sees them.
    if is_out:
        # Bypass typing's subscription-time checks (notably for ClassVar) so
        # unsupported inner forms reach the worker's own validation boundary.
        annotation = GenericAlias(azf.Out, (annotation,))
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match="invalid non-type annotation"):
        validate_parameter(
            implementation, annotation,
            direction="out" if is_out else "in",
            binding_type="eventHub" if is_out else "eventHubTrigger",
        )


@pytest.mark.parametrize("annotation", [
    pytest.param(azf.Out, id="unparameterized"),
    pytest.param(GenericAlias(azf.Out, ()), id="zero-arguments"),
    pytest.param(GenericAlias(azf.Out, (str, bytes)), id="two-arguments"),
])
def test_rejects_malformed_out(implementation, annotation):
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match="invalid Out annotation"):
        validate_parameter(
            implementation, annotation,
            direction="out", binding_type="eventHub",
        )


def test_out_annotation_requires_output_direction(implementation):
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match='declared to have the "in" direction'):
        validate_parameter(implementation, azf.Out[list[str]])


def test_output_direction_requires_out_annotation(implementation):
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match='declared to have the "out" direction'):
        validate_parameter(
            implementation, list[str], direction="out", binding_type="eventHub"
        )


@pytest.mark.parametrize("name,direction,message", [
    ("value", "inout", '"inout" bindings are not supported'),
    ("$return", "in", 'must have direction set to "out"'),
])
def test_rejects_invalid_binding_direction(
        implementation, name, direction, message):
    registry = implementation.functions.Registry
    kwargs = {}
    signature = inspect.signature(registry.validate_binding_direction)
    if "protos" in signature.parameters:
        kwargs["protos"] = implementation.protos
    with pytest.raises(
            implementation.functions.FunctionLoadError, match=message):
        registry.validate_binding_direction(
            name, getattr(implementation.protos.BindingInfo, direction),
            "test", **kwargs,
        )


@pytest.mark.parametrize("direction", ["in", "out"])
def test_unannotated_parameter_still_accepted(implementation, direction):
    inputs, outputs = validate_parameter(
        implementation, direction=direction, binding_type="eventHub"
    )
    selected, other = (
        (inputs, outputs) if direction == "in" else (outputs, inputs)
    )
    assert other == {}
    assert selected["value"].binding_name == "eventHub"
    assert selected["value"].pytype is None


@pytest.mark.parametrize("annotation", [
    pytest.param(str, id="str"),
    pytest.param(typing.List[str], id="typing-list"),
    pytest.param(list[str], id="builtin-list"),
    pytest.param(collections.abc.Sequence[str], id="abc-sequence"),
    pytest.param(list[str | bytes], id="union-item"),
])
def test_explicit_return_preserves_sdk_accepted_annotation(
        implementation, annotation, monkeypatch):
    converter = azf.get_binding_registry().get("eventHub")
    validator = Mock(return_value=True)
    monkeypatch.setattr(converter, "check_output_type_annotation", validator)

    result = explicit_return(implementation, annotation)

    validator.assert_called_once_with(annotation)
    assert result.binding_name == "eventHub"
    assert result.pytype is annotation


@pytest.mark.parametrize("annotation", [list[int], list[bytes], list[list[str]]])
def test_explicit_return_delegates_element_rejection_to_sdk(
        implementation, annotation, monkeypatch):
    converter = azf.get_binding_registry().get("eventHub")
    validator = Mock(return_value=False)
    monkeypatch.setattr(converter, "check_output_type_annotation", validator)
    # The worker must honor rejection independently of released SDK policy.
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match="does not match") as exc_info:
        explicit_return(implementation, annotation)
    validator.assert_called_once_with(annotation)
    assert repr(annotation) in str(exc_info.value)


@pytest.mark.parametrize("annotation", UNSUPPORTED)
def test_explicit_return_rejects_unsupported_annotation(
        implementation, annotation):
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match="invalid non-type return annotation"):
        explicit_return(implementation, annotation)


@pytest.mark.parametrize("annotation", [
    pytest.param(azf.Out, id="unparameterized"),
    pytest.param(azf.Out[str], id="scalar"),
    pytest.param(azf.Out[typing.List[str]], id="typing-list"),
    pytest.param(azf.Out[list[str]], id="builtin-list"),
])
def test_explicit_return_rejects_out(implementation, annotation):
    with pytest.raises(
            implementation.functions.FunctionLoadError,
            match="return annotation should not be azure.functions.Out"):
        explicit_return(implementation, annotation)


class Text(str):
    pass


class Bytes(bytes):
    pass


class ByteArray(bytearray):
    pass


@pytest.mark.parametrize("annotation,input_ok,output_ok", [
    (str, True, True),
    (bytes, True, True),
    (bytearray, False, True),
    (Text, True, True),
    (Bytes, True, True),
    (ByteArray, False, True),
    (int, False, False),
])
def test_generic_binding_preserves_class_support(
        implementation, annotation, input_ok, output_ok):
    assert (
        implementation.generic.check_input_type_annotation(annotation)
        is input_ok
    )
    assert (
        implementation.generic.check_output_type_annotation(annotation)
        is output_ok
    )


NONCLASS = UNSUPPORTED + [
    pytest.param(typing.List[str], id="typing-list"),
    pytest.param(list[str], id="builtin-list"),
    pytest.param(collections.abc.Sequence[str], id="abc-sequence"),
    # GenericAlias instances could pass isinstance(..., type) on older Python.
    pytest.param(GenericAlias(str, (int,)), id="str-generic-alias"),
    pytest.param(None, id="none"),
    pytest.param(42, id="integer-instance"),
]


@pytest.mark.parametrize("annotation", NONCLASS)
def test_generic_binding_rejects_nonclass_without_typeerror(
        implementation, annotation):
    assert (
        implementation.generic.check_input_type_annotation(annotation)
        is False
    )
    assert (
        implementation.generic.check_output_type_annotation(annotation)
        is False
    )


@pytest.mark.parametrize("annotation", NONCLASS)
@pytest.mark.parametrize("binding_type,direction", [
    pytest.param("httpTrigger", "in", id="http-trigger-input"),
    pytest.param("http", "out", id="http-output"),
])
def test_http_parameter_rejects_nonclass_with_load_error(
        implementation, annotation, binding_type, direction):
    if direction == "out":
        annotation = GenericAlias(azf.Out, (annotation,))
    # Require the public load error, not a leaked converter TypeError or
    # AttributeError. Expected rejection does not depend on production helpers.
    with pytest.raises(implementation.functions.FunctionLoadError):
        validate_parameter(
            implementation, annotation,
            direction=direction, binding_type=binding_type,
        )


@pytest.mark.parametrize("annotation", NONCLASS)
def test_http_return_rejects_nonclass_with_load_error(
        implementation, annotation):
    with pytest.raises(implementation.functions.FunctionLoadError):
        explicit_return(implementation, annotation, binding_type="http")


@pytest.mark.parametrize("is_out", [False, True], ids=["input", "out"])
def test_unknown_binding_generic_alias_raises_load_error(
        implementation, is_out):
    annotation = azf.Out[list[str]] if is_out else list[str]
    with pytest.raises(
            implementation.functions.FunctionLoadError, match="does not match"):
        validate_parameter(
            implementation, annotation,
            direction="out" if is_out else "in",
            binding_type="unknownBinding",
        )
