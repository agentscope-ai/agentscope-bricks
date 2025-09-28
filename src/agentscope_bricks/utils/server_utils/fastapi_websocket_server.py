# -*- coding: utf-8 -*-
import json
import traceback
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Type, Any, Callable, TypeVar

from fastapi import FastAPI, Request, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket
from starlette.websockets import WebSocketDisconnect
from uvicorn.main import run

from agentscope_bricks.components.realtime_clients.realtime_component import (
    RealtimeState,
)
from agentscope_bricks.utils.schemas.realtime import (
    ModelstudioVoiceChatRequest as BailianVoiceChatRequest,
)
from agentscope_bricks.utils.logger_util import logger


class RealtimeService(ABC):

    ws: WebSocket
    state: RealtimeState

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.state = RealtimeState.IDLE

    @abstractmethod
    async def process_message(self, request: BailianVoiceChatRequest) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def process_data(self, data: bytes) -> None:
        raise NotImplementedError()

    async def destroy(self) -> None:
        """Clean up resources when the service is destroyed."""
        pass


RealtimeServiceT = TypeVar(
    "RealtimeServiceT",
    bound=RealtimeService,
    contravariant=True,
)


class FastApiWebsocketServer:

    def __init__(
        self,
        endpoint_path: str,
        service_class: Type[RealtimeServiceT],
        **kwargs: Any,
    ) -> None:

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> Any:
            # TODO: add lifespan before start
            yield
            # TODO: add lifespan after finish

        self.endpoint_path = endpoint_path
        self.service_class = service_class
        self.app = FastAPI(lifespan=lifespan)
        self._add_middleware()
        self._add_router()
        self._add_health()

    def _add_health(self) -> None:

        @self.app.get("/readiness")
        async def readiness() -> str:
            return "success"

        @self.app.get("/liveness")
        async def liveness() -> str:
            return "success"

    def _add_middleware(self) -> None:

        @self.app.middleware("http")
        async def bailian_custom_router(
            request: Request,
            call_next: Callable,
        ) -> Response:
            response: Response = await call_next(request)
            return response

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _add_router(self) -> None:

        async def _get_request_info(
            text_message: str,
        ) -> BailianVoiceChatRequest:
            text_json = json.loads(text_message)
            return BailianVoiceChatRequest.model_validate(text_json)

        def _get_request_id(request: BailianVoiceChatRequest) -> str:
            if request.request_id:
                request_id = request.request_id
            else:
                request_id = str(uuid.uuid4())
            return request_id

        @self.app.websocket(self.endpoint_path)
        async def main(websocket: WebSocket) -> None:

            await websocket.accept()

            try:
                service = self.service_class(websocket)

                while (
                    True
                ):  # websocket.application_state == WebSocketState.CONNECTED:
                    message = await websocket.receive()
                    try:
                        if "text" in message:
                            request = await _get_request_info(message["text"])
                            await service.process_message(request=request)
                        elif "bytes" in message:
                            await service.process_data(data=message["bytes"])
                    except Exception as e:
                        logger.info(
                            f"process failed: exception={e}, details="
                            f"{str(traceback.format_exc())}",
                        )

            except WebSocketDisconnect:
                logger.info("client disconnected")

            except Exception as e:
                logger.error(f"websocket failed: exception={e}")
                # logger.info(f"websocket failed: exception={e}, details={
                # str(traceback.format_exc())}")

            finally:
                await service.destroy()
                logger.info("session exits")

    def run(self, *args: Any, **kwargs: Any) -> None:
        run(app=self.app, **kwargs)
