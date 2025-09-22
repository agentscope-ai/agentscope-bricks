# -*- coding: utf-8 -*-
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, Callable, Tuple, Type

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.datastructures import QueryParams
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from uvicorn.main import run

from agentscope_bricks.utils.schemas.modelstudio_llm import RequestType
from agentscope_bricks.utils.schemas.oai_llm import (
    create_error_response,
    create_success_result,
)
import inspect

"""
TODO:
1. support multiple endpoint register
2. support local and remote on dashscope
2.1 request and response for local and dashscope
2.2 header specific
3. error handler for bad request

"""


# make sure async function can be used
async def run_as_async(func: Callable, app: FastAPI, **kwargs: Any) -> None:
    kwargs["app"] = app
    if inspect.iscoroutinefunction(func):
        await func(**kwargs)
    else:
        func(**kwargs)


class FastApiServer:
    """FastAPI server wrapper for handling HTTP requests with streaming
    responses.
    """

    def __init__(
        self,
        func: Callable,
        endpoint_path: str,
        request_model: Type[RequestType] = None,
        response_type: str = "sse",
        **kwargs: Any,
    ) -> None:
        """Initialize the FastAPI server.

        Args:
            func (Callable): The function to handle requests.
            endpoint_path (str): The API endpoint path.
            request_model (Type[RequestType], optional): The request model
                            type. Defaults to None.
            response_type (str): The response type ('sse', 'json', 'text').
                            Defaults to "sse".
            **kwargs (Any): Additional keyword arguments.
        """

        # Add before start and after finish lifespan
        before_start, after_finish = None, None
        if kwargs.get("before_start"):
            before_start = kwargs.pop("before_start")
        if kwargs.get("after_finish"):
            after_finish = kwargs.pop("after_finish")
        if before_start and not callable(before_start):
            raise TypeError("before_start must be a callable")
        if after_finish and not callable(after_finish):
            raise TypeError("after_finish must be a callable")

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> Any:
            """Manage the application lifespan.

            Args:
                app (FastAPI): The FastAPI application instance.

            Yields:
                Any: Control during application lifetime.
            """
            if before_start:
                await run_as_async(before_start, app, **kwargs)
            yield
            if after_finish:
                await run_as_async(after_finish, app, **kwargs)

        self.func = func
        self.request_model = request_model
        self.endpoint_path = endpoint_path
        self.response_type = response_type  # 可选值: 'sse', 'json', 'text'
        self.app = FastAPI(lifespan=lifespan)
        self._add_middleware()
        self._add_router()
        self._add_health()

    def _add_health(self) -> None:
        """Add health check endpoints to the FastAPI application."""

        @self.app.get("/readiness")
        async def readiness() -> str:
            """Check if the application is ready to serve requests.

            Returns:
                str: Success message if ready.

            Raises:
                HTTPException: If the application is not ready.
            """
            if getattr(self.app.state, "is_ready", True):
                return "success"
            raise HTTPException(
                status_code=500,
                detail="Application is not ready",
            )

        @self.app.get("/liveness")
        async def liveness() -> str:
            """Check if the application is alive and healthy.

            Returns:
                str: Success message if healthy.

            Raises:
                HTTPException: If the application is not healthy.
            """
            if getattr(self.app.state, "is_healthy", True):
                return "success"
            raise HTTPException(
                status_code=500,
                detail="Application is not healthy",
            )

    def _add_middleware(self) -> None:
        """Add middleware to the FastAPI application."""

        @self.app.middleware("http")
        async def modelstudio_custom_router(
            request: Request,
            call_next: Callable,
        ) -> Response:
            """Custom middleware for request processing.

            Args:
                request (Request): The incoming HTTP request.
                call_next (Callable): The next middleware or route handler.

            Returns:
                Response: The HTTP response.
            """
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
        """Add the main router endpoint to the FastAPI application."""

        async def _get_request_info(
            request: Request,
        ) -> Tuple[QueryParams, RequestType]:
            """Extract request information from the HTTP request.

            Args:
                request (Request): The incoming HTTP request.

            Returns:
                Tuple[QueryParams, RequestType]: Query parameters and parsed
                request body.
            """
            body = await request.body()
            request_body = json.loads(body.decode("utf-8")) if body else {}
            request_body_obj = self.request_model.model_validate(request_body)

            query_params = request.query_params
            return query_params, request_body_obj

        def _get_request_id(request_body_obj: RequestType) -> str:
            """Extract or generate a request ID from the request body.

            Args:
                request_body_obj (RequestType): The parsed request body object.

            Returns:
                str: The request ID.
            """
            request_id = str(uuid.uuid4())
            return request_id

        @self.app.post(self.endpoint_path)
        async def main(request: Request) -> StreamingResponse:
            """Main endpoint handler for processing requests.

            Args:
                request (Request): The incoming HTTP request.

            Returns:
                StreamingResponse: The streaming HTTP response.
            """
            query_params, request_body_obj = await _get_request_info(
                request=request,
            )
            request_id = _get_request_id(request_body_obj)

            generator = self.func(request=request_body_obj)

            async def stream_generator() -> Any:
                """Generate streaming response data.

                Yields:
                    Any: Formatted response data for streaming.
                """
                try:
                    async for output in generator:
                        yield f"data: {create_success_result(request_id=request_id, output=output)}\n\n"  # noqa E501
                except Exception as e:
                    yield (
                        f"data: "
                        f"{create_error_response(request_id=request_id, error=e)}\n\n"  # noqa E501
                    )  # noqa E501

            media_type = {
                "sse": "text/event-stream",
                "json": "application/x-ndjson",
                "text": "text/plain",
            }.get(self.response_type, "text/event-stream")

            return StreamingResponse(
                stream_generator(),
                media_type=media_type,
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the FastAPI server.

        Args:
            *args (Any): Positional arguments to pass to uvicorn.run.
            **kwargs (Any): Keyword arguments to pass to uvicorn.run.
        """
        run(app=self.app, **kwargs)
