# -*- coding: utf-8 -*-
from __future__ import annotations

import abc
import asyncio
import os
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from pathlib import Path
from typing import Any, List, Literal, cast, Dict

from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from mcp import ClientSession, StdioServerParameters
from mcp import Tool as MCPTool
from mcp import stdio_client
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, JSONRPCMessage
from typing_extensions import NotRequired, TypedDict


class MCPServer(abc.ABC):
    """Base class for Model Context Protocol servers."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Abstract metho of connecting to the server.

        For example, this might mean spawning a subprocess or opening a network
        connection. The server is expected to remain connected until
        `cleanup()` is called.

        Raises:
            Exception: If connection fails.
        """
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """A readable name for the server.

        Returns:
            str: The server name.
        """
        pass

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """Cleanup the server.

        For example, this might mean closing a subprocess or closing a network
        connection.

        Raises:
            Exception: If cleanup fails.
        """
        pass

    @abc.abstractmethod
    async def list_tools(self) -> list[MCPTool]:
        """List the tools available on the server.

        Returns:
            list[MCPTool]: List of available tools.

        Raises:
            Exception: If listing tools fails.
        """
        pass

    @abc.abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
    ) -> CallToolResult:
        """Invoke a tool on the server.

        Args:
            tool_name (str): Name of the tool to invoke.
            arguments (dict[str, Any] | None): Arguments to pass to the tool.

        Returns:
            CallToolResult: Result of the tool invocation.

        Raises:
            Exception: If tool invocation fails.
        """
        pass


class _MCPServerWithClientSession(MCPServer, abc.ABC):
    """Base class for MCP servers that use a `ClientSession` to communicate
    with the server."""

    def __init__(self, cache_tools_list: bool) -> None:
        """Initialize the server with client session.

        Args:
            cache_tools_list (bool): Whether to cache the tools list. If
                `True`, the tools list will be cached and only fetched from the
                server once. If `False`, the tools list will be fetched from
                the server  on each call to `list_tools()`. The cache can be
                invalidated by calling `invalidate_tools_cache()`. You
                should set this to `True` if you know the server will not
                change its tools list, because it can drastically improve
                latency (by avoiding a round-trip to the
                server every time).
        """
        self.session: ClientSession | None = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.cache_tools_list = cache_tools_list

        # The cache is always dirty at startup, so that we fetch tools at
        # least once
        self._cache_dirty = True
        self._tools_list: list[MCPTool] = []

    @abc.abstractmethod
    def create_streams(
        self,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[JSONRPCMessage | Exception],
            MemoryObjectSendStream[JSONRPCMessage],
        ]
    ]:
        """Create the streams for the server.

        Returns:
            AbstractAsyncContextManager: Context manager for the streams.
        """
        pass

    async def __aenter__(self) -> _MCPServerWithClientSession:
        """Enter the async context manager.

        Returns:
            _MCPServerWithClientSession: Self instance.

        Raises:
            Exception: If connection fails.
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        """Exit the async context manager.

        Args:
            exc_type (Any): Exception type.
            exc_value (Any): Exception value.
            traceback (Any): Exception traceback.
        """
        await self.cleanup()

    def invalidate_tools_cache(self) -> None:
        """Invalidate the tools cache.

        This will force the next call to `list_tools()` to fetch tools from
        the server instead of using the cached version.
        """
        self._cache_dirty = True

    async def connect(self) -> None:
        """Connect to the server.

        Raises:
            Exception: If connection initialization fails.
        """
        try:
            transport = await self.exit_stack.enter_async_context(
                self.create_streams(),
            )
            read, write = transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write),
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            print(f"Error initializing MCP server: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> list[MCPTool]:
        """List the tools available on the server.

        Returns:
            list[MCPTool]: List of available tools.

        Raises:
            RuntimeError: If server is not initialized.
        """
        if not self.session:
            raise RuntimeError(
                "Server not initialized. Make sure call `connect()` first.",
            )

        # Return from cache if caching is enabled, we have tools, and the
        # cache is not dirty
        if (
            self.cache_tools_list
            and not self._cache_dirty
            and self._tools_list
        ):
            return self._tools_list

        # Reset the cache dirty to False
        self._cache_dirty = False

        # Fetch the tools from the server
        self._tools_list = (await self.session.list_tools()).tools
        return self._tools_list

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
    ) -> CallToolResult:
        """Invoke a tool on the server.

        Args:
            tool_name (str): Name of the tool to invoke.
            arguments (dict[str, Any] | None): Arguments to pass to the tool.

        Returns:
            CallToolResult: Result of the tool invocation.

        Raises:
            RuntimeError: If server is not initialized.
        """
        if not self.session:
            raise RuntimeError(
                "Server not initialized. Make sure call `connect()` first.",
            )

        return await self.session.call_tool(tool_name, arguments)

    async def cleanup(self) -> None:
        """Cleanup the server.

        This method safely closes all resources and connections.
        """
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
            except Exception as e:
                print(f"Error cleaning up server: {e}")


class MCPServerStdioParams(TypedDict):
    """Mirrors `mcp.client.stdio.StdioServerParameters`, but lets you pass
    params without another
    import.
    """

    command: str
    """The executable to run to start the server. For example, `python` or
    `node`."""

    args: NotRequired[list[str]]
    """Command line args to pass to the `command` executable. For example,
    `['foo.py']` or
    `['server.js', '--port', '8080']`."""

    env: NotRequired[dict[str, str]]
    """The environment variables to set for the server. ."""

    cwd: NotRequired[str | Path]
    """The working directory to use when spawning the process."""

    encoding: NotRequired[str]
    """The text encoding used when sending/receiving messages to the server.
    Defaults to `utf-8`."""

    encoding_error_handler: NotRequired[Literal["strict", "ignore", "replace"]]
    """The text encoding error handler. Defaults to `strict`.

    See https://docs.python.org/3/library/codecs.html#codec-base-classes for
    explanations of possible values.
    """


class MCPServerStdio(_MCPServerWithClientSession):
    """MCP server implementation that uses the stdio transport. See the [spec]
    (https://spec.modelcontextprotocol.io/specification/2024-11-05/basic
    /transports/#stdio)
    for details.
    """

    def __init__(
        self,
        params: MCPServerStdioParams,
        cache_tools_list: bool = False,
        name: str | None = None,
    ) -> None:
        """Create a new MCP server based on the stdio transport.

        Args:
            params (MCPServerStdioParams): The params that configure the
                server. This includes the command to run to start the
                server, the args to pass to the command, the environment
                variables to set for the server, the working directory to
                use when spawning the process, and the text encoding used
                when sending/receiving messages to the server.
            cache_tools_list (bool, optional): Whether to cache the tools list.
                If `True`, the tools list will be cached and only fetched from
                the server once. If `False`, the tools list will be fetched
                from the server on each call to `list_tools()`. The cache
                can be invalidated by calling `invalidate_tools_cache()`.
                You should set this to `True` if you know the server will
                not change its tools list, because it can drastically
                improve latency (by avoiding a round-trip to the server every
                time). Defaults to False.
            name (str | None, optional): A readable name for the server. If not
                provided, we'll create one from the command. Defaults to None.
        """
        super().__init__(cache_tools_list)

        self.params = StdioServerParameters(
            command=params["command"],
            args=params.get("args", []),
            env=params.get("env"),
            cwd=params.get("cwd"),
            encoding=params.get("encoding", "utf-8"),
            encoding_error_handler=params.get(
                "encoding_error_handler",
                "strict",
            ),
        )

        self._name = name or f"stdio: {self.params.command}"

    def create_streams(
        self,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[JSONRPCMessage | Exception],
            MemoryObjectSendStream[JSONRPCMessage],
        ]
    ]:
        """Create the streams for the server.

        Returns:
            AbstractAsyncContextManager: Context manager for stdio client
            streams.
        """
        return stdio_client(self.params)

    @property
    def name(self) -> str:
        """A readable name for the server.

        Returns:
            str: The server name.
        """
        return self._name

    def to_dict(self) -> dict:
        """Convert the server to a dictionary for JSON serialization.

        Returns:
            dict: Dictionary representation of the server configuration.
        """
        return {
            "name": self._name,
            "type": "stdio",
            "command": self.params.command,
            "args": self.params.args,
            "cwd": str(self.params.cwd) if self.params.cwd else None,
        }

    def __json__(self) -> dict:
        """Method for custom JSON serialization.

        Returns:
            dict: Dictionary representation for JSON serialization.
        """
        return self.to_dict()


class MCPServerSseParams(TypedDict):
    """Mirrors the params in`mcp.client.sse.sse_client`."""

    url: str
    """The URL of the server."""

    headers: NotRequired[dict[str, str]]
    """The headers to send to the server."""

    timeout: NotRequired[float]
    """The timeout for the HTTP request. Defaults to 5 seconds."""

    sse_read_timeout: NotRequired[float]
    """The timeout for the SSE connection, in seconds. Defaults to 5
    minutes."""


class MCPServerSse(_MCPServerWithClientSession):
    """MCP server implementation that uses the HTTP with SSE transport. See
    the [spec]
    (https://spec.modelcontextprotocol.io/specification/2024-11-05/basic
    /transports/#http-with-sse)
    for details.
    """

    def __init__(
        self,
        params: MCPServerSseParams,
        cache_tools_list: bool = False,
        name: str | None = None,
    ) -> None:
        """Create a new MCP server based on the HTTP with SSE transport.

        Args:
            params (MCPServerSseParams): The params that configure the server.
                This includes the URL of the server, the headers to send to the
                server, the timeout for the HTTP request, and the timeout for
                the SSE connection.
            cache_tools_list (bool, optional): Whether to cache the tools list.
                If `True`, the tools list will be cached and only fetched from
                the server once. If `False`, the tools list will be fetched
                from the server on each call to `list_tools()`. The cache
                can be invalidated by calling `invalidate_tools_cache()`.
                You should set this to `True` if you know the server will
                not change its tools list, because it can drastically
                improve latency (by avoiding a round-trip to the server every
                time). Defaults to False.
            name (str | None, optional): A readable name for the server. If not
                provided, we'll create one from the URL. Defaults to None.
        """
        super().__init__(cache_tools_list)

        self.params = params
        self._name = name or f"sse: {self.params['url']}"

    def create_streams(
        self,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[JSONRPCMessage | Exception],
            MemoryObjectSendStream[JSONRPCMessage],
        ]
    ]:
        """Create the streams for the server.

        Returns:
            AbstractAsyncContextManager: Context manager for SSE client
            streams.
        """
        return sse_client(
            url=self.params["url"],
            headers=self.params.get("headers", None),
            timeout=self.params.get("timeout", 5),
            sse_read_timeout=self.params.get("sse_read_timeout", 60 * 5),
        )

    @property
    def name(self) -> str:
        """A readable name for the server.

        Returns:
            str: The server name.
        """
        return self._name

    def to_dict(self) -> dict:
        """Convert the server to a dictionary for JSON serialization.

        Returns:
            dict: Dictionary representation of the server configuration.
        """
        return {
            "name": self._name,
            "type": "sse",
            "url": self.params["url"],
        }

    def __json__(self) -> dict:
        """Method for custom JSON serialization.

        Returns:
            dict: Dictionary representation for JSON serialization.
        """
        return self.to_dict()


class MCPServerManager:
    """Manager class for handling multiple MCP servers.

    The servers can be initialized from a JSON config file with the following
    format: {
        "server_name": {
            "command": "python", "args": ["/path/to/script.py"], "transport":
            "stdio"
        }, "another_server": {
            "url": "http://localhost:8000/sse", "transport": "sse"
        }
    }
    """

    def __init__(self, servers: list[MCPServer]) -> None:
        """Initialize the server manager with a list of MCP servers.

        Args:
            servers (list[MCPServer]): List of MCPServer instances to manage.
        """
        self.servers = servers
        self.serversMap = {server.name: server for server in servers}
        self.active_servers = []

    @classmethod
    def from_config(cls, config: dict[str, dict]) -> "MCPServerManager":
        """Create a MCPServerManager instance from a config dictionary.

        Args:
            config (dict[str, dict]): A dictionary mapping server names to
                their configurations. Each configuration must have a
                'transport' field specifying either 'stdio' or 'sse',
                along with the appropriate parameters for that transport type.

        Returns:
            MCPServerManager: A new MCPServerManager instance initialized with
                the configured servers.

        Raises:
            ValueError: If the config format is invalid or missing required
                fields.
        """
        servers: List[MCPServer] = []
        for server_name, server_config in config.items():
            # 兼容部分"type"key
            if "type" in server_config:
                server_config["transport"] = server_config["type"]
            if "baseUrl" in server_config:
                server_config["url"] = server_config["baseUrl"]

            # bailian mcp host server导入场景进行dashscopeApiKey替换
            if (
                "headers" in server_config
                and "Authorization" in server_config["headers"]
            ):
                auth_header = server_config["headers"]["Authorization"]
                if "${DASHSCOPE_API_KEY}" in auth_header:
                    server_config["headers"]["Authorization"] = (
                        auth_header.replace(
                            "${DASHSCOPE_API_KEY}",
                            os.getenv(
                                "DASHSCOPE_API_KEY",
                                "${DASHSCOPE_API_KEY}",
                            ),
                        )
                    )

            if "transport" not in server_config:
                raise ValueError(
                    f"Missing 'transport' field in config for server '"
                    f"{server_name}'",
                )

            transport = server_config["transport"]
            server_config = server_config.copy()
            del server_config["transport"]

            if transport == "stdio":
                if "command" not in server_config:
                    raise ValueError(
                        f"Missing 'command' field in stdio config for server '{server_name}'",  # noqa E501
                    )
                if "args" not in server_config:
                    server_config["args"] = []

                servers.append(
                    MCPServerStdio(
                        params=cast(MCPServerStdioParams, server_config),
                        name=server_name,
                    ),
                )

            elif transport == "sse":
                if "url" not in server_config:
                    raise ValueError(
                        f"Missing 'url' field in sse config for server '{server_name}'",  # noqa E501
                    )

                servers.append(
                    MCPServerSse(
                        params=cast(MCPServerSseParams, server_config),
                        name=server_name,
                    ),
                )

            else:
                raise ValueError(
                    f"Invalid transport '{transport}' for server '"
                    f"{server_name}'. Must be 'stdio' or 'sse'",
                )
        return cls(servers)

    @classmethod
    def from_config_file(cls, config_path: str | Path) -> "MCPServerManager":
        """Create a MCPServerManager instance from a JSON config file.

        Args:
            config_path (str | Path): Path to the JSON config file.

        Returns:
            MCPServerManager: A new MCPServerManager instance initialized with
                the configured servers.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            JSONDecodeError: If the config file contains invalid JSON.
            ValueError: If the config format is invalid or missing required
                fields.
        """
        import json
        from pathlib import Path

        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = json.load(f)

        return cls.from_config(config)

    async def __aenter__(self) -> list[MCPServer]:
        """Activate all servers when entering the context.

        Returns:
            list[MCPServer]: List of activated servers.

        Raises:
            Exception: If any server fails to activate.
        """
        for server in self.servers:
            print(server.name)
            self.active_servers.append(await server.__aenter__())
        return self.active_servers

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Cleanup all servers when exiting the context.

        Args:
            exc_type (Any): Exception type.
            exc_val (Any): Exception value.
            exc_tb (Any): Exception traceback.
        """
        for server in reversed(self.servers):
            await server.__aexit__(exc_type, exc_val, exc_tb)

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> CallToolResult:
        """Invoke a tool on a specific server managed by this manager.

        Args:
            server_name (str): Name of the server to invoke the tool on.
            tool_name (str): Name of the tool to invoke.
            arguments (dict[str, Any] | None): Arguments to pass to the tool.

        Returns:
            CallToolResult: Result of the tool invocation.

        Raises:
            KeyError: If the server with the given name is not found.
        """
        if server_name not in self.serversMap:
            raise KeyError(f"Server '{server_name}' not found in manager")

        server = self.serversMap[server_name]
        return await server.call_tool(tool_name, arguments)

    async def list_tools(self, server_name: str) -> list[MCPTool]:
        """List the tools available on a specific server managed by this
        manager.

        Args:
            server_name (str): Name of the server to list tools from.

        Returns:
            list[MCPTool]: List of available tools on the specified server.

        Raises:
            KeyError: If the server with the given name is not found.
        """
        if server_name not in self.serversMap:
            raise KeyError(f"Server '{server_name}' not found in manager")

        server = self.serversMap[server_name]
        return await server.list_tools()
