import collections.abc
import json
import typing

from azure.functions import _cosmosdb as cdb

from . import meta
from .. import protos


class CosmosDBConverter(meta.InConverter, meta.OutConverter,
                        binding='cosmosDB'):

    @classmethod
    def check_input_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, cdb.DocumentList)

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (cdb.DocumentList, cdb.Document))

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> cdb.DocumentList:
        data_type = data.WhichOneof('data')

        if data_type == 'string':
            body = data.string

        elif data_type == 'bytes':
            body = data.bytes.decode('utf-8')

        elif data_type == 'json':
            body = data.json

        else:
            raise NotImplementedError(
                f'unsupported queue payload type: {data_type}')

        documents = json.loads(body)
        if not isinstance(documents, list):
            documents = [documents]

        return cdb.DocumentList(
            cdb.Document.from_dict(doc) for doc in documents)

    @classmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        if isinstance(obj, cdb.Document):
            data = cdb.DocumentList([obj])

        elif isinstance(obj, cdb.DocumentList):
            data = obj

        elif isinstance(obj, collections.abc.Iterable):
            data = cdb.DocumentList()

            for doc in obj:
                if not isinstance(doc, cdb.Document):
                    raise NotImplementedError
                else:
                    data.append(doc)

        else:
            raise NotImplementedError

        return protos.TypedData(
            json=json.dumps([dict(d) for d in data])
        )


class CosmosDBTriggerConverter(CosmosDBConverter,
                               binding='cosmosDBTrigger', trigger=True):
    pass
