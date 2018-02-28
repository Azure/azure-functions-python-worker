from azure.functions import _abc as azf_abc


class Out(azf_abc.Out):

    def __init__(self):
        self.__value = None

    def set(self, val):
        self.__value = val

    def get(self):
        return self.__value
