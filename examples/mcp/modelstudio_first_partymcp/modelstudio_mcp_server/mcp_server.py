# -*- coding: utf-8 -*-
# pylint:disable=no-untyped-def

import os
import sys
from mcp.server.fastmcp import FastMCP

from agentscope_bricks.components import mcp_server_metas
from agentscope_bricks.mcp_utils.mcp_wrapper import MCPWrapper

"""
启动 agentscope_bricks/components/__init__.py 内提供的modelstudio平台一方server源码
"""


def main() -> None:

    # get from args
    server_name = None
    for i, arg in enumerate(sys.argv):
        print(sys.argv[i])
        print(sys.argv)
        if arg == "--server" and i + 1 < len(sys.argv):
            server_name = sys.argv[i + 1]
            break

    # get from env
    if not server_name:
        server_name = os.getenv("SERVER_NAME", None)

    all_server_names = set(mcp_server_metas.keys())
    if not server_name:
        print(
            f"Please specify the server name with --server <server_name>, "
            f"support servers are {list(all_server_names)}",
        )
        sys.exit(1)

    if server_name not in mcp_server_metas:
        print(
            f"Invalid server name '{server_name}',"
            f" Available servers: {list(all_server_names)}",
        )
        sys.exit(1)

    port = os.getenv("PORT", 8080)
    host = os.getenv("HOST", "0.0.0.0")

    # Get server metadata
    server_meta = mcp_server_metas[server_name]

    # Override server name and description if specified
    mcp_server_name = os.getenv("OVERRIDE_NAME", server_name)
    mcp_server_instructions = os.getenv(
        "OVERRIDE_DESCRIPTION",
        server_meta.instructions,
    )

    # Create an MCP server
    mcp = FastMCP(
        name=mcp_server_name,
        instructions=mcp_server_instructions,
        port=port,
        host=host,
    )

    # Register each component as a tool
    for component in server_meta.components:
        MCPWrapper(mcp, component).wrap(component.name, component.description)
        print(f"Added tool: {component.name}")

    print("MCP server is running...")

    # get mcp transport type
    transport_type = os.getenv("TRANSPORT", "sse")
    mcp.run(transport=transport_type)


if __name__ == "__main__":
    main()

# usage
"""shell
pip install https://bailian-cn-beijing.oss-cn-beijing.aliyuncs.com/sdk
/modelstudiosdk-0.4.4a0-py3-none-any.whl
npx @modelcontextprotocol/inspector python mcp_server.py
-e SERVER_NAME=modelstudio_wan_image -e MODEL_NAME=wanx2.1-t2i-turbo -e
DASHSCOPE_API_KEY=sk-x -e TRANSPORT=stdio -e OVERRIDE_NAME=custom_name
-e OVERRIDE_DESCRIPTION="Custom server description for MCP inspector"

# Available server names: modelstudio_wan_image, modelstudio_wan_video,
# modelstudio_qwen_image, modelstudio_web_search
"""
