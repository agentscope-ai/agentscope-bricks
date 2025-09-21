# -*- coding: utf-8 -*-
import asyncio
import json
import traceback
from typing import Any, Dict, List, Optional, Sequence

try:
    from agentscope_runtime.sandbox.tools.tool import Tool
    from agentscope_runtime.sandbox.registry import SandboxType
except ImportError:
    raise ImportError(
        "Please install agentscope-runtime to use this feature: "
        "pip install agentscope-runtime",
    )

from agentscope_bricks.base.component import Component


class AgentScopeRuntimeToolAdapter(Tool):
    """Adapter class that wraps agentscope_bricks zh to make them
    compatible with AgentScope Runtime.

    This adapter allows any component that inherits from
    agentscope_bricks.base.component.Component to be used as a tool in
     AgentScope Runtime environments.

    Args:
        component (Component): The agentscope_bricks component to wrap
        name (str, optional): Override the component name. Defaults to
            component.name
        description (str, optional): Override the component description.
            Defaults to component.description
        tool_type (str): The tool type. Defaults to "function"

    Examples:
        Basic usage with a search component:

        .. code-block:: python

            from agentscope_bricks.zh.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_bricks.agentscope_runtime_utils import (
                AgentScopeRuntimeToolAdapter,
            )

            # Create the search component
            search_component = ModelstudioSearch()

            # Create the runtime adapter
            search_tool = AgentScopeRuntimeAdapter(search_component)

            # Use the tool
            result = search_tool(query="What's the weather in Beijing?")
    """

    def __init__(
        self,
        component: Component,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tool_type: str = "function",
    ) -> None:
        """Initialize the component adapter.

        Args:
            component: The agentscope_bricks component to wrap
            name: Optional override for the component name
            description: Optional override for the component description
            tool_type: The tool type
        """
        self._component = component
        self._name = name or component.name
        self._description = description or component.description
        self._tool_type = tool_type

        # Generate schema from component's function schema
        self._schema = self._generate_schema_from_component()

    @property
    def name(self) -> str:
        """Get the tool name."""
        return self._name

    @property
    def tool_type(self) -> str:
        """Get the tool type."""
        return self._tool_type

    @property
    def schema(self) -> Dict:
        """Get the tool schema in AgentScope Runtime format."""
        return {
            "type": "function",
            "function": self._schema,
        }

    @property
    def sandbox_type(self) -> SandboxType:
        """Component tools don't need a sandbox type."""
        return SandboxType.DUMMY

    @property
    def sandbox(self) -> None:
        """Component tools don't have sandbox."""
        return None

    def __call__(self, **kwargs: Any) -> dict:
        """Call the component directly."""
        return self.call(**kwargs)

    def call(self, *, sandbox: Optional[Any] = None, **kwargs: Any) -> dict:
        """Execute the component call.

        Args:
            sandbox: Ignored for component tools (for interface compatibility)
            **kwargs: Component parameters

        Returns:
            Dict: Result in AgentScope Runtime format
        """
        try:
            # Validate input with component's input type
            if self._component.input_type:
                validated_input = self._component.input_type.model_validate(
                    kwargs,
                )
            else:
                validated_input = kwargs

            # Execute the component asynchronously
            try:
                # We're in an async context, but need to run sync
                import concurrent.futures

                def run_async() -> Any:
                    return asyncio.run(self._component.arun(validated_input))

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                result = asyncio.run(self._component.arun(validated_input))

            # Format result
            if hasattr(result, "model_dump"):
                # Pydantic model result
                result_dict = result.model_dump()
                content_text = json.dumps(
                    result_dict,
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                # Other result types
                content_text = str(result)

            return {
                "meta": None,
                "content": [
                    {
                        "type": "text",
                        "text": content_text,
                        "annotations": None,
                        "description": "None",
                    },
                ],
                "isError": False,
            }

        except Exception as e:
            return {
                "meta": None,
                "content": [
                    {
                        "type": "text",
                        "text": f"{e}:\n{traceback.format_exc()}",
                        "annotations": None,
                        "description": "None",
                    },
                ],
                "isError": True,
            }

    def bind(self, *args: Any, **kwargs: Any) -> Any:
        """Return a new instance (for interface compatibility).

        Note: agentscope_bricks zh don't support binding like partial
        functions,
        so this returns the same instance.
        """
        return self

    def _generate_schema_from_component(self) -> Dict:
        """Generate schema from component's function schema."""
        # Get the component's function schema
        function_schema = self._component.function_schema.model_dump()

        # Convert to AgentScope Runtime format
        schema = {
            "name": self._name,
            "description": self._description,
            "parameters": function_schema.get("parameters", {}),
        }

        return schema


def create_agentscope_runtime_tools(
    components: Sequence[Component],
    name_overrides: Optional[Dict[str, str]] = None,
    description_overrides: Optional[Dict[str, str]] = None,
) -> List[AgentScopeRuntimeToolAdapter]:
    """Create a list of component adapters for use with AgentScope Runtime.

    This is a convenience function that creates adapters for multiple
    zh at once.

    Args:
        components: Sequence of agentscope_bricks zh to wrap
        name_overrides: Optional dict mapping component names to override names
        description_overrides: Optional dict mapping component names to
            override descriptions

    Returns:
        List[AgentScopeRuntimeToolAdapter]: List of adapter instances ready
        to use

    Examples:
        Create tools from multiple zh:

        .. code-block:: python

            from agentscope_bricks.zh.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_bricks.zh.RAGs.modelstudio_rag import (
                ModelstudioRag,
            )
            from agentscope_bricks.agentscope_runtime_utils import
            create_component_tools

            # Create zh
            search_component = ModelstudioSearch()
            rag_component = ModelstudioRag()

            # Create runtime adapters
            tools = create_component_tools([search_component, rag_component])

            # Use with AgentScope Runtime...
    """
    name_overrides = name_overrides or {}
    description_overrides = description_overrides or {}

    tools = []
    for component in components:
        name_override = name_overrides.get(component.name)
        description_override = description_overrides.get(component.name)

        tool = AgentScopeRuntimeToolAdapter(
            component,
            name=name_override,
            description=description_override,
        )
        tools.append(tool)

    return tools
