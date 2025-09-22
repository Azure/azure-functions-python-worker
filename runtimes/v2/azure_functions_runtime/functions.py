# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import inspect
import operator
import pathlib
import typing
import uuid

from .logging import logger

from .bindings.meta import (has_implicit_output,
                            check_deferred_bindings_enabled,
                            check_output_type_annotation,
                            check_input_type_annotation,
                            validate_settlement_param)
from .utils.constants import HTTP_TRIGGER
from .utils.typing_inspect import is_generic_type, get_origin, get_args  # type: ignore


class ParamTypeInfo(typing.NamedTuple):
    binding_name: str
    pytype: typing.Optional[type]
    deferred_bindings_enabled: typing.Optional[bool] = False


class FunctionInfo(typing.NamedTuple):
    func: typing.Callable

    name: str
    directory: str
    function_id: str
    requires_context: bool
    is_async: bool
    has_return: bool
    is_http_func: bool
    deferred_bindings_enabled: bool
    settlement_client_arg: typing.Optional[str]

    input_types: typing.Mapping[str, ParamTypeInfo]
    output_types: typing.Mapping[str, ParamTypeInfo]
    return_type: typing.Optional[typing.Union[str, ParamTypeInfo]]

    trigger_metadata: typing.Optional[typing.Dict[str, typing.Any]]


class FunctionLoadError(RuntimeError):

    def __init__(self, function_name: str, msg: str) -> None:
        super().__init__(
            "cannot load the " + function_name + " function: " + msg)


class Registry:
    _functions: typing.MutableMapping[str, FunctionInfo]
    _deferred_bindings_enabled: bool = False

    def __init__(self) -> None:
        self._functions = {}

    def get_function(self, function_id: str) -> typing.Union[FunctionInfo, None]:
        if function_id in self._functions:
            return self._functions[function_id]

        return None

    def deferred_bindings_enabled(self) -> bool:
        return self._deferred_bindings_enabled

    @staticmethod
    def get_explicit_and_implicit_return(binding_name: str,
                                         binding,
                                         explicit_return: bool,
                                         implicit_return: bool,
                                         bound_params: dict) -> \
            typing.Tuple[bool, bool]:
        if binding_name == '$return':
            explicit_return = True
        elif has_implicit_output(binding.type):
            implicit_return = True
            bound_params[binding_name] = binding
        else:
            bound_params[binding_name] = binding
        return explicit_return, implicit_return

    @staticmethod
    def get_return_binding(binding_name: str,
                           binding_type: str,
                           return_binding_name: str,
                           explicit_return_val_set: bool) \
            -> typing.Tuple[str, bool]:
        # prioritize explicit return value
        if explicit_return_val_set:
            return return_binding_name, explicit_return_val_set
        if binding_name == "$return":
            return_binding_name = binding_type
            assert return_binding_name is not None
            explicit_return_val_set = True
        elif has_implicit_output(binding_type):
            return_binding_name = binding_type

        return return_binding_name, explicit_return_val_set

    @staticmethod
    def validate_binding_direction(binding_name: str,
                                   binding_direction: str,
                                   func_name: str,
                                   protos):
        if binding_direction == protos.BindingInfo.inout:
            raise FunctionLoadError(
                func_name,
                '"inout" bindings are not supported')

        if binding_name == '$return' and \
                binding_direction != protos.BindingInfo.out:
            raise FunctionLoadError(
                func_name,
                '"$return" binding must have direction set to "out"')

    @staticmethod
    def is_context_required(params, bound_params: dict,
                            annotations: dict,
                            func_name: str) -> bool:
        requires_context = False
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
                        'type azure.functions.Context, got "' + repr(ctx_anno) + '"')
        return requires_context

    @staticmethod
    def validate_function_params(params: dict, bound_params: dict,
                                 annotations: dict, func_name: str,
                                 protos):
        logger.debug("Params: %s, BoundParams: %s, Annotations: %s, FuncName: %s",
                     params, bound_params, annotations, func_name)
        settlement_client_arg = None
        if set(params) - set(bound_params):
            # Check for settlement client support for the missing parameters
            settlement_client_arg = validate_settlement_param(
                params, bound_params, annotations)
            if settlement_client_arg is not None:
                params.pop(settlement_client_arg)
            else:
                # Not supported by settlement client, raise error for missing parameters
                raise FunctionLoadError(
                    func_name,
                    'the following parameters are declared in Python '
                    'but not in the function definition (function.json or '
                    f'function decorators):  {set(params) - set(bound_params)!r}')

        if set(bound_params) - set(params):
            raise FunctionLoadError(
                func_name,
                'Extra parameters in binding definition — the following parameters '
                'are declared as bindings but are not '
                'present in Python: ' + repr(set(params) - set(bound_params)))

        input_types: typing.Dict[str, ParamTypeInfo] = {}
        output_types: typing.Dict[str, ParamTypeInfo] = {}
        fx_deferred_bindings_enabled = False

        for param in params.values():
            binding = bound_params[param.name]
            logger.debug("Param %s, binding: %s", param, binding)

            param_has_anno = param.name in annotations
            param_anno = annotations.get(param.name)
            logger.debug("Param_has_anno %s, param_anno: %s",
                         param_has_anno, param_anno)

            # Check if deferred bindings is enabled
            fx_deferred_bindings_enabled, is_deferred_binding = (
                check_deferred_bindings_enabled(
                    param_anno,
                    fx_deferred_bindings_enabled))

            if param_has_anno:
                if is_generic_type(param_anno):
                    param_anno_origin = get_origin(param_anno)
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

            is_binding_out = binding.direction == protos.BindingInfo.out

            if is_param_out:
                param_anno_args = get_args(param_anno)
                if len(param_anno_args) != 1:
                    raise FunctionLoadError(
                        func_name,
                        'binding ' + param.name
                        + ' has invalid Out annotation ' + repr(param_anno))
                param_py_type = param_anno_args[0]

                # typing_inspect.get_args() returns a flat list,
                # so if the annotation was func.Out[typing.List[foo]],
                # we need to reconstruct it.
                if (isinstance(param_py_type, tuple)
                        and is_generic_type(param_py_type[0])):
                    param_py_type = operator.getitem(
                        param_py_type[0], *param_py_type[1:])
            else:
                param_py_type = param_anno

            logger.debug("Param_py_type %s", param_py_type)

            if (param_has_anno and not isinstance(param_py_type, type)
                    and not is_generic_type(param_py_type)):
                raise FunctionLoadError(
                    func_name,
                    'binding ' + param.name
                    + ' has invalid non-type annotation ' + repr(param_anno))

            if is_binding_out and param_has_anno and not is_param_out:
                raise FunctionLoadError(
                    func_name,
                    'binding ' + param.name + ' is declared to have the "out" '
                    'direction, but its annotation in Python is not '
                    'a subclass of azure.functions.Out')

            if not is_binding_out and is_param_out:
                raise FunctionLoadError(
                    func_name,
                    'binding ' + param.name + ' is declared to have the "in" '
                    'direction in the binding decorator, but its annotation '
                    'is azure.functions.Out in Python')

            if param_has_anno and param_py_type in (str, bytes) and (
                    not has_implicit_output(binding.type)):
                param_bind_type = 'generic'
            else:
                param_bind_type = binding.type

            logger.debug("param_bind_type %s", param_bind_type)

            if param_has_anno:
                if is_param_out:
                    checks_out = check_output_type_annotation(
                        param_bind_type, param_py_type)
                else:
                    checks_out = check_input_type_annotation(
                        param_bind_type, param_py_type, is_deferred_binding)

                logger.debug("checks_out: %s",
                             checks_out)

                if not checks_out:
                    if binding.data_type is not protos.BindingInfo.undefined:
                        raise FunctionLoadError(
                            func_name,
                            'binding type "' + repr(param.name)
                            + '" and dataType "' + binding.type + '" in '
                            'the binding decorator do not match the corresponding '
                            'function parameter\'s Python type '
                            'annotation ' + param_py_type.__name__)
                    else:
                        raise FunctionLoadError(
                            func_name,
                            'type of ' + param.name + ' binding in the binding '
                            'decorator "' + binding.type + '" does not match its '
                            'Python annotation "' + param_py_type.__name__ + '"')

            param_type_info = ParamTypeInfo(param_bind_type,
                                            param_py_type,
                                            is_deferred_binding)
            if is_binding_out:
                output_types[param.name] = param_type_info
            else:
                input_types[param.name] = param_type_info
        return (input_types, output_types, fx_deferred_bindings_enabled,
                settlement_client_arg)

    @staticmethod
    def get_function_return_type(annotations: dict, has_explicit_return: bool,
                                 has_implicit_return: bool, binding_name: str,
                                 func_name: str):
        return_pytype = None
        if has_explicit_return and 'return' in annotations:
            return_anno = annotations.get('return')
            if is_generic_type(
                    return_anno) and get_origin(
                    return_anno) is not None and get_origin(
                    return_anno).__name__ == 'Out':
                raise FunctionLoadError(
                    func_name,
                    'return annotation should not be azure.functions.Out')

            return_pytype = return_anno
            if not isinstance(return_pytype, type):
                raise FunctionLoadError(
                    func_name,
                    'has invalid non-type return '
                    'annotation ' + repr(return_pytype))

            if return_pytype is (str, bytes):
                binding_name = 'generic'

            if not check_output_type_annotation(
                    binding_name, return_pytype):
                raise FunctionLoadError(
                    func_name,
                    'Python return annotation "' + return_pytype.__name__
                    + '" does not match binding type "' + binding_name + '"')

        if has_implicit_return and 'return' in annotations:
            return_pytype = annotations.get('return')

        return_type = None
        if has_explicit_return or has_implicit_return:
            return_type = ParamTypeInfo(binding_name, return_pytype)

        return return_type

    def add_func_to_registry_and_return_funcinfo(
            self, function,
            function_name: str,
            function_id: str,
            directory: str,
            requires_context: bool,
            has_explicit_return: bool,
            has_implicit_return: bool,
            deferred_bindings_enabled: bool,
            settlement_client_arg: typing.Optional[str],
            input_types: typing.Dict[str, ParamTypeInfo],
            output_types: typing.Dict[str, ParamTypeInfo],
            return_type: str):

        http_trigger_param_name = self._get_http_trigger_param_name(input_types)

        trigger_metadata = None
        is_http_func = False
        if http_trigger_param_name is not None:
            trigger_metadata = {
                "type": HTTP_TRIGGER,
                "param_name": http_trigger_param_name
            }
            is_http_func = True

        function_info = FunctionInfo(
            func=function,
            name=function_name,
            directory=directory,
            function_id=function_id,
            requires_context=requires_context,
            is_async=inspect.iscoroutinefunction(function),
            has_return=has_explicit_return or has_implicit_return,
            is_http_func=is_http_func,
            deferred_bindings_enabled=deferred_bindings_enabled,
            settlement_client_arg=settlement_client_arg,
            input_types=input_types,
            output_types=output_types,
            return_type=return_type,
            trigger_metadata=trigger_metadata)

        self._functions[function_id] = function_info

        if not self._deferred_bindings_enabled:
            self._deferred_bindings_enabled = deferred_bindings_enabled

        return function_info

    def _get_http_trigger_param_name(self, input_types):
        http_trigger_param_name = next(
            (input_type for input_type, type_info in input_types.items()
             if type_info.binding_name == HTTP_TRIGGER),
            None
        )
        return http_trigger_param_name

    def add_indexed_function(self, function, protos):
        func = function.get_user_function()
        func_name = function.get_function_name()
        function_id = str(uuid.uuid5(namespace=uuid.NAMESPACE_OID,
                                     name=func_name))
        return_binding_name: typing.Optional[str] = None
        explicit_return_val_set = False
        has_explicit_return = False
        has_implicit_return = False

        sig = inspect.signature(func)
        params = dict(sig.parameters)
        annotations = typing.get_type_hints(func)
        func_dir = str(pathlib.Path(inspect.getfile(func)).parent)

        bound_params = {}
        for binding in function.get_bindings():
            self.validate_binding_direction(binding.name,
                                            binding.direction,
                                            func_name, protos)

            has_explicit_return, has_implicit_return = \
                self.get_explicit_and_implicit_return(
                    binding.name, binding, has_explicit_return,
                    has_implicit_return, bound_params)

            return_binding_name, explicit_return_val_set = \
                self.get_return_binding(binding.name,
                                        binding.type,
                                        return_binding_name,
                                        explicit_return_val_set)

        requires_context = self.is_context_required(params, bound_params,
                                                    annotations,
                                                    func_name)

        (input_types, output_types,
         deferred_bindings_enabled,
         settlement_client_arg) = self.validate_function_params(
            params,
            bound_params,
            annotations,
            func_name,
            protos)

        return_type = \
            self.get_function_return_type(annotations,
                                          has_explicit_return,
                                          has_implicit_return,
                                          return_binding_name,
                                          func_name)

        return \
            self.add_func_to_registry_and_return_funcinfo(
                func, func_name, function_id, func_dir,
                requires_context, has_explicit_return,
                has_implicit_return, deferred_bindings_enabled,
                settlement_client_arg,
                input_types, output_types,
                return_type)
