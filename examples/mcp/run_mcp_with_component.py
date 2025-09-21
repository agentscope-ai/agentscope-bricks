# -*- coding: utf-8 -*-
from mcp.server.fastmcp import FastMCP

from agentscope_bricks.mcp_utils.mcp_wrapper import MCPWrapper
from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
)

# Create an MCP server
mcp = FastMCP("ComponentDemo")

# Wrap and add the SearchComponent
MCPWrapper(mcp, ModelstudioSearchLite).wrap(
    "search_component",
    "Search Component For Example",
)
print("MCP server is running...")
mcp.run()

# try to debug the mcp server with mcp inspector with following command
""" shell
cd /path/of/modelstudiosdk
npx @modelcontextprotocol/inspector python
agentscope_bricks/mcp_for_plugin_center.py -e TASK=xxx -e
PYTHONPATH=/path/of/modelstudiosdk
"""

# try to connect to host of claude desktop or goose with following
"""
uv run /path/of/modelstudiosdk/agentscope_bricks/mcp_utis.py
or
python /path/of/modelstudiosdk/agentscope_bricks/mcp_utils.py
"""
