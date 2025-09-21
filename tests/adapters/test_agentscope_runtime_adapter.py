# -*- coding: utf-8 -*-
"""
Tests for tool.py module.

These tests verify that the tool.py module works correctly
with agentscope_bricks zh when AgentScope Runtime is available.
"""

import pytest
from pydantic import BaseModel

from agentscope_bricks.adapters.agentscope_runtime.tool import (
    AgentScopeRuntimeToolAdapter,
    create_agentscope_runtime_tools,
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


def test_agentscope_runtime_adapter_creation():
    """Test that AgentScopeRuntimeAdapter can be created successfully."""
    component = MockComponent()

    # This should work with agentscope_runtime available
    adapter = AgentScopeRuntimeToolAdapter(component)

    assert adapter.name == "mock_component"
    assert adapter.tool_type == "function"
    assert adapter.sandbox_type.name == "DUMMY"
    assert adapter.sandbox is None


def test_agentscope_runtime_adapter_with_overrides():
    """Test AgentScopeRuntimeAdapter with name and description overrides."""
    component = MockComponent()

    adapter = AgentScopeRuntimeToolAdapter(
        component,
        name="custom_name",
        description="Custom description",
        tool_type="custom_type",
    )

    assert adapter.name == "custom_name"
    assert adapter.tool_type == "custom_type"
    assert adapter._description == "Custom description"


def test_adapter_call_method():
    """Test that adapter call method works correctly."""
    component = MockComponent()
    adapter = AgentScopeRuntimeToolAdapter(component)

    result = adapter.call(value="test_value")

    assert result["isError"] is False
    assert len(result["content"]) == 1
    assert result["content"][0]["type"] == "text"
    assert "Processed: test_value" in result["content"][0]["text"]
    assert result["meta"] is None
    assert result["content"][0]["annotations"] is None


def test_adapter_call_method_validation_error():
    """Test input validation error handling."""
    component = MockComponent()
    adapter = AgentScopeRuntimeToolAdapter(component)

    # Call with invalid input (missing required field)

    result = adapter.call(invalid_field="test")

    # Should not even call asyncio.run due to validation error
    assert result["isError"] is True
    assert "validation error" in result["content"][0]["text"].lower()


def test_create_component_tools():
    """Test that create_component_tools works correctly."""
    component = MockComponent()

    # This should work with agentscope_runtime available
    tools = create_agentscope_runtime_tools([component])

    assert len(tools) == 1
    assert tools[0].name == "mock_component"
    assert isinstance(tools[0], AgentScopeRuntimeToolAdapter)


def test_create_component_tools_with_overrides():
    """Test create_component_tools with name and description overrides."""
    component = MockComponent()

    name_overrides = {"mock_component": "custom_name"}
    description_overrides = {"mock_component": "Custom description"}

    tools = create_agentscope_runtime_tools(
        [component],
        name_overrides=name_overrides,
        description_overrides=description_overrides,
    )

    assert len(tools) == 1
    assert tools[0].name == "custom_name"
    assert tools[0]._description == "Custom description"


def test_multiple_components_tools():
    """Test creating tools with multiple zh."""

    class MockComponent2(Component[MockInput, MockOutput]):
        name = "mock_component_2"
        description = "Second mock component"

        async def _arun(self, args: MockInput, **kwargs):
            return MockOutput(result=f"Second: {args.value}")

    component1 = MockComponent()
    component2 = MockComponent2()

    tools = create_agentscope_runtime_tools([component1, component2])

    assert len(tools) == 2
    tool_names = [tool.name for tool in tools]
    assert "mock_component" in tool_names
    assert "mock_component_2" in tool_names


if __name__ == "__main__":
    pytest.main([__file__])
