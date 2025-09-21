# -*- coding: utf-8 -*-
import os
from typing import (
    List,
    Optional,
    Any,
    AsyncGenerator,
    Union,
)

from agentscope_runtime.engine.agents.base_agent import Agent
from agentscope_runtime.engine.schemas.agent_schemas import (
    Content,
    Message,
    convert_to_openai_messages,
    MessageType,
    Role,
    Tool,
)
from agentscope_runtime.engine.schemas.context import Context
from agentscope_runtime.sandbox.tools.tool import Tool as SandboxTool
from agentscope_bricks.models import BaseLLM
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage, Parameters
from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
)
from agentscope_bricks.utils.message_util import merge_incremental_chunk
from agentscope_bricks.utils.tool_call_utils import (
    execute_tool_call_from_message,
)
from agentscope_bricks.adapters.agentscope_runtime.tool import (
    AgentScopeRuntimeToolAdapter,
)


class SimpleAgent(Agent):
    def __init__(
        self,
        name: str = "",
        tools: Optional[List[SandboxTool]] = None,
        agent_config: Optional[dict] = None,
    ):
        """
        Simple Agent is an agent that call llm and execute tool to run.
        """

        super().__init__(name=name, agent_config=agent_config)

        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        self.llm = BaseLLM(api_key=api_key)
        self.tools = tools
        self.tool_maps = {tool.name: tool for tool in self.tools}
        self._attr = {
            "tools": tools,
            "agent_config": self.agent_config,
        }

    def copy(self) -> "SimpleAgent":
        return SimpleAgent(**self._attr)

    async def run_async(
        self,
        context: Context,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[Message, Content], None]:
        oai_messages = convert_to_openai_messages(context.request.input)
        oai_tools = [Tool(**tool.schema) for tool in self.tools]

        context.request.tools = oai_tools
        parameters = Parameters(
            **context.request.model_dump(
                exclude_none=True,
                exclude_unset=True,
            ),
        )

        while True:
            response = self.llm.astream_unwrapped(
                model=context.request.model,
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
                            self.tool_maps,
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


# use  agentscope-bricks components
search_tool = AgentScopeRuntimeToolAdapter(ModelstudioSearchLite())

# use simple agent to do function call.
simple_agent = SimpleAgent(
    tools=[search_tool],
)
