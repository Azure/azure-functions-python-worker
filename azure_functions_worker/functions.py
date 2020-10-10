# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import inspect
import operator
import typing

from . import bindings
from . import protos
from ._thirdparty import typing_inspect


class ParamTypeInfo(typing.NamedTuple):

    binding_name: str
    pytype: typing.Optional[type]


class FunctionInfo(typing.NamedTuple):

    func: typing.Callable

    name: str
    directory: str
    requires_context: bool
    is_async: bool
    has_return: bool

    input_types: typing.Mapping[str, ParamTypeInfo]
    output_types: typing.Mapping[str, ParamTypeInfo]
    return_type: typing.Optional[ParamTypeInfo]


class FunctionLoadError(RuntimeError):

    def __init__(self, function_name: str, msg: str) -> None:
        super().__init__(
            f'cannot load the {function_name} function: {msg}')


class Registry:

    _functions: typing.MutableMapping[str, FunctionInfo]

    def __init__(self) -> None:
        self._functions = {}

    def get_function(self, function_id: str) -> FunctionInfo:
        try:
            return self._functions[function_id]
        except KeyError:
            raise RuntimeError(
                f'no function with function_id={function_id}') from None

    def add_function(self, function_id: str,
                     func: typing.Callable,
                     metadata: protos.RpcFunctionMetadata):
        func_name = metadata.name
        sig = inspect.signature(func)
        params = dict(sig.parameters)
        annotations = typing.get_type_hints(func)

        input_types: typing.Dict[str, ParamTypeInfo] = {}
        output_types: typing.Dict[str, ParamTypeInfo] = {}
        return_binding_name: typing.Optional[str] = None
        return_pytype: typing.Optional[type] = None

        requires_context = False
        has_explicit_return = False
        has_implicit_return = False

        bound_params = {}
        for name, desc in metadata.bindings.items():
            if desc.direction == protos.BindingInfo.inout:
                raise FunctionLoadError(
                    func_name,
                    '"inout" bindings are not supported')

            if name == '$return':
                if desc.direction != protos.BindingInfo.out:
                    raise FunctionLoadError(
                        func_name,
                        '"$return" binding must have direction set to "out"')

                has_explicit_return = True
                return_binding_name = desc.type
                assert return_binding_name is not None

            elif bindings.has_implicit_output(desc.type):
                # If the binding specify implicit output binding
                # (e.g. orchestrationTrigger, activityTrigger)
                # we should enable output even if $return is not specified
                has_implicit_return = True
                return_binding_name = desc.type
                bound_params[name] = desc
            else:
                bound_params[name] = desc

        if 'context' in params and 'context' not in bound_params:
            requires_context = True
            params.pop('context')
            if 'context' in annotations:
                ctx_anno = annotations.get('context')
                if (not isinstance(ctx_anno, type)
                        or ctx_anno.__name__ != 'Context'):
                    raise FunctionLoadError(
                        func_name,
                        'the "context" parameter is expected to be of '
                        'type azure.functions.Context, got '
                        f'{ctx_anno!r}')

        if set(params) - set(bound_params):
            raise FunctionLoadError(
                func_name,
                'the following parameters are declared in Python but '
                f'not in function.json: {set(params) - set(bound_params)!r}')

        if set(bound_params) - set(params):
            raise FunctionLoadError(
                func_name,
                f'the following parameters are declared in function.json but '
                f'not in Python: {set(bound_params) - set(params)!r}')

        for param in params.values():
            desc = bound_params[param.name]

            param_has_anno = param.name in annotations
            param_anno = annotations.get(param.name)

            if param_has_anno:
                if typing_inspect.is_generic_type(param_anno):
                    param_anno_origin = typing_inspect.get_origin(param_anno)
                    if param_anno_origin is not None:
                        is_param_out = (
                            isinstance(param_anno_origin, type)
                            and param_anno_origin.__name__ == 'Out'
                        )
                    else:
                        is_param_out = (
                            isinstance(param_anno, type)
                            and param_anno.__name__ == 'Out'
                        )
                else:
                    is_param_out = (
                        isinstance(param_anno, type)
                        and param_anno.__name__ == 'Out'
                    )
            else:
                is_param_out = False

            is_binding_out = desc.direction == protos.BindingInfo.out

            if is_param_out:
                param_anno_args = typing_inspect.get_args(param_anno)
                if len(param_anno_args) != 1:
                    raise FunctionLoadError(
                        func_name,
                        f'binding {param.name} has invalid Out annotation '
                        f'{param_anno!r}')
                param_py_type = param_anno_args[0]

                # typing_inspect.get_args() returns a flat list,
                # so if the annotation was func.Out[typing.List[foo]],
                # we need to reconstruct it.
                if (isinstance(param_py_type, tuple)
                   and typing_inspect.is_generic_type(param_py_type[0])):

                    param_py_type = operator.getitem(
                        param_py_type[0], *param_py_type[1:])
            else:
                param_py_type = param_anno

            if (param_has_anno and not isinstance(param_py_type, type)
               and not typing_inspect.is_generic_type(param_py_type)):
                raise FunctionLoadError(
                    func_name,
                    f'binding {param.name} has invalid non-type annotation '
                    f'{param_anno!r}')

            if is_binding_out and param_has_anno and not is_param_out:
                raise FunctionLoadError(
                    func_name,
                    f'binding {param.name} is declared to have the "out" '
                    'direction, but its annotation in Python is not '
                    'a subclass of azure.functions.Out')

            if not is_binding_out and is_param_out:
                raise FunctionLoadError(
                    func_name,
                    f'binding {param.name} is declared to have the "in" '
                    'direction in function.json, but its annotation '
                    'is azure.functions.Out in Python')

            if param_has_anno and param_py_type in (str, bytes) and (
                    not bindings.has_implicit_output(desc.type)):
                param_bind_type = 'generic'
            else:
                param_bind_type = desc.type

            if param_has_anno:
                if is_param_out:
                    checks_out = bindings.check_output_type_annotation(
                        param_bind_type, param_py_type)
                else:
                    checks_out = bindings.check_input_type_annotation(
                        param_bind_type, param_py_type)

                if not checks_out:
                    if desc.data_type is not protos.BindingInfo.undefined:
                        raise FunctionLoadError(
                            func_name,
                            f'{param.name!r} binding type "{desc.type}" '
                            f'and dataType "{desc.data_type}" in function.json'
                            f' do not match the corresponding function '
                            f'parameter\'s Python type '
                            f'annotation "{param_py_type.__name__}"')
                    else:
                        raise FunctionLoadError(
                            func_name,
                            f'type of {param.name} binding in function.json '
                            f'"{desc.type}" does not match its Python '
                            f'annotation "{param_py_type.__name__}"')

            param_type_info = ParamTypeInfo(param_bind_type, param_py_type)
            if is_binding_out:
                output_types[param.name] = param_type_info
            else:
                input_types[param.name] = param_type_info

        return_pytype = None
        if has_explicit_return and 'return' in annotations:
            return_anno = annotations.get('return')
            if (typing_inspect.is_generic_type(return_anno)
               and typing_inspect.get_origin(return_anno).__name__ == 'Out'):
                raise FunctionLoadError(
                    func_name,
                    'return annotation should not be azure.functions.Out')

            return_pytype = return_anno
            if not isinstance(return_pytype, type):
                raise FunctionLoadError(
                    func_name,
                    f'has invalid non-type return '
                    f'annotation {return_pytype!r}')

            if return_pytype is (str, bytes):
                return_binding_name = 'generic'

            if not bindings.check_output_type_annotation(
                    return_binding_name, return_pytype):
                raise FunctionLoadError(
                    func_name,
                    f'Python return annotation "{return_pytype.__name__}" '
                    f'does not match binding type "{return_binding_name}"')

        if has_implicit_return and 'return' in annotations:
            return_pytype = annotations.get('return')

        return_type = None
        if has_explicit_return or has_implicit_return:
            return_type = ParamTypeInfo(return_binding_name, return_pytype)

        self._functions[function_id] = FunctionInfo(
            func=func,
            name=func_name,
            directory=metadata.directory,
            requires_context=requires_context,
            is_async=inspect.iscoroutinefunction(func),
            has_return=has_explicit_return or has_implicit_return,
            input_types=input_types,
            output_types=output_types,
            return_type=return_type)
