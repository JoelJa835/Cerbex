from grpc_status import rpc_status
from google.rpc import code_pb2, status_pb2
status = status_pb2.Status(code=code_pb2.INTERNAL, message="Internal error")
details = rpc_status.to_status(status)
print(details)
