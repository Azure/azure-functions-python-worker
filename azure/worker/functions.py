import inspect
import typing

import azure.functions as azf

from . import type_meta
from . import protos


class FunctionInfo(typing.NamedTuple):

    func: typing.Callable

    name: str
    directory: str
    requires_context: bool
    is_async: bool

    input_types: typing.Mapping[str, type_meta.Binding]
    output_types: typing.Mapping[str, type_meta.Binding]
    return_type: typing.Optional[type_meta.Binding]


class FunctionLoadError(RuntimeError):

    def __init__(self, function_name, msg):
        super().__init__(
            f'cannot load the {function_name} function: {msg}')


class Registry:

    _functions: typing.MutableMapping[str, FunctionInfo]

    def __init__(self):
        self._functions = {}

    def get(self, function_id: str):
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

        input_types = {}
        output_types = {}
        return_type = None

        requires_context = False

        bindings = {}
        for name, desc in metadata.bindings.items():
            if desc.direction == protos.BindingInfo.inout:
                raise FunctionLoadError(
                    func_name,
                    f'"inout" bindings are not supported')

            if name == '$return':
                if desc.direction != protos.BindingInfo.out:
                    raise FunctionLoadError(
                        func_name,
                        f'"$return" binding must have direction set to "out"')

                try:
                    return_type = type_meta.Binding(desc.type)
                except ValueError:
                    raise FunctionLoadError(
                        func_name,
                        f'unknown type for $return binding: "{desc.type}"')
            else:
                bindings[name] = desc

        if 'context' in params and 'context' not in bindings:
            requires_context = True
            ctx_param = params.pop('context')
            if ctx_param.annotation is not ctx_param.empty:
                if (not isinstance(ctx_param.annotation, type) or
                        not issubclass(ctx_param.annotation, azf.Context)):
                    raise FunctionLoadError(
                        func_name,
                        f'the "context" parameter is expected to be of '
                        f'type azure.functions.Context, got '
                        f'{ctx_param.annotation!r}')

        if set(params) - set(bindings):
            raise FunctionLoadError(
                func_name,
                f'the following parameters are declared in Python but '
                f'not in function.json: {set(params) - set(bindings)!r}')

        if set(bindings) - set(params):
            raise FunctionLoadError(
                func_name,
                f'the following parameters are declared in function.json but '
                f'not in Python: {set(bindings) - set(params)!r}')

        for param in params.values():
            desc = bindings[param.name]

            param_has_anno = param.annotation is not param.empty
            if param_has_anno and not isinstance(param.annotation, type):
                raise FunctionLoadError(
                    func_name,
                    f'binding {param.name} has invalid non-type annotation '
                    f'{param.annotation!r}')

            is_param_out = (param_has_anno and
                            issubclass(param.annotation, azf.Out))
            is_binding_out = desc.direction == protos.BindingInfo.out

            if is_binding_out and param_has_anno and not is_param_out:
                raise FunctionLoadError(
                    func_name,
                    f'binding {param.name} is declared to have the "out" '
                    f'direction, but its annotation in Python is not '
                    f'a subclass of azure.functions.Out')

            if not is_binding_out and is_param_out:
                raise FunctionLoadError(
                    func_name,
                    f'binding {param.name} is declared to have the "in" '
                    f'direction in function.json, but its annotation '
                    f'is azure.functions.Out in Python')

            try:
                param_bind_type = type_meta.Binding(desc.type)
            except ValueError:
                raise FunctionLoadError(
                    func_name,
                    f'unknown type for {param.name} binding: "{desc.type}"')

            if is_binding_out:
                output_types[param.name] = param_bind_type
            else:
                input_types[param.name] = param_bind_type

            if param_has_anno:
                if is_param_out:
                    assert issubclass(param.annotation, azf.Out)
                    param_py_type = param.annotation.__args__
                    if param_py_type:
                        param_py_type = param_py_type[0]
                else:
                    param_py_type = param.annotation
                if param_py_type:
                    if not type_meta.check_bind_type_matches_py_type(
                            param_bind_type, param_py_type):
                        raise FunctionLoadError(
                            func_name,
                            f'type of {param.name} binding in function.json '
                            f'"{param_bind_type}" does not match its Python '
                            f'annotation "{param_py_type.__name__}"')

        if return_type is not None and sig.return_annotation is not sig.empty:
            ra = sig.return_annotation
            if not isinstance(ra, type):
                raise FunctionLoadError(
                    func_name,
                    f'has invalid non-type return annotation {ra!r}')

            if issubclass(ra, azf.Out):
                raise FunctionLoadError(
                    func_name,
                    f'return annotation should not be azure.functions.Out')

            if not type_meta.check_bind_type_matches_py_type(
                    return_type, ra):
                raise FunctionLoadError(
                    func_name,
                    f'Python return annotation "{ra.__name__}" does not match '
                    f'binding type "{return_type}"')

        self._functions[function_id] = FunctionInfo(
            func=func,
            name=func_name,
            directory=metadata.directory,
            input_types=input_types,
            output_types=output_types,
            requires_context=requires_context,
            is_async=inspect.iscoroutinefunction(func),
            return_type=return_type)
