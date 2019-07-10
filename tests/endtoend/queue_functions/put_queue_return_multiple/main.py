import typing
import azure.functions as azf


def main(req: azf.HttpRequest, msgs: azf.Out[typing.List[str]]):
    msgs.set(['one', 'two'])
