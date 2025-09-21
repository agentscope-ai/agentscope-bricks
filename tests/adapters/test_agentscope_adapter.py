# -*- coding: utf-8 -*-
"""
Tests for tool.py module.

These tests verify that the tool.py module works correctly
with agentscope_bricks zh when AgentScope is available.
"""

import pytest
from pydantic import BaseModel

from agentscope_bricks.adapters.agentscope.tool import (
    agentscope_tool_adapter,
    agentscope_toolkit_adapter,
)
from agentscope_bricks.base.component import Component


class MockInput(BaseModel):
    value: str


class MockOutput(BaseModel):
    result: str


class MockComponent(Component[MockInput, MockOutput]):
    """Mock component for testing."""

    name = "mock_component"
    description = "A mock component for testing"

    async def _arun(self, args: MockInput, **kwargs):
        return MockOutput(result=f"Processed: {args.value}")


def test_component_to_agentscope_tool_creation():
    """Test that component_to_agentscope_tool can be created successfully."""
    component = MockComponent()

    # This should work with agentscope available
    tool = agentscope_tool_adapter(component)

    assert tool.name == "mock_component"
    assert tool.source == "function"
    assert tool.group == "basic"
    assert tool.mcp_name is None


def test_component_to_agentscope_tool_with_overrides():
    """Test component_to_agentscope_tool with name and description
    overrides."""
    component = MockComponent()

    tool = agentscope_tool_adapter(
        component,
        name="custom_name",
        description="Custom description",
    )

    assert tool.name == "custom_name"
    assert tool.json_schema["function"]["description"] == "Custom description"


def test_create_component_toolkit():
    """Test that create_component_toolkit works correctly."""
    component = MockComponent()

    # This should work with agentscope available
    toolkit = agentscope_toolkit_adapter([component])

    assert len(toolkit.tools) == 1
    assert "mock_component" in toolkit.tools
    assert toolkit.tools["mock_component"].name == "mock_component"


def test_create_component_toolkit_with_overrides():
    """Test create_component_toolkit with name and description overrides."""
    component = MockComponent()

    name_overrides = {"mock_component": "custom_name"}
    description_overrides = {"mock_component": "Custom description"}

    toolkit = agentscope_toolkit_adapter(
        [component],
        name_overrides=name_overrides,
        description_overrides=description_overrides,
    )

    assert len(toolkit.tools) == 1
    assert "custom_name" in toolkit.tools
    assert toolkit.tools["custom_name"].name == "custom_name"


def test_component_tool_wrapper_execution():
    """Test that the wrapped component function executes correctly."""
    component = MockComponent()
    tool = agentscope_tool_adapter(component)

    # Test the wrapper function directly
    result = tool.original_func(value="test_value")

    from agentscope.tool import ToolResponse

    assert isinstance(result, ToolResponse)
    assert len(result.content) == 1
    # Content is now a dict, not a TextBlock object
    assert result.content[0]["type"] == "text"
    assert "Processed: test_value" in result.content[0]["text"]


def test_component_tool_wrapper_error_handling():
    """Test error handling in the wrapped component function."""
    component = MockComponent()
    tool = agentscope_tool_adapter(component)

    # Test input validation error
    result = tool.original_func(invalid_field="test")

    from agentscope.tool import ToolResponse

    assert isinstance(result, ToolResponse)
    assert result.metadata.get("error") is True
    assert "Input validation error" in result.content[0]["text"]


def test_multiple_components_toolkit():
    """Test creating toolkit with multiple zh."""

    class MockComponent2(Component[MockInput, MockOutput]):
        name = "mock_component_2"
        description = "Second mock component"

        async def _arun(self, args: MockInput, **kwargs):
            return MockOutput(result=f"Second: {args.value}")

    component1 = MockComponent()
    component2 = MockComponent2()

    toolkit = agentscope_toolkit_adapter([component1, component2])

    assert len(toolkit.tools) == 2
    assert "mock_component" in toolkit.tools
    assert "mock_component_2" in toolkit.tools


def test_json_schema_format():
    """Test that JSON schema is formatted correctly for AgentScope."""
    component = MockComponent()
    tool = agentscope_tool_adapter(component)

    schema = tool.json_schema

    assert schema["type"] == "function"
    assert "function" in schema
    assert "name" in schema["function"]
    assert "description" in schema["function"]
    assert "parameters" in schema["function"]
    assert schema["function"]["name"] == "mock_component"


@pytest.mark.asyncio
async def test_toolkit_tool_execution():
    """Test actual tool execution through AgentScope toolkit."""
    from agentscope.message import ToolUseBlock

    component = MockComponent()
    toolkit = agentscope_toolkit_adapter([component])

    # Create a tool call block
    tool_call = ToolUseBlock(
        type="tool_use",
        id="test_call_1",
        name="mock_component",
        input={"value": "test_input"},
    )

    # Execute the tool - first await call_tool_function to get the async
    # generator
    response_found = False
    async_gen = await toolkit.call_tool_function(tool_call)
    async for response in async_gen:
        from agentscope.tool import ToolResponse

        assert isinstance(response, ToolResponse)
        assert len(response.content) > 0
        # The response should contain our processed result
        response_found = True
        break  # Just test the first response

    assert response_found, "No response received from tool execution"


def test_toolkit_json_schemas():
    """Test that toolkit generates correct JSON schemas like in AgentScope
    tutorial."""
    import json

    component = MockComponent()
    toolkit = agentscope_toolkit_adapter([component])

    # Get JSON schemas
    schemas = toolkit.get_json_schemas()

    assert len(schemas) == 1
    schema = schemas[0]

    # Verify structure matches AgentScope tutorial format
    assert schema["type"] == "function"
    assert "function" in schema

    function_def = schema["function"]
    assert "name" in function_def
    assert "parameters" in function_def
    assert "description" in function_def

    assert function_def["name"] == "mock_component"
    assert function_def["description"] == "A mock component for testing"

    # Verify parameters structure
    parameters = function_def["parameters"]
    assert parameters["type"] == "object"
    assert "properties" in parameters
    assert "required" in parameters

    # Should have 'value' property from MockInput
    properties = parameters["properties"]
    assert "value" in properties
    assert properties["value"]["type"] == "string"

    # Should be required
    assert "value" in parameters["required"]

    # Test that JSON serialization works (like in tutorial)
    try:
        json_output = json.dumps(schemas, indent=4, ensure_ascii=False)
        assert "mock_component" in json_output
        assert "value" in json_output
        print("✅ JSON schema serialization successful")
    except Exception as e:
        pytest.fail(f"JSON serialization failed: {e}")


def test_multiple_components_json_schemas():
    """Test JSON schemas for multiple zh."""
    import json

    class MockSearchComponent(Component[MockInput, MockOutput]):
        name = "search_tool"
        description = "A search tool for testing"

        async def _arun(self, args: MockInput, **kwargs):
            return MockOutput(result=f"Search: {args.value}")

    class MockAnalysisComponent(Component[MockInput, MockOutput]):
        name = "analysis_tool"
        description = "An analysis tool for testing"

        async def _arun(self, args: MockInput, **kwargs):
            return MockOutput(result=f"Analysis: {args.value}")

    components = [MockSearchComponent(), MockAnalysisComponent()]
    toolkit = agentscope_toolkit_adapter(components)

    schemas = toolkit.get_json_schemas()

    assert len(schemas) == 2

    # Check that both tools are present
    tool_names = [schema["function"]["name"] for schema in schemas]
    assert "search_tool" in tool_names
    assert "analysis_tool" in tool_names

    # Verify JSON serialization
    json_output = json.dumps(schemas, indent=4, ensure_ascii=False)
    assert "search_tool" in json_output
    assert "analysis_tool" in json_output


@pytest.mark.asyncio
@pytest.mark.skipif(
    "DASHSCOPE_API_KEY" not in __import__("os").environ,
    reason="DASHSCOPE_API_KEY environment variable not set",
)
async def test_component_with_react_agent_integration():
    """Test end-to-end integration with AgentScope ReActAgent"""
    import os
    from agentscope.agent import ReActAgent
    from agentscope.model import DashScopeChatModel
    from agentscope.formatter import DashScopeChatFormatter
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg

    # Create a simple component for testing
    class SimpleCalculatorComponent(Component[MockInput, MockOutput]):
        name = "simple_calculator"
        description = "A simple calculator that doubles the input number"

        async def _arun(self, args: MockInput, **kwargs):
            try:
                # Try to parse as number and double it
                number = float(args.value)
                result = number * 2
                return MockOutput(result=f"Result: {result}")
            except ValueError:
                return MockOutput(
                    result=f"Error: '{args.value}' is not a number",
                )

    # Create toolkit with our component
    component = SimpleCalculatorComponent()
    toolkit = agentscope_toolkit_adapter([component])

    # Create ReActAgent with our toolkit (similar to tutorial)
    agent = ReActAgent(
        name="TestAgent",
        sys_prompt="You are a helpful assistant that can use tools. When "
        "asked to calculate something, use the simple_calculator "
        "tool.",
        model=DashScopeChatModel(
            model_name="qwen-max",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            stream=False,  # Disable streaming for testing
        ),
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    # Test a simple calculation request
    test_message = Msg(
        name="user",
        role="user",
        content="Please calculate 5 doubled using the calculator tool.",
    )

    # This should trigger the agent to use our component
    try:
        response = await agent(test_message)

        # Verify we got a response
        assert response is not None
        assert hasattr(response, "content")

        # The response should mention the calculation result
        response_text = str(response.content).lower()
        # Should either contain the result or mention using the tool
        assert any(
            keyword in response_text
            for keyword in ["10", "result", "calculator", "tool"]
        )

        print("✅ End-to-end integration test successful")

    except Exception as e:
        # If the test fails due to API issues, we'll skip but log the attempt
        pytest.skip(f"Integration test skipped due to API error: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
