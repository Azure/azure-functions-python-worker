from azure.functions import _abc as azf_abc


class Context(azf_abc.Context):

    def __init__(self, func_name: str, func_dir: str,
                 invocation_id: str) -> None:
        self.__func_name = func_name
        self.__func_dir = func_dir
        self.__invocation_id = invocation_id

    @property
    def invocation_id(self) -> str:
        return self.__invocation_id

    @property
    def function_name(self) -> str:
        return self.__func_name

    @property
    def function_directory(self) -> str:
        return self.__func_dir
