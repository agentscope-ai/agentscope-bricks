# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

import os
from shutil import rmtree

if os.path.exists("./build"):
    rmtree("./build")
if os.path.exists("./modelstudio_mcp_server.egg-info"):
    rmtree("./modelstudio_mcp_server.egg-info")

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="modelstudio-mcp-server",
    version="0.1.1.1",
    description="Modelstudio MCP Server runner with uvicorn support",
    long_description="A Model Context Protocol (MCP) server for Modelstudio "
    "services, supporting both direct execution and uvicorn "
    "deployment",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "modelstudio-mcp-server=modelstudio_mcp_server.mcp_server:main",
        ],
    },
    include_package_data=True,
)
