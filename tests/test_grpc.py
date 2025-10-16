"""РўРµСЃС‚С‹ gRPC-СЃРµСЂРІРёСЃР°."""

import grpc

from grpc_server import create_grpc_server
from proto import user_pb2, user_pb2_grpc


def test_get_user(admin_user, app):
    """РџРѕР»СѓС‡РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ С‡РµСЂРµР· gRPC."""
    server = create_grpc_server()
    port = server.add_insecure_port("localhost:0")
    server.start()
    try:
        with grpc.insecure_channel(f"localhost:{port}") as channel:
            stub = user_pb2_grpc.UserServiceStub(channel)
            resp = stub.GetUser(user_pb2.GetUserRequest(id=admin_user.id))
            assert resp.id == admin_user.id
            assert resp.username == admin_user.username
            assert resp.role == admin_user.role
    finally:
        server.stop(0)
