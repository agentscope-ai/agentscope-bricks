# -*- coding: utf-8 -*-
from langchain_core.messages import AIMessage, HumanMessage
from mcp import ClientSession
from mcp.types import PromptMessage
from typing import Any, Optional


def convert_mcp_prompt_message_to_langchain_message(
    message: PromptMessage,
) -> HumanMessage | AIMessage:
    """Convert an MCP prompt message to a LangChain message.

    Args:
        message (PromptMessage): MCP prompt message to convert

    Returns:
        HumanMessage | AIMessage: A LangChain message

    Raises:
        ValueError: If the message role or content type is unsupported.
    """
    if message.content.type == "text":
        if message.role == "user":
            return HumanMessage(content=message.content.text)
        elif message.role == "assistant":
            return AIMessage(content=message.content.text)
        else:
            raise ValueError(
                f"Unsupported prompt message role: {message.role}",
            )

    raise ValueError(
        f"Unsupported prompt message content type: {message.content.type}",
    )


async def load_mcp_prompt(
    session: ClientSession,
    name: str,
    arguments: Optional[dict[str, Any]] = None,
) -> list[HumanMessage | AIMessage]:
    """Load MCP prompt and convert to LangChain messages.

    Args:
        session (ClientSession): The MCP client session.
        name (str): The name of the prompt to load.
        arguments (Optional[dict[str, Any]]): Optional arguments for the
               prompt. Defaults to None.

    Returns:
        list[HumanMessage | AIMessage]: List of converted LangChain messages.
    """
    response = await session.get_prompt(name, arguments)
    return [
        convert_mcp_prompt_message_to_langchain_message(message)
        for message in response.messages
    ]
