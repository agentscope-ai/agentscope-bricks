# -*- coding: utf-8 -*-
# pylint:disable=no-untyped-def
from typing import AsyncGenerator

from agentscope_bricks.models.llm import BaseLLM
from agentscope_bricks.utils.schemas.modelstudio_llm import (
    ModelstudioChatRequest,
    ModelstudioParameters,
)
from agentscope_bricks.utils.server_utils.fastapi_server import FastApiServer


async def general_arun(request: ModelstudioChatRequest) -> AsyncGenerator[
    dict,
    None,
]:
    """Test arun method"""
    llm = BaseLLM()
    parameters = ModelstudioParameters(
        **request.model_dump(exclude_unset=True),
    )
    try:
        async for chunk in llm.astream(
            model=request.model,
            messages=request.messages,
            parameters=parameters,
        ):
            yield chunk.model_dump_json(exclude_none=True)
    except Exception as e:
        import traceback

        print(f"error {e} with traceback {traceback.format_exc()}")


server = FastApiServer(
    func=general_arun,
    endpoint_path="/api/v1/chat/completions",
    request_model=ModelstudioChatRequest,
)

if __name__ == "__main__":
    server.run()

# query the service with
"""
curl --location 'http://127.0.0.1:8000/api/v1/chat/completions' \
--header 'Content-Type: application/json' \
--data '{
    "model": "qwen-max",
    "messages":[{"role": "user", "content":"今天天气如何"}]
}'
"""
