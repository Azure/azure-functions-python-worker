# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
import grpc

from azureworker.protos import FunctionRpc_pb2 as azureworker_dot_protos_dot_FunctionRpc__pb2


class FunctionRpcStub(object):
  """Interface exported by the server.
  """

  def __init__(self, channel):
    """Constructor.

    Args:
      channel: A grpc.Channel.
    """
    self.EventStream = channel.stream_stream(
        '/FunctionRpc.FunctionRpc/EventStream',
        request_serializer=azureworker_dot_protos_dot_FunctionRpc__pb2.StreamingMessage.SerializeToString,
        response_deserializer=azureworker_dot_protos_dot_FunctionRpc__pb2.StreamingMessage.FromString,
        )


class FunctionRpcServicer(object):
  """Interface exported by the server.
  """

  def EventStream(self, request_iterator, context):
    # missing associated documentation comment in .proto file
    pass
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')


def add_FunctionRpcServicer_to_server(servicer, server):
  rpc_method_handlers = {
      'EventStream': grpc.stream_stream_rpc_method_handler(
          servicer.EventStream,
          request_deserializer=azureworker_dot_protos_dot_FunctionRpc__pb2.StreamingMessage.FromString,
          response_serializer=azureworker_dot_protos_dot_FunctionRpc__pb2.StreamingMessage.SerializeToString,
      ),
  }
  generic_handler = grpc.method_handlers_generic_handler(
      'FunctionRpc.FunctionRpc', rpc_method_handlers)
  server.add_generic_rpc_handlers((generic_handler,))
