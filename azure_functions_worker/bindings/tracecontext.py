# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.


class TraceContext:

    def __init__(self, trace_parent: str,
                 trace_state: str, attributes: dict) -> None:
        self.__trace_parent = trace_parent
        self.__trace_state = trace_state
        self.__attributes = attributes

    @property
    def Tracestate(self) -> str:
        return self.__trace_state

    @property
    def Traceparent(self) -> str:
        return self.__trace_parent

    @property
    def Attributes(self) -> str:
        return self.__attributes
