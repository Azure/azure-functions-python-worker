import inspect
import typing

import azure.functions as azf

from . import rpc_types
from . import protos


class FunctionInfo(typing.NamedTuple):

    func: object

    name: str
    directory: str
    requires_context: bool
    is_async: bool

    output_types: typing.Mapping[str, rpc_types.BindType]
    return_type: typing.Optional[rpc_types.BindType]


class Registry:

    _functions: typing.Mapping[str, FunctionInfo]

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
        params = sig.parameters.copy()

        output_types = {}
        return_type = None

        requires_context = False

        bindings = {}
        for name, desc in metadata.bindings.items():
            if desc.direction == protos.BindingInfo.inout:
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'"inout" bindings are not supported')

            if name == '$return':
                if desc.direction != protos.BindingInfo.out:
                    raise RuntimeError(
                        f'cannot load the {func_name} function: '
                        f'"$return" binding must have direction set to "out"')

                try:
                    return_type = rpc_types.BindType(desc.type)
                except ValueError:
                    raise RuntimeError(
                        f'cannot load the {func_name} function: '
                        f'unknown type for $return binding: "{desc.type}"')
            else:
                bindings[name] = desc

        if 'context' in params and 'context' not in bindings:
            requires_context = True
            ctx_param = params.pop('context')
            if ctx_param.annotation is not ctx_param.empty:
                if (not isinstance(ctx_param.annotation, type) or
                        not issubclass(ctx_param.annotation, azf.Context)):
                    raise RuntimeError(
                        f'cannot load the {func_name} function: '
                        f'the "context" parameter is expected to be of '
                        f'type azure.functions.Context, got '
                        f'{ctx_param.annotation!r}')

        if set(params) - set(bindings):
            raise RuntimeError(
                f'cannot load the {func_name} function: '
                f'the following parameters are declared in Python but '
                f'not in function.json: {set(params) - set(bindings)!r}')

        if set(bindings) - set(params):
            raise RuntimeError(
                f'cannot load the {func_name} function: '
                f'the following parameters are declared in function.json but '
                f'not in Python: {set(bindings) - set(params)!r}')

        for param in params.values():
            desc = bindings[param.name]

            param_has_anno = (param.annotation is not param.empty and
                              isinstance(param.annotation, type))
            is_param_out = (param_has_anno and
                            issubclass(param.annotation, azf.Out))
            is_binding_out = desc.direction == protos.BindingInfo.out

            if is_binding_out and param_has_anno and not is_param_out:
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'binding {param.name} is declared to have the "out" '
                    f'direction, but its annotation in Python is not '
                    f'a subclass of azure.functions.Out')

            if not is_binding_out and is_param_out:
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'binding {param.name} is declared to have the "in" '
                    f'direction in function.json, but its annotation '
                    f'is azure.functions.Out in Python')

            try:
                param_bind_type = rpc_types.BindType(desc.type)
            except ValueError:
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'unknown type for {param.name} binding: "{desc.type}"')

            if is_binding_out:
                output_types[param.name] = param_bind_type

            if param_has_anno:
                if is_param_out:
                    assert issubclass(param.annotation, azf.Out)
                    param_py_type = param.annotation.__args__
                    if param_py_type:
                        param_py_type = param_py_type[0]
                else:
                    param_py_type = param.annotation
                if param_py_type:
                    if not rpc_types.check_bind_type_matches_py_type(
                            param_bind_type, param_py_type):
                        raise RuntimeError(
                            f'cannot load the {func_name} function: '
                            f'type of {param.name} binding in function.json '
                            f'"{param_bind_type}" does not match its Python '
                            f'annotation "{param_py_type.__name__}"')

        if (return_type is not None and
                sig.return_annotation is not sig.empty and
                isinstance(sig.return_annotation, type)):
            ra = sig.return_annotation
            if issubclass(ra, azf.Out):
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'return annotation should not be azure.functions.Out')
            if not rpc_types.check_bind_type_matches_py_type(return_type, ra):
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'Python return annotation "{ra.__name__}" does not match '
                    f'binding type "{return_type}"')

        self._functions[function_id] = FunctionInfo(
            func=func,
            name=func_name,
            directory=metadata.directory,
            output_types=output_types,
            requires_context=requires_context,
            is_async=inspect.iscoroutinefunction(func),
            return_type=return_type)
