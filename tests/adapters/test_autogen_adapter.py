# -*- coding: utf-8 -*-
"""
Tests for tool.py module.

These tests verify that the tool.py module works correctly
with agentscope_bricks zh when AutoGen is available.
"""

import pytest
from pydantic import BaseModel

from agentscope_bricks.adapters.autogen.tool import (
    AutogenToolAdapter,
    create_autogen_tools,
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


def test_component_tool_adapter_creation():
    """Test that ComponentToolAdapter can be created successfully."""
    component = MockComponent()

    # This should work with autogen_core available
    adapter = AutogenToolAdapter(component)

    assert adapter.name == "mock_component"
    assert adapter.description == "A mock component for testing"
    assert adapter.args_type is not None


def test_create_component_tools():
    """Test that create_component_tools works correctly."""
    component = MockComponent()

    # This should work with autogen_core available
    tools = create_autogen_tools([component])

    assert len(tools) == 1
    assert tools[0].name == "mock_component"


def test_create_component_tools_with_overrides():
    """Test create_component_tools with name and description overrides."""
    component = MockComponent()

    name_overrides = {"mock_component": "custom_name"}
    description_overrides = {"mock_component": "Custom description"}

    tools = create_autogen_tools(
        [component],
        name_overrides=name_overrides,
        description_overrides=description_overrides,
    )

    assert len(tools) == 1
    assert tools[0].name == "custom_name"
    assert tools[0].description == "Custom description"


@pytest.mark.asyncio
async def test_component_tool_adapter_run_method():
    """Test that ComponentToolAdapter run method works correctly."""
    component = MockComponent()
    adapter = AutogenToolAdapter(component)

    # Create a mock input model
    from autogen_core import CancellationToken

    class TestInput(BaseModel):
        value: str

    # Test the run method by calling the component directly
    # since CancellationToken might be cancelled by default
    result = await adapter.run(
        MockInput(value="test_value"),
        cancellation_token=CancellationToken(),
    )

    # The result should be the formatted output from the component
    assert result == '{"result": "Processed: test_value"}'


def test_component_tool_adapter_input_model_creation():
    """Test that ComponentToolAdapter creates input models correctly."""
    component = MockComponent()
    adapter = AutogenToolAdapter(component)

    # The args_type should be callable (it's a method)
    assert adapter.args_type is not None
    assert callable(adapter.args_type)


if __name__ == "__main__":
    pytest.main([__file__])
