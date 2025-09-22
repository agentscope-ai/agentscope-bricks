# -*- coding: utf-8 -*-
import json
import os
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)

import instructor
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel

from agentscope_bricks.base.model import AIModel, ModelType
from agentscope_bricks.constants import BASE_URL

from agentscope_bricks.utils.schemas.oai_llm import (
    Parameters,
    OpenAIMessage,
    UserMessage,
    ImageMessageContent,
    AssistantMessage,
    SystemMessage,
    ToolMessage,
)
from agentscope_bricks.utils.tracing_utils import TraceType
from agentscope_bricks.utils.tracing_utils.wrapper import trace

MessageT = TypeVar("MessageT", bound=OpenAIMessage, contravariant=True)
ParamsT = TypeVar("ParamsT", bound=Parameters, contravariant=True)
StructReturnT = TypeVar("StructReturnT", bound=BaseModel, contravariant=True)
LlmReturnT = TypeVar(
    "LlmReturnT",
    bound=Union[
        ChatCompletion,
        ChatCompletionChunk,
        AsyncGenerator[ChatCompletionChunk, Any],
        BaseModel,
        AsyncGenerator[BaseModel, Any],
    ],
    covariant=True,
)


class BaseLLM(AIModel, Generic[MessageT, ParamsT, StructReturnT, LlmReturnT]):
    """Base class for LLM (Language Model) implementations.

    This class provides a generic interface for different types of LLMs and
    ensures that they can be used in a consistent manner. It defines the `run`
    method with multiple overloads to support different input types and a
    generic return type.

    Attributes:
        client: Optional OpenAI or AsyncOpenAI client instance for API calls.
    """

    client: Optional[
        Union[OpenAI, AsyncOpenAI, instructor.client.Instructor]
    ] = None

    def __init__(self, **kwargs: Any):
        """Initialize the LLM with generic prompt messages and parameters.

        Args:
            **kwargs: Additional keyword arguments including:
                - client: Optional pre-configured client instance
                - Other initialization parameters passed to parent class
        """
        super().__init__(model_type=ModelType.LLM, **kwargs)
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
        api_key: Optional[str] = None,
        base_url: str = BASE_URL,
        **kwargs: Any,
    ) -> Union[OpenAI, AsyncOpenAI]:
        """Get a LLM client from OpenAI compatible service.

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
            api_key = os.getenv("DASHSCOPE_API_KEY")

        if not api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY is not set, or Other OPENAI compatible "
                "api-key is not set",
            )
        _client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return _client

    @classmethod
    def from_instructor_client(cls, **kwargs: Any) -> "BaseLLM":
        """Create a BaseLLM instance with instructor client for structured
        output.

        Args:
            **kwargs: Additional keyword arguments for client configuration.

        Returns:
            BaseLLM: Instance configured with instructor client.
        """
        _client = cls.get_client(**kwargs)
        _client = instructor.from_openai(_client)
        return cls(client=_client, **kwargs)

    async def arun(
        self,
        model: str,
        messages: Sequence[Union[MessageT, Dict]],
        parameters: Union[ParamsT, Dict] = None,
        response_model: Optional[Type[StructReturnT]] = None,
        **kwargs: Any,
    ) -> LlmReturnT:
        """Run the LLM with the given prompt messages and parameters.

        On one hand, Openai's `ChatCompletion` and `ChatCompletionChunk` are
        formal message result, on the other hand, by package `instructor`,
        structured result are supported as well, user could define a
        `response_model` which is a BaseModel instance, and the instructor
        will make sure the output is in the format of this BaseModel.

        Args:
            model: Model name to use for completion.
            messages: The prompt messages as sequence of MessageT or Dict.
            parameters: The parameters for the LLM as ParamsT or Dict.
            response_model: Optional structured output model type.
            **kwargs: Additional keyword arguments including:
                - api_key: Optional API key override
                - Other arguments passed to the completion API

        Returns:
            LlmReturnT: The completion result.

        Raises:
            ValueError: If JSON schema format is invalid when using json_schema
                response format.
        """
        # update the api key if passed
        api_key = kwargs.get("api_key", None)

        if api_key:
            # is_instructor = isinstance(self.client,
            # instructor.client.Instructor) and response_model
            self.client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
            if response_model:
                self.client = instructor.from_openai(self.client)

        # support dict message
        if isinstance(messages[0], dict):
            formatted_messages: List[OpenAIMessage] = [
                OpenAIMessage(**message) for message in messages
            ]
        else:
            formatted_messages = messages

        # support dict parameters
        if isinstance(parameters, dict):
            parameters: Parameters = Parameters(**parameters)

        extra_model_kwargs = {}

        # make sure the parameters is an openai parameters
        if parameters and type(parameters) is not Parameters:
            parameters = Parameters(
                **parameters.model_dump(exclude_none=True, exclude_unset=True),
            )
            # in some cases parameters might be []
            if parameters.tools == []:
                parameters.tools = None

        parameters = (
            parameters.model_dump(exclude_none=True, exclude_unset=True)
            if parameters
            else {}
        )

        response_format = parameters.get("response_format")
        if response_format:
            if response_format == "json_schema":
                json_schema = parameters.get("json_schema")
                if not json_schema:
                    raise ValueError(
                        "Must define JSON Schema when the response format is json_schema",  # noqa E501
                    )
                try:
                    schema = json.loads(json_schema)
                except Exception:
                    raise ValueError(
                        f"not correct json_schema format: {json_schema}",
                    )
                parameters.pop("json_schema")
                parameters["response_format"] = {
                    "type": "json_schema",
                    "json_schema": schema,
                }
            else:
                parameters["response_format"] = {"type": response_format}

        dict_messages: List[Any] = [
            self._convert_message_to_dict(m) for m in formatted_messages
        ]

        if response_model:
            # TODO: response model is used for structured output,
            #  not compatible with function calling for now
            extra_model_kwargs["response_model"] = response_model
            # todo: change from create_partial to create, double check
            response = await self.client.chat.completions.create(
                model=model,
                stream=False,
                messages=dict_messages,
                **parameters,
                **extra_model_kwargs,
            )
        else:
            response = await self.client.chat.completions.create(
                model=model,
                stream=False,
                messages=dict_messages,
                **parameters,
                **extra_model_kwargs,
            )
        return response

    @trace(trace_type=TraceType.LLM, trace_name="base_llm")
    async def astream(
        self,
        model: str,
        messages: Sequence[Union[MessageT, Dict]],
        parameters: ParamsT = None,
        response_model: Optional[Type[StructReturnT]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ChatCompletionChunk, Any]:
        """Stream LLM responses with tracing enabled.

        Args:
            model: Model name to use for completion.
            messages: The prompt messages as sequence of MessageT or Dict.
            parameters: The parameters for the LLM.
            response_model: Optional structured output model type.
            **kwargs: Additional keyword arguments passed to _astream.

        Yields:
            ChatCompletionChunk: Streaming response chunks from the LLM.
        """
        responses = await self._astream(
            model=model,
            messages=messages,
            parameters=parameters,
            response_model=response_model,
            **kwargs,
        )

        async for response in responses:
            yield response

    async def astream_unwrapped(
        self,
        model: str,
        messages: Sequence[Union[OpenAIMessage, Dict]],
        parameters: ParamsT = None,
        response_model: Optional[Type[StructReturnT]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ChatCompletionChunk, Any]:
        """Stream LLM responses without tracing wrapper.

        Args:
            model: Model name to use for completion.
            messages: The prompt messages as sequence of PromptMessage or Dict.
            parameters: The parameters for the LLM.
            response_model: Optional structured output model type.
            **kwargs: Additional keyword arguments passed to _astream.

        Yields:
            ChatCompletionChunk: Streaming response chunks from the LLM.
        """
        responses = await self._astream(
            model=model,
            messages=messages,
            parameters=parameters,
            response_model=response_model,
            **kwargs,
        )

        async for response in responses:
            yield response

    async def _astream(
        self,
        model: str,
        messages: Sequence[Union[MessageT, Dict]],
        parameters: ParamsT = None,
        response_model: Optional[Type[StructReturnT]] = None,
        **kwargs: Any,
    ) -> LlmReturnT:
        """Internal method to run streaming LLM with the given prompt
        messages and parameters.

        Args:
            model: Model name to use for completion.
            messages: The prompt messages as sequence of MessageT or Dict.
            parameters: The parameters for the LLM.
            response_model: Optional structured output model type for
                    structured output.
            **kwargs: Additional keyword arguments including:
                - api_key: Optional API key override
                - Other arguments passed to the completion API

        Returns:
            LlmReturnT: The streaming completion result.

        Raises:
            ValueError: If JSON schema format is invalid when using json_schema
                response format.
        """
        # update the api key
        api_key = kwargs.get("api_key", None)
        if api_key:
            is_instructor = isinstance(
                self.client,
                instructor.client.Instructor,
            )
            self.client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
            if is_instructor:
                self.client = instructor.from_openai(self.client)

        # support dict message
        if isinstance(messages[0], dict):
            formatted_messages: List[OpenAIMessage] = [
                OpenAIMessage(**message) for message in messages
            ]
        else:
            formatted_messages = messages

        extra_model_kwargs = {}

        # make sure the parameters is an openai parameters
        if parameters and type(parameters) is not Parameters:
            parameters = Parameters(
                **parameters.model_dump(exclude_none=True),
            )

            # in some cases parameters might be []
            if parameters.tools == []:
                parameters.tools = None

        parameters = (
            parameters.model_dump(exclude_none=True) if parameters else {}
        )
        if "stream" in parameters:
            parameters.pop("stream")
        parameters["stream_options"] = {"include_usage": True}

        response_format = parameters.get("response_format")
        if response_format:
            if response_format == "json_schema":
                json_schema = parameters.get("json_schema")
                if not json_schema:
                    raise ValueError(
                        "Must define JSON Schema when the response format is json_schema",  # noqa E501
                    )
                try:
                    schema = json.loads(json_schema)
                except Exception:
                    raise ValueError(
                        f"not correct json_schema format: {json_schema}",
                    )
                parameters.pop("json_schema")
                parameters["response_format"] = {
                    "type": "json_schema",
                    "json_schema": schema,
                }
            elif "type" not in response_format:
                parameters["response_format"] = {"type": response_format}

        dict_messages: List[Any] = [
            self._convert_message_to_dict(m) for m in formatted_messages
        ]

        if response_model:
            # TODO: response model is used for structured output,
            #  not compatible with function calling for now
            extra_model_kwargs["response_model"] = response_model
            response = self.client.chat.completions.create_partial(
                model=model,
                stream=True,
                messages=dict_messages,
                **parameters,
                **extra_model_kwargs,
            )
        else:
            response = await self.client.chat.completions.create(
                model=model,
                stream=True,
                messages=dict_messages,
                **parameters,
                **extra_model_kwargs,
            )
        return response

    @staticmethod
    def transform_response(response: Any) -> str:
        """Transform various response types to string representation.

        Args:
            response: The response object to transform. Can be string, dict,
                BaseModel, or other types.

        Returns:
            str: String representation of the response.
        """

        def dump_json_str(obj: Any) -> str:
            """Convert an object to a JSON string.

            Args:
                obj: The object to convert to JSON string.

            Returns:
                str: JSON string representation of the object.
            """
            return json.dumps(
                dump_json(obj),
                ensure_ascii=False,
                default=lambda x: str(x),
            )

        def dump_json(obj: Any) -> Any:
            """Recursively convert an object to JSON-serializable format.

            Args:
                obj: The object to convert.

            Returns:
                Any: JSON-serializable representation of the object.
            """
            if isinstance(obj, dict):
                return {k: dump_json(v) for k, v in obj.items()}
            elif isinstance(obj, (tuple, list)):
                return [dump_json(v) for v in obj]
            elif isinstance(obj, BaseModel):
                return obj.model_dump(exclude_unset=True, exclude_none=True)
            elif isinstance(obj, (AsyncGenerator, Generator, AsyncIterable)):
                return str(obj)
            else:
                return obj

        if isinstance(response, str):
            return response
        elif isinstance(response, dict):
            return json.dumps(response, ensure_ascii=False)
        elif isinstance(response, BaseModel):
            return response.model_dump_json(
                exclude_none=True,
                exclude_unset=True,
            )
        else:
            return dump_json_str(response)

    def _convert_message_to_dict(
        self,
        message: OpenAIMessage,
    ) -> Dict[str, Any]:
        """Convert OpenAIMessage to dict format for OpenAI API.

        Args:
            message: The OpenAIMessage instance to convert.

        Returns:
            Dict[str, Any]: Dictionary representation compatible with OpenAI
            API.

        Raises:
            ValueError: If message type is unknown or unsupported.
        """
        message_dict: Dict[str, Any] = {}
        if isinstance(message, UserMessage):
            if isinstance(message.content, str):
                message_dict = {"role": "user", "content": message.content}
            elif isinstance(message.content, list):
                sub_messages = []
                for message_content in message.content:
                    sub_messages.append(message_content.model_dump())
                message_dict = {"role": "user", "content": sub_messages}
        elif isinstance(message, AssistantMessage):
            message = cast(AssistantMessage, message)
            message_dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                message_dict["tool_calls"] = [
                    tool_call.model_dump() for tool_call in message.tool_calls
                ]
        elif isinstance(message, SystemMessage):
            message_dict = {"role": "system", "content": message.content}
        elif isinstance(message, ToolMessage):
            message = cast(ToolMessage, message)
            message_dict = {
                "role": "tool",
                "content": message.content,
                "tool_call_id": message.tool_call_id,
            }
        elif isinstance(message, OpenAIMessage) and message.role in [
            "system",
            "tool",
            "user",
            "assistant",
        ]:
            # in the case pass in a plain OpenAIMessage
            message_origin_dict = message.model_dump()
            message_dict = {
                "role": message.role,
                "content": message_origin_dict["content"],
            }
            if message.tool_calls:
                message_dict["tool_calls"] = message_origin_dict["tool_calls"]
        else:
            raise ValueError(f"Got unknown type {message}")

        if message.name:
            message_dict["name"] = message.name

        return message_dict
