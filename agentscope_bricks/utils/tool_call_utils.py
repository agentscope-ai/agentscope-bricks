# -*- coding: utf-8 -*-
import asyncio
import json
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from agentscope_runtime.sandbox.tools.tool import Tool as SandboxTool
from agentscope_bricks.base.component import Component
from agentscope_bricks.mcp_utils.server import MCPServer
from agentscope_bricks.models.llm import BaseLLM
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    Role,
    Tool,
    FunctionCall,
    AgentRequest,
    Content,
    convert_to_openai_messages,
    MessageType,
    DataContent,
)
from agentscope_bricks.utils.schemas.oai_llm import (
    AssistantMessage,
    Parameters,
    OpenAIMessage,
    ToolCall,
    ToolMessage,
    create_chat_completion_chunk,
)
from agentscope_bricks.utils.tracing_utils import TraceType
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.message_util import merge_incremental_chunk


async def execute_tool_call(
    tool_calls: List[Union[ToolCall, Dict]],
    tools: Optional[
        Mapping[str, Union[Component, SandboxTool, Callable]]
    ] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Execute multiple tool in the tools register

    Args:
        tool_calls: List of ToolCall objects or dictionaries representing
            tool calls to execute, typically generated from LLM response.
        tools: Optional mapping of tool names to callable components or
            functions that can be executed.
        **kwargs: Additional keyword arguments passed to tool execution,
            including tool_name which gets set during execution.

    Returns:
        Dict[str, Any]: Dictionary mapping tool names to their execution
            results as transformed response strings.
    """
    result = {}

    if not tool_calls or not tools:
        return result

    # convert tool_call to ToolCall Object
    formatted_tool_calls = [
        ToolCall(**tool_call) if isinstance(tool_call, dict) else tool_call
        for tool_call in tool_calls
    ]

    async def process_tool_call(tool_call: ToolCall) -> None:
        """Process a single tool call asynchronously.

        Args:
            tool_call: The ToolCall object to process.
        """
        tool_name = tool_call.function.name
        tool = tools.get(tool_name)
        kwargs["tool_name"] = tool_name
        if tool:
            if isinstance(tool, SandboxTool):
                tool_response = tool(
                    **json.loads(
                        tool_call.function.arguments,
                    ),
                )
            else:
                parameters = tool.verify_args(tool_call.function.arguments)
                tool_response = await tool.arun(parameters, **kwargs)
        else:
            tool_response = None
        result[tool_name] = BaseLLM.transform_response(tool_response)

    await asyncio.gather(
        *[process_tool_call(tool_call) for tool_call in formatted_tool_calls],
    )

    return result


async def execute_tool_call_from_message(
    response: Union[ChatCompletion, ChatCompletionChunk],
    tools: Optional[
        Mapping[str, Union[Component, SandboxTool, Callable]]
    ] = None,
    **kwargs: Any,
) -> List[OpenAIMessage]:
    """Execute tool calls from a chat response message.

    Args:
        response: The chat completion response containing tool calls to process
            Can be either ChatCompletion or ChatCompletionChunk.
        tools: Optional mapping of tool names to callable components or
            functions that can be executed.
        **kwargs: Additional keyword arguments passed to tool execution.

    Returns:
        List[OpenAIMessage]: List of prompt messages including the assistant
            response with tool calls and tool response messages. Returns empty
            list if no tool calls are present or finish_reason is not
            "tool_calls".
    """
    if response.choices[0].finish_reason != "tool_calls":
        return []

    response_message = (
        response.choices[0].delta
        if isinstance(response, ChatCompletionChunk)
        else response.choices[0].message
    )
    tool_calls = response_message.tool_calls

    if not tool_calls or not tools:
        return []
    tool_calls = (
        [
            ToolCall(
                index=tool_call.index,
                id=tool_call.id,
                type=tool_call.type,
                function=FunctionCall(**tool_call.function.__dict__),
            )
            for tool_call in tool_calls
        ]
        if tool_calls
        else None
    )
    request_messages: List[OpenAIMessage] = []
    assistant_response = AssistantMessage(tool_calls=tool_calls)
    if response_message.content:
        assistant_response.content = response_message.content

    request_messages.append(assistant_response)

    tool_call_results = await execute_tool_call(tool_calls, tools, **kwargs)

    for i, tool_name in enumerate(tool_call_results):
        request_messages.append(
            ToolMessage(
                content=tool_call_results[tool_name],
                tool_call_id=tool_calls[i].id,
                name=tool_name,
            ),
        )

    return request_messages


def check_and_update_available_tools(
    tools: Optional[List[Union[Tool, Dict]]] = None,
    available_components: Optional[
        Dict[str, Union[Component, Callable]]
    ] = None,
) -> Tuple[Dict[str, Component], List[Union[Tool, Dict]]]:
    """Update available components to the parameter tools.

    Args:
        tools: Sequence of Tool objects or
            dictionaries defining the tools to check for.
        available_components: Register of components' name
            to Component or Callable instances.

    Returns:
        Dict[str, Component]: Dictionary containing only the components
            whose names match the tool names. Returns empty dict if no
            tools are provided.
    """
    # add available_components to tools
    if not tools:
        tools = []

    if available_components:
        for tool_name in available_components:
            tools.append(
                Tool(
                    function=available_components[tool_name].function_schema,
                ),
            )

    if tools == []:
        return {}, tools

    result: Dict[str, Any] = {k: v for k, v in available_components.items()}
    return result, tools


@trace(
    trace_type=TraceType.FUNCTION_CALL,
    trace_name="function_call_with_openai",
)
async def function_call_with_openai(
    model: str,
    model_cls: BaseLLM,
    messages: List[OpenAIMessage],
    parameters: Optional[Parameters] = None,
    available_components: Optional[
        Dict[str, Union[Component, Callable]]
    ] = None,
    mcp_servers: Optional[List[MCPServer]] = None,
    **kwargs: Any,
) -> AsyncGenerator[ChatCompletionChunk | None, Any]:
    """Execute a function calling loop with LLM and available tools.

    This function handles the iterative process of calling the LLM, executing
    any tool calls in the response if tool components exists, and continuing
    the conversation until no more tool calls are needed.

    Args:
        model: The model name to use for LLM completion.
        model_cls: The BaseLLM instance to use for generating responses.
        messages: List of Message objects representing the conversation.
        parameters: Optional Parameters object for LLM configuration.
        available_components: Register of components that can be executed as
            tools.
        mcp_servers: Optional list of MCPServer instances to get additional
            tools from.
        **kwargs: Additional keyword arguments including:
            - allow_incremental_tools_message: Whether to yield incremental
              tool messages (defaults to True)
            - Other arguments passed to LLM and tool execution

    Yields:
        ChatCompletionChunk | None: Streaming response chunks from the LLM
            and tool execution results. May yield None in some cases.
    """
    if mcp_servers:
        from agentscope_bricks.utils.mcp_util import MCPUtil

        components = await MCPUtil.get_all_tools(mcp_servers)
        tools = [
            {"type": "function", "function": comp.function_schema.model_dump()}
            for comp in components
        ]

        # update parameters
        base_params = {
            "tools": tools,
            "stream_options": {"include_usage": True},
        }
        if parameters is not None:
            base_params["tools"].extend(parameters.tools)
        parameters = Parameters(**base_params)

        # update available components
        available_components = {
            **(available_components or {}),
            **{comp.name: comp for comp in components},
        }

    allow_incremental_tools_message = kwargs.pop(
        "allow_incremental_tools_message",
        True,
    )
    # no need to valid tools before calling llm
    valid_components, tools = check_and_update_available_tools(
        parameters.tools,
        available_components,
    )
    parameters.tools = tools
    usage_chunks = []

    while True:
        response = model_cls.astream_unwrapped(
            model=model,
            stream=True,
            messages=messages,
            parameters=parameters,
            **kwargs,
        )
        is_more_request = False
        cumulated = []
        async for resp in response:
            if resp.usage:
                usage_chunks.append(resp)
                continue
            if not resp.choices:
                continue
            # if not allow_incremental_tools_message is True, we should not to
            # yield the response
            if not allow_incremental_tools_message and (
                resp.choices[0].delta.tool_calls
                or resp.choices[0].finish_reason == "tool_calls"
            ):
                pass
            else:
                yield resp

            cumulated.append(resp)

            if (
                len(resp.choices) > 0
                and resp.choices[0].finish_reason == "tool_calls"
            ):
                cumulated_resp = merge_incremental_chunk(cumulated)
                if not allow_incremental_tools_message:
                    cumulated_resp.choices[0].delta.role = Role.ASSISTANT
                    yield cumulated_resp

                tool_response: List[OpenAIMessage] = (
                    await execute_tool_call_from_message(
                        cumulated_resp,
                        valid_components,
                        **kwargs,
                    )
                )
                # the first response is from the assistant, the others are from
                # the tool calls
                if len(tool_response) > 1:
                    is_more_request = True
                    # TODO: only support one tool response
                    yield create_chat_completion_chunk(
                        message=tool_response[1],
                        model_name=model,
                        finish_reason=None,
                    )
                messages.extend(tool_response)

        if not is_more_request:
            break

    if len(usage_chunks) > 0:
        yield merge_incremental_chunk(usage_chunks)


@trace(
    trace_type=TraceType.FUNCTION_CALL,
    trace_name="function_call_with_agent_api",
)
async def function_call_with_agent_api(
    model: str,
    model_cls: BaseLLM,
    request: Union[AgentRequest, Dict],
    available_components: Optional[
        Dict[str, Union[Component, Callable]]
    ] = None,
    mcp_servers: Optional[List[MCPServer]] = None,
    **kwargs: Any,
) -> AsyncGenerator[Message | Content, Any]:
    """Execute a function calling loop with LLM and available tools.

    This function handles the iterative process of calling the LLM, executing
    any tool calls in the response if tool components exists, and continuing
    the conversation until no more tool calls are needed.

    Args:
        model: The model name to use for LLM completion.
        model_cls: The BaseLLM instance to use for generating responses.
        request: The agent api request object.
        available_components: Register of components that can be executed as
            tools.
        mcp_servers: Optional list of MCPServer instances to get additional
            tools from.
        **kwargs: Additional keyword arguments including:
            - allow_incremental_tools_message: Whether to yield incremental
              tool messages (defaults to True)
            - Other arguments passed to LLM and tool execution

    Yields:
        Message | None: The message object defined in the Agent api
    """

    if isinstance(request, dict):
        request = AgentRequest(**request)

    messages = request.input

    if mcp_servers:
        from agentscope_bricks.utils.mcp_util import MCPUtil

        components = await MCPUtil.get_all_tools(mcp_servers)
        mcp_tools = [
            Tool(
                type="function",
                function=component.function_schema.model_dump(),
            )
            for component in components
        ]

        if request.tools:
            request.tools.extend(mcp_tools)
        else:
            request.tools = mcp_tools

        # update available components
        available_components = {
            **(available_components or {}),
            **{component.name: component for component in components},
        }

    # no need to valid tools before calling llm
    valid_components, tools = check_and_update_available_tools(
        request.tools,
        available_components,
    )
    request.tools = tools

    # prepare oai format
    oai_messages: List[Dict] = convert_to_openai_messages(messages)
    parameters = Parameters(
        **request.model_dump(
            exclude_none=True,
            exclude_unset=True,
        ),
    )

    while True:
        response = model_cls.astream_unwrapped(
            model=model,
            stream=True,
            messages=oai_messages,
            parameters=parameters,
            **kwargs,
        )
        is_more_request = False
        init_event = True
        output_message = Message()
        cumulated = []
        tool_calls_result = False
        content_index = None

        # Create initial Message
        async for resp in response:
            # generate init message
            if init_event:
                if (
                    resp.choices[0].delta.tool_calls
                    and resp.choices[0].finish_reason != "tool_calls"
                ):
                    output_message.type = MessageType.FUNCTION_CALL
                else:
                    output_message.role = Role.ASSISTANT
                    output_message.type = MessageType.MESSAGE
                yield output_message.in_progress()

                init_event = False

            # cumulate resp
            cumulated.append(resp)

            # record usage for text message
            if resp.usage and output_message.type == MessageType.MESSAGE:
                yield output_message.content_completed(content_index)
                output_message.usage = resp.usage.model_dump()
                yield output_message.completed()
                continue

            # record usage for tool call
            elif (
                resp.usage
                and output_message.type == MessageType.FUNCTION_CALL
                and tool_calls_result
            ):
                cumulated_resp = merge_incremental_chunk(cumulated)
                delta_content = output_message.content_completed(
                    content_index,
                )
                yield delta_content
                output_message.usage = resp.usage.model_dump()
                yield output_message.completed()

                # tool execution
                tool_responses: List[OpenAIMessage] = (
                    await execute_tool_call_from_message(
                        cumulated_resp,
                        valid_components,
                        **kwargs,
                    )
                )
                if len(tool_responses) > 1:
                    is_more_request = True

                    # TODO: only support one tool response
                    tool_output_message = Message.from_openai_message(
                        tool_responses[1],
                    )
                    yield tool_output_message.completed()

                tool_response_dict = [
                    tool_response.model_dump()
                    for tool_response in tool_responses
                ]
                oai_messages.extend(tool_response_dict)

            # return when no response choices and handled usage
            if not resp.choices:
                continue

            # get delta content and yield
            delta_content = Content.from_chat_completion_chunk(
                resp,
                content_index,
            )
            if delta_content:
                delta_content = output_message.add_delta_content(
                    new_content=delta_content,
                )
                content_index = delta_content.index
                yield delta_content

            if (
                len(resp.choices) > 0
                and resp.choices[0].finish_reason == "tool_calls"
            ):
                tool_calls_result = True

        if not is_more_request:
            break

    # if len(usage_chunks) > 0:
    #     last_usage_chunk = merge_incremental_chunk(usage_chunks)
    #     delta_content = text_message.add_delta_content(
    #         new_content=Content.from_chat_completion_chunk(
    #             last_usage_chunk,
    #         ),
    #     )
    #     yield delta_content
    #     text_message.completed()
