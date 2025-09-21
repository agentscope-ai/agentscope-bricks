# -*- coding: utf-8 -*-
"""Unit tests for MCPServerManager class."""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from agentscope_bricks.mcp_utils.server import (
    MCPServerManager,
    MCPServerStdio,
    MCPServerSse,
)


@pytest.fixture
def stdio_config():
    """Fixture for stdio server configuration."""
    return {
        "test-stdio-server": {
            "transport": "stdio",
            "command": "python",
            "args": ["-c", "print('hello')"],
        },
    }


@pytest.fixture
def sse_config():
    """Fixture for SSE server configuration."""
    return {
        "mcp-time": {
            "transport": "sse",
            "url": "https://mcp.higress.ai/mcp-time/cme6u9s4j00597201q4zwd4nm/sse",  # noqa E501
        },
    }


@pytest.fixture
def mixed_config():
    """Fixture for mixed server configuration."""
    return {
        "test-stdio-server": {
            "transport": "stdio",
            "command": "python",
            "args": ["-c", "print('hello')"],
        },
        "mcp-time": {
            "transport": "sse",
            "url": "https://mcp.higress.ai/mcp-time/cme6u9s4j00597201q4zwd4nm/sse",  # noqa E501
        },
    }


def test_manager_from_stdio_config(stdio_config):
    """Test creating MCPServerManager from stdio config."""
    manager = MCPServerManager.from_config(stdio_config)

    # Verify the manager was created with correct servers
    assert len(manager.servers) == 1
    assert isinstance(manager.servers[0], MCPServerStdio)
    assert manager.servers[0].name == "test-stdio-server"

    # Verify the serversMap
    assert len(manager.serversMap) == 1
    assert "test-stdio-server" in manager.serversMap
    assert isinstance(manager.serversMap["test-stdio-server"], MCPServerStdio)


def test_manager_from_sse_config(sse_config):
    """Test creating MCPServerManager from SSE config."""
    manager = MCPServerManager.from_config(sse_config)

    # Verify the manager was created with correct servers
    assert len(manager.servers) == 1
    assert isinstance(manager.servers[0], MCPServerSse)
    assert manager.servers[0].name == "mcp-time"

    # Verify the serversMap
    assert len(manager.serversMap) == 1
    assert "mcp-time" in manager.serversMap
    assert isinstance(manager.serversMap["mcp-time"], MCPServerSse)


def test_manager_from_mixed_config(mixed_config):
    """Test creating MCPServerManager from mixed config."""
    manager = MCPServerManager.from_config(mixed_config)

    # Verify the manager was created with correct servers
    assert len(manager.servers) == 2

    # Check that we have both types of servers
    server_types = [type(server) for server in manager.servers]
    assert MCPServerStdio in server_types
    assert MCPServerSse in server_types

    # Verify the serversMap
    assert len(manager.serversMap) == 2
    assert "test-stdio-server" in manager.serversMap
    assert "mcp-time" in manager.serversMap


def test_manager_from_config_with_type_key():
    """Test creating MCPServerManager with 'type' key instead of 'transport'"""
    config = {
        "test-server": {
            "type": "stdio",
            "command": "python",
            "args": ["-c", "print('hello')"],
        },
    }

    manager = MCPServerManager.from_config(config)

    # Verify the manager was created correctly
    assert len(manager.servers) == 1
    assert isinstance(manager.servers[0], MCPServerStdio)


def test_manager_from_config_with_baseurl_key():
    """Test creating MCPServerManager with 'baseUrl' key instead of 'url'."""
    config = {
        "test-server": {
            "transport": "sse",
            "baseUrl": "https://example.com/sse",
            "headers": {"Authorization": "Bearer token"},
        },
    }

    manager = MCPServerManager.from_config(config)

    # Verify the manager was created correctly
    assert len(manager.servers) == 1
    assert isinstance(manager.servers[0], MCPServerSse)
    # The server should have the correct URL
    assert manager.servers[0].params["url"] == "https://example.com/sse"


def test_manager_from_config_with_dashscope_api_key():
    """Test creating MCPServerManager with DASHSCOPE_API_KEY replacement."""
    config = {
        "test-server": {
            "transport": "sse",
            "url": "https://example.com/sse",
            "headers": {"Authorization": "Bearer ${DASHSCOPE_API_KEY}"},
        },
    }

    # Mock the environment variable
    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-api-key"}):
        manager = MCPServerManager.from_config(config)

    # Verify the API key was replaced
    assert len(manager.servers) == 1
    assert isinstance(manager.servers[0], MCPServerSse)
    assert (
        manager.servers[0].params["headers"]["Authorization"]
        == "Bearer test-api-key"
    )


def test_manager_from_config_missing_transport():
    """Test creating MCPServerManager with missing transport field."""
    config = {
        "test-server": {
            "command": "python",
            "args": ["-c", "print('hello')"],
        },
    }

    # Expect a ValueError
    with pytest.raises(ValueError, match="Missing 'transport' field"):
        MCPServerManager.from_config(config)


def test_manager_from_config_invalid_transport():
    """Test creating MCPServerManager with invalid transport type."""
    config = {
        "test-server": {
            "transport": "invalid",
            "command": "python",
            "args": ["-c", "print('hello')"],
        },
    }

    # Expect a ValueError
    with pytest.raises(ValueError, match="Invalid transport 'invalid'"):
        MCPServerManager.from_config(config)


def test_manager_from_config_missing_command():
    """Test creating MCPServerManager with missing command for stdio
    transport."""
    config = {
        "test-server": {
            "transport": "stdio",
        },
    }

    # Expect a ValueError
    with pytest.raises(ValueError, match="Missing 'command' field"):
        MCPServerManager.from_config(config)


def test_manager_from_config_missing_url():
    """Test creating MCPServerManager with missing url for SSE transport."""
    config = {
        "test-server": {
            "transport": "sse",
        },
    }

    # Expect a ValueError
    with pytest.raises(ValueError, match="Missing 'url' field"):
        MCPServerManager.from_config(config)


def test_manager_from_config_file_not_found():
    """Test creating MCPServerManager from non-existent config file."""
    with pytest.raises(FileNotFoundError):
        MCPServerManager.from_config_file("/path/that/does/not/exist.json")


@pytest.mark.asyncio
async def test_manager_async_context_manager(mixed_config):
    """Test MCPServerManager async context manager functionality."""
    manager = MCPServerManager.from_config(mixed_config)

    # Mock the servers' __aenter__ and __aexit__ methods
    for server in manager.servers:
        server.__aenter__ = AsyncMock(return_value=server)
        server.__aexit__ = AsyncMock()

    # Use the manager as an async context manager
    async with manager as servers:
        # Verify that __aenter__ was called on all servers
        for server in manager.servers:
            server.__aenter__.assert_called_once()

        # Verify that we got the active servers
        assert len(servers) == len(manager.servers)

    # Verify that __aexit__ was called on all servers in reverse order
    for server in reversed(manager.servers):
        server.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_manager_async_context_manager_exception():
    """Test MCPServerManager async context manager with exception."""
    config = {
        "test-server": {
            "transport": "stdio",
            "command": "python",
            "args": ["-c", "print('hello')"],
        },
    }
    manager = MCPServerManager.from_config(config)

    # Mock the server's __aenter__ and __aexit__ methods
    server = manager.servers[0]
    server.__aenter__ = AsyncMock(return_value=server)
    server.__aexit__ = AsyncMock()

    # Use the manager as an async context manager with an exception
    try:
        async with manager:
            # Simulate an exception
            raise Exception("Test exception")
    except Exception:
        pass

    # Verify that __aexit__ was called on the server
    server.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_manager_call_tool(mixed_config):
    """Test MCPServerManager call_tool functionality."""
    manager = MCPServerManager.from_config(mixed_config)

    # Mock the servers' __aenter__ method to activate them
    for server in manager.servers:
        server.__aenter__ = AsyncMock(return_value=server)

    # Mock the stdio server's call_tool method
    stdio_server = manager.serversMap["test-stdio-server"]
    stdio_server.call_tool = AsyncMock(return_value=MagicMock())

    # Mock the sse server's call_tool method
    sse_server = manager.serversMap["mcp-time"]
    sse_server.call_tool = AsyncMock(return_value=MagicMock())

    # Use the manager as an async context manager to activate servers
    async with manager:
        # Test calling a tool on the stdio server
        await manager.call_tool(
            "test-stdio-server",
            "test_tool",
            {"param": "value"},
        )
        stdio_server.call_tool.assert_called_once_with(
            "test_tool",
            {"param": "value"},
        )

        # Test calling a tool on the sse server
        await manager.call_tool(
            "mcp-time",
            "test_tool",
            {"param": "value"},
        )  # noqa E501
        sse_server.call_tool.assert_called_once_with(
            "test_tool",
            {"param": "value"},
        )

        # Test calling a tool on a non-existent server
        with pytest.raises(KeyError):
            await manager.call_tool(
                "non-existent-server",
                "test_tool",
                {"param": "value"},
            )


@pytest.mark.asyncio
async def test_manager_list_tools(mixed_config):
    """Test MCPServerManager list_tools functionality."""
    manager = MCPServerManager.from_config(mixed_config)

    # Mock the servers' __aenter__ method to activate them
    for server in manager.servers:
        server.__aenter__ = AsyncMock(return_value=server)

    # Mock the sse server's list_tools method
    sse_server = manager.serversMap["mcp-time"]
    sse_server.list_tools = AsyncMock(return_value=[MagicMock()])

    # Use the manager as an async context manager to activate servers
    async with manager:

        # Test listing tools from the sse server
        tools2 = await manager.list_tools("mcp-time")
        sse_server.list_tools.assert_called_once()
        assert len(tools2) == 1

        # Test listing tools from a non-existent server
        with pytest.raises(KeyError):
            await manager.list_tools("non-existent-server")
