"""gRPC-сервер для доступа к данным CRM."""

from concurrent import futures

import grpc

from app import app as flask_app
from models import Request, User
from proto import request_pb2, request_pb2_grpc, user_pb2, user_pb2_grpc


class UserService(user_pb2_grpc.UserServiceServicer):
    """Сервис работы с пользователями."""

    def __init__(self, app):
        self.app = app

    def GetUser(
        self, request: user_pb2.GetUserRequest, context: grpc.ServicerContext
    ) -> user_pb2.User:
        """Получить пользователя по идентификатору."""
        with self.app.app_context():
            user = User.query.get(request.id)
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Пользователь не найден")
            return user_pb2.User(id=user.id, username=user.username, role=user.role)


class RequestService(request_pb2_grpc.RequestServiceServicer):
    """Сервис работы с заявками."""

    def __init__(self, app):
        self.app = app

    def GetRequest(
        self, request: request_pb2.GetRequestRequest, context: grpc.ServicerContext
    ) -> request_pb2.Request:
        """Получить заявку по идентификатору."""
        with self.app.app_context():
            req = Request.query.get(request.id)
            if req is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Заявка не найдена")
            return request_pb2.Request(
                id=req.id, object_id=req.object_id, status=req.status
            )


def create_grpc_server() -> grpc.Server:
    """Создать и настроить gRPC-сервер."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserService(flask_app), server)
    request_pb2_grpc.add_RequestServiceServicer_to_server(
        RequestService(flask_app), server
    )
    return server


if __name__ == "__main__":
    srv = create_grpc_server()
    srv.add_insecure_port("[::]:50051")
    srv.start()
    srv.wait_for_termination()
