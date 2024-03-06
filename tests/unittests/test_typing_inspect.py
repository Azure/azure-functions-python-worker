# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# Imported from https://github.com/ilevkivskyi/typing_inspect/blob/168fa6f7c5c55f720ce6282727211cf4cf6368f6/test_typing_inspect.py
# Author: Ivan Levkivskyi
# License: MIT

from azure_functions_worker._thirdparty.typing_inspect import (
    is_generic_type, is_callable_type, is_tuple_type, is_union_type,
    is_typevar, is_classvar, get_origin, get_parameters, get_last_args, get_args,
    get_generic_type, get_generic_bases, get_last_origin, )
from unittest import TestCase, main, skipIf
from typing import (
    Union, ClassVar, Callable, Optional, TypeVar, Sequence, Mapping,
    MutableMapping, Iterable, Generic, List, Any, Dict, Tuple, NamedTuple,
)


class IsUtilityTestCase(TestCase):
    def sample_test(self, fun, samples, nonsamples):
        for s in samples:
            self.assertTrue(fun(s), f"{s} type expected in {samples}")
        for s in nonsamples:
            self.assertFalse(fun(s), f"{s} type expected in {nonsamples}")

    def test_generic(self):
        T = TypeVar('T')
        samples = [Generic, Generic[T], Iterable[int], Mapping,
                   MutableMapping[T, List[int]], Sequence[Union[str, bytes]]]
        nonsamples = [int, Union[int, str], Union[int, T], ClassVar[List[int]],
                      Callable[..., T], ClassVar, Optional, bytes, list]
        self.sample_test(is_generic_type, samples, nonsamples)

    def test_callable(self):
        samples = [Callable, Callable[..., int],
                   Callable[[int, int], Iterable[str]]]
        nonsamples = [int, type, 42, [], List[int],
                      Union[callable, Callable[..., int]]]
        self.sample_test(is_callable_type, samples, nonsamples)
        class MyClass(Callable[[int], int]):
            pass
        self.assertTrue(is_callable_type(MyClass))

    def test_tuple(self):
        samples = [Tuple, Tuple[str, int], Tuple[Iterable, ...]]
        nonsamples = [int, tuple, 42, List[int], NamedTuple('N', [('x', int)])]
        self.sample_test(is_tuple_type, samples, nonsamples)
        class MyClass(Tuple[str, int]):
            pass
        self.assertTrue(is_tuple_type(MyClass))

    def test_union(self):
        T = TypeVar('T')
        S = TypeVar('S')
        samples = [Union, Union[T, int], Union[int, Union[T, S]]]
        nonsamples = [int, Union[int, int], [], Iterable[Any]]
        self.sample_test(is_union_type, samples, nonsamples)

    def test_typevar(self):
        T = TypeVar('T')
        S_co = TypeVar('S_co', covariant=True)
        samples = [T, S_co]
        nonsamples = [int, Union[T, int], Union[T, S_co], type, ClassVar[int]]
        self.sample_test(is_typevar, samples, nonsamples)

    def test_classvar(self):
        T = TypeVar('T')
        samples = [ClassVar, ClassVar[int], ClassVar[List[T]]]
        nonsamples = [int, 42, Iterable, List[int], type, T]
        self.sample_test(is_classvar, samples, nonsamples)


class GetUtilityTestCase(TestCase):

    def test_origin(self):
        T = TypeVar('T')
        self.assertEqual(get_origin(int), None)
        self.assertEqual(get_origin(ClassVar[int]), None)
        self.assertEqual(get_origin(Generic), Generic)
        self.assertEqual(get_origin(Generic[T]), Generic)
        self.assertEqual(get_origin(List[Tuple[T, T]][int]), list)

    def test_parameters(self):
        T = TypeVar('T')
        S_co = TypeVar('S_co', covariant=True)
        U = TypeVar('U')
        self.assertEqual(get_parameters(int), ())
        self.assertEqual(get_parameters(Generic), ())
        self.assertEqual(get_parameters(Union), ())
        self.assertEqual(get_parameters(List[int]), ())
        self.assertEqual(get_parameters(Generic[T]), (T,))
        self.assertEqual(get_parameters(Tuple[List[T], List[S_co]]), (T, S_co))
        self.assertEqual(get_parameters(Union[S_co, Tuple[T, T]][int, U]), (U,))
        self.assertEqual(get_parameters(Mapping[T, Tuple[S_co, T]]), (T, S_co))

    def test_args_evaluated(self):
        T = TypeVar('T')
        self.assertEqual(get_args(Union[int, Tuple[T, int]][str], evaluate=True),
                         (int, Tuple[str, int]))
        self.assertEqual(get_args(Dict[int, Tuple[T, T]][Optional[int]], evaluate=True),
                         (int, Tuple[Optional[int], Optional[int]]))
        self.assertEqual(get_args(Callable[[], T][int], evaluate=True), ([], int,))

    def test_generic_type(self):
        T = TypeVar('T')
        class Node(Generic[T]): pass
        self.assertIs(get_generic_type(Node()), Node)
        self.assertIs(get_generic_type(Node[int]()), Node[int])
        self.assertIs(get_generic_type(Node[T]()), Node[T],)
        self.assertIs(get_generic_type(1), int)

    def test_generic_bases(self):
        class MyClass(List[int], Mapping[str, List[int]]): pass
        self.assertEqual(get_generic_bases(MyClass),
                         (List[int], Mapping[str, List[int]]))
        self.assertEqual(get_generic_bases(int), ())


if __name__ == '__main__':
    main()
