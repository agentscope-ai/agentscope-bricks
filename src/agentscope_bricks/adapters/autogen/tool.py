# -*- coding: utf-8 -*-
import json
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
)

try:
    from autogen_core import CancellationToken
    from autogen_core.tools import BaseTool
except ImportError:
    # Create mock classes when autogen is not available
    raise ImportError(
        "Please install autogen-core to use this feature: "
        "pip install autogen-core",
    )

from pydantic import BaseModel

from agentscope_bricks.base.component import Component


class AutogenToolAdapter(BaseTool[BaseModel, Any]):
    """Adapter class that wraps agentscope_bricks zh to make them
    compatible with AutoGen.

    This adapter allows any component that inherits from
    agentscope_bricks.base.component.Component to be used as a tool in
    AutoGen agents

    Args:
        component (Component): The agentscope_bricks component to wrap
        name (str, optional): Override the component name. Defaults to
            component.name
        description (str, optional): Override the component description.
            Defaults to component.description

    Examples:
        Basic usage with a search component:

        .. code-block:: python

            from agentscope_bricks.zh.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_bricks.autogen_util import ComponentToolAdapter
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from autogen_agentchat.agents import AssistantAgent
            from autogen_agentchat.messages import TextMessage
            from autogen_core import CancellationToken

            async def main():
                # Create the search component
                search_component = ModelstudioSearch()

                # Create the autogen tool adapter
                search_tool = ComponentToolAdapter(search_component)

                # Create an agents with the search tool
                model = OpenAIChatCompletionClient(model="gpt-4")
                agents = AssistantAgent(
                    "assistant",
                    tools=[search_tool],
                    model_client=model,
                )

                # Use the agents
                response = await agents.on_messages(
                    [TextMessage(content="What's the weather in Beijing?",
                    source="user")],
                    CancellationToken(),
                )
                print(response.chat_message)

            asyncio.run(main())
    """

    def __init__(
        self,
        component: Component,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Initialize the component tool adapter.

        Args:
            component: The agentscope_bricks component to wrap
            name: Optional override for the component name
            description: Optional override for the component description
        """

        self._component = component

        # Use provided name/description or fall back to component defaults
        tool_name = name or component.name
        tool_description = description or component.description

        # Create input model from component's input type
        arg_type = component.input_type
        return_type = component.return_type

        super().__init__(arg_type, return_type, tool_name, tool_description)

    async def run(
        self,
        args: BaseModel,
        cancellation_token: CancellationToken,
    ) -> Any:
        """Run the component with the provided arguments.

        Args:
            args: The arguments to pass to the component
            cancellation_token: Token to signal cancellation

        Returns:
            The result of the component execution

        Raises:
            Exception: If the operation is cancelled or the component
            execution fails
        """

        # Run the component
        try:
            result = await self._component.arun(args)
            # make sure return as string
            return json.dumps(result.model_dump(), ensure_ascii=False)
        except Exception as e:
            # Re-raise with more context
            raise Exception(
                f"Component {self._component.name} failed: {str(e)}",
            ) from e


def create_autogen_tools(
    components: Sequence[Component],
    name_overrides: Optional[Dict[str, str]] = None,
    description_overrides: Optional[Dict[str, str]] = None,
) -> List[AutogenToolAdapter]:
    """Create a list of component tool adapters for use with AutoGen agents.

    This is a convenience function that creates adapters for multiple
    zh at once, similar to how tool.py provides
    LanggraphNode.

    Args:
        components: Sequence of agentscope_bricks zh to wrap
        name_overrides: Optional dict mapping component names to override names
        description_overrides: Optional dict mapping component names to
                override descriptions


    Returns:
        List of ComponentToolAdapter instances ready to use with AutoGen agents

    Examples:
        Create tools from multiple zh:

        .. code-block:: python

            from agentscope_bricks.zh.modelstudio_search import
            ModelstudioSearch
            from agentscope_bricks.zh.modelstudio_rag
            import ModelstudioRag
            from agentscope_bricks.autogen_util import create_component_tools
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from autogen_agentchat.agents import AssistantAgent

            async def main():
                # Create zh
                search_component = ModelstudioSearch()
                rag_component = ModelstudioRag()

                # Create autogen tools
                tools = create_component_tools([search_component,
                    rag_component])

                # Create agents with all tools
                model = OpenAIChatCompletionClient(model="gpt-4")
                agents = AssistantAgent(
                    "assistant",
                    tools=tools,
                    model_client=model,
                )

                # Use the agents...

            asyncio.run(main())
    """
    name_overrides = name_overrides or {}
    description_overrides = description_overrides or {}

    tools = []
    for component in components:
        name_override = name_overrides.get(component.name)
        description_override = description_overrides.get(component.name)

        tool = AutogenToolAdapter(
            component,
            name=name_override,
            description=description_override,
        )
        tools.append(tool)

    return tools
