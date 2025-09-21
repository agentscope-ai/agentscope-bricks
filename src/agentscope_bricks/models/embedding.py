# -*- coding: utf-8 -*-
import json
import os
from typing import (
    Any,
    AsyncGenerator,
    Generic,
    Optional,
    TypeVar,
    Union,
    List,
)

import dashscope
from openai import OpenAI, AsyncOpenAI
from openai.types import CreateEmbeddingResponse
from typing_extensions import Literal, TypeAlias, Iterable

from agentscope_bricks.base import AIModel
from agentscope_bricks.base.model import ModelType
from agentscope_bricks.constants import BASE_URL
from agentscope_bricks.utils.schemas.embedding import EmbeddingResponse

TextEmbeddingModel: TypeAlias = Literal[
    "text-embedding-v1",
    "text-embedding-v2",
    "text-embedding-v3",
    "text-embedding-v4",
]
MultimodalEmbeddingModel: TypeAlias = Literal["multimodal-embedding-v1"]
EmbeddingReturnT = TypeVar(
    "EmbeddingReturnT",
    bound=Union[
        EmbeddingResponse,
        CreateEmbeddingResponse,
        AsyncGenerator[EmbeddingResponse, CreateEmbeddingResponse],
    ],
    covariant=True,
)


class BaseEmbedding(AIModel, Generic[EmbeddingReturnT]):
    client: Optional[Union[OpenAI, AsyncOpenAI]] = None

    def __init__(self, model_type: ModelType, **kwargs: Any):
        super().__init__(model_type=model_type, **kwargs)
        client = kwargs.get("client", None)
        if not client:
            self.client = self.get_client(**kwargs)
        else:
            self.client = client

    def model_dump_json(self) -> str:
        """Serialize the model information to JSON string.

        Returns:
            str: JSON string containing model type and client information.
        """
        info = {"model_type": str(self.model_type), "client": str(self.client)}
        return json.dumps(info)

    @classmethod
    def get_client(
        cls,
        api_key: str = os.getenv("DASHSCOPE_API_KEY", ""),
        base_url: str = BASE_URL,
        **kwargs: Any,
    ) -> Union[OpenAI, AsyncOpenAI]:
        """Get embedding client from OpenAI compatible service.

        Args:
            api_key: API key of the OpenAI compatible service. Defaults to
                DASHSCOPE_API_KEY environment variable.
            base_url: Base URL for the OpenAI compatible service. Defaults to
                BASE_URL constant.
            **kwargs: Additional keyword arguments for client configuration.

        Returns:
            Union[OpenAI, AsyncOpenAI]: Configured OpenAI client instance.

        Raises:
            ValueError: If api_key is not provided or set in environment.
        """
        if not api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY is not set, or Other OPENAI compatible "
                "api-key is not set",
            )
        _client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return _client


class TextEmbedding(BaseEmbedding):
    def __init__(self, **kwargs: Any):
        super().__init__(model_type=ModelType.TEXT_EMBEDDING, **kwargs)

    async def arun(
        self,
        input: Union[str, List[str], Iterable[int], Iterable[Iterable[int]]],
        model: Union[str, TextEmbeddingModel],
        **kwargs: Any,
    ) -> EmbeddingReturnT:
        # update the api key if passed
        api_key = kwargs.get("api_key", None)
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)

        response = await self.client.embeddings.create(
            model=model,
            input=input,
            **kwargs,
        )
        return response


class MultimodalEmbedding(BaseEmbedding):
    def __init__(self, **kwargs: Any):
        super().__init__(model_type=ModelType.MULTIMODAL_EMBEDDING, **kwargs)

    async def arun(
        self,
        input: List[dict[str, str]],
        model: Union[str, MultimodalEmbeddingModel],
        **kwargs: Any,
    ) -> EmbeddingReturnT:
        # update the api key if passed
        api_key = kwargs.get("api_key", None)
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
        response = dashscope.MultiModalEmbedding.call(
            model=model,
            input=input,
            **kwargs,
        )
        return self._convert_response(response, model)

    def _convert_response(
        self,
        ds_response: dict,
        model: str,
    ) -> EmbeddingResponse:
        embeddings = ds_response.get("output", {}).get("embeddings", [])
        usage = ds_response.get("usage", {})
        data = [
            {
                "object": item.get("object", "embedding"),
                "index": item.get("index", -1),
                "embedding": item.get("embedding", []),
            }
            for item in embeddings
        ]

        return EmbeddingResponse(
            data=data,
            model=model,
            object="list",
            usage=usage,
        )
