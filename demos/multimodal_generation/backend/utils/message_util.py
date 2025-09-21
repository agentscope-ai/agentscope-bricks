# -*- coding: utf-8 -*-
import copy
import json
import re
from typing import (
    List,
    AsyncGenerator,
    Any,
    Dict,
    Optional,
    Union,
    Mapping,
    Callable,
)
from agentscope_bricks.utils.logger_util import logger

from openai.types.chat import ChatCompletionChunk

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage
from agentscope_bricks.utils.message_util import merge_incremental_chunk
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    Role,
    Content,
    TextContent,
    MessageType,
)


def parse_script(text: str) -> tuple[str, str, str]:
    """
    从脚本文字中提取核心产品和广告语。

    Args:
        text (str): 包含产品和广告语的脚本文字。

    Returns:
        tuple[str, str]: 一个包含产品名称和广告语的元组 (product, slogan)。
                         如果找不到，对应的值会是空字符串。
    """
    product_name = ""
    product_desc = ""
    slogan = ""

    product_name_match = re.search(r"产品名称：(.*)", text)
    if product_name_match:
        product_name = product_name_match.group(1).strip()

    product_desc_match = re.search(r"产品描述：(.*)", text)
    if product_desc_match:
        product_desc = product_desc_match.group(1).strip()

    slogan_match = re.search(r"产品标语：(.*)", text)
    if slogan_match:
        slogan = slogan_match.group(1).strip()

    return product_name, product_desc, slogan


def parse_storyboard(text: str) -> List[str]:
    """
    Parse storyboard text into individual storyboard items

    Args:
        text (str): The storyboard text to parse

    Returns:
        List[str]: List of individual storyboard item texts
    """
    # Split by "分镜" pattern to separate different storyboard items
    # Use regex to split by "分镜\d+：" pattern
    pattern = r"分镜\d+："
    parts = re.split(pattern, text)

    # Remove empty parts and clean up
    storyboard_items = []
    for part in parts:
        part = part.strip()
        if part:  # Only add non-empty parts
            storyboard_items.append(part)

    return storyboard_items


def parse_role_description(text: str) -> List[str]:
    """
    Parse role description text into individual role description items

    Args:
        text (str): The role description text to parse

    Returns:
        List[str]: List of individual role description item texts
    """
    # Split by "角色\d+：" pattern to separate different role items
    pattern = r"角色\d+："
    parts = re.split(pattern, text)

    # Remove empty parts and clean up
    role_items = []
    for part in parts:
        part = part.strip()
        if part:  # Only add non-empty parts
            role_items.append(part)

    return role_items


def parse_first_frame_description(text: str) -> List[str]:
    """
    Parse first frame description text into individual frame description items

    Args:
        text (str): The first frame description text to parse

    Returns:
        List[str]: List of individual frame description item texts
    """
    # Find all "分镜X：" patterns and their positions
    pattern = r"分镜\d+："
    matches = list(re.finditer(pattern, text))

    if not matches:
        # If no "分镜X：" pattern found, return the whole text as one item
        return [text.strip()] if text.strip() else []

    frame_items = []
    for i, match in enumerate(matches):
        start_pos = match.end()  # Position after "分镜X："

        if i + 1 < len(matches):
            # Not the last match, content goes until next "分镜X："
            end_pos = matches[i + 1].start()
            content = text[start_pos:end_pos].strip()
        else:
            # Last match, content goes to the end
            content = text[start_pos:].strip()

        if content:  # Only add non-empty content
            frame_items.append(content)

    return frame_items


def parse_video_description(text: str) -> List[str]:
    """
    Parse video description text into individual video description items

    Args:
        text (str): The video description text to parse

    Returns:
        List[str]: List of individual video description item texts
    """
    # Find all "视频X：" patterns and their positions
    pattern = r"视频\d+："
    matches = list(re.finditer(pattern, text))

    if not matches:
        # If no "视频X：" pattern found, return the whole text as one item
        return [text.strip()] if text.strip() else []

    video_items = []
    for i, match in enumerate(matches):
        start_pos = match.end()  # Position after "视频X："

        if i + 1 < len(matches):
            # Not the last match, content goes until next "视频X："
            end_pos = matches[i + 1].start()
            content = text[start_pos:end_pos].strip()
        else:
            # Last match, content goes to the end
            content = text[start_pos:].strip()

        if content:  # Only add non-empty content
            video_items.append(content)

    return video_items


def parse_line(text: str) -> List[str]:
    """
    Parse line text into individual role, dialogue and voice items

    Args:
        text (str): The line text to parse

    Returns:
        List[str]: List of individual role, dialogue and voice texts
    """
    # Find all "分镜X：" patterns and their positions
    pattern = r"分镜\d+："
    matches = list(re.finditer(pattern, text))

    if not matches:
        # If no "分镜X：" pattern found, return empty list
        return []

    line_items = []
    for i, match in enumerate(matches):
        start_pos = match.end()  # Position after "分镜X："

        if i + 1 < len(matches):
            # Not the last match, content goes until next "分镜X："
            end_pos = matches[i + 1].start()
            content = text[start_pos:end_pos].strip()
        else:
            # Last match, content goes to the end
            content = text[start_pos:].strip()

        if content:
            # Parse role, dialogue and voice from this storyboard section
            role_match = re.search(r"角色：(.+?)(?=\n|$)", content)
            dialogue_match = re.search(r"旁白：(.+?)(?=\n|$)", content)
            voice_match = re.search(r"音色：(.+?)(?=\n|$)", content)

            if role_match and dialogue_match and voice_match:
                role = role_match.group(1).strip()
                dialogue = dialogue_match.group(1).strip()
                voice = voice_match.group(1).strip()
                line_items.extend([role, dialogue, voice])

    return line_items


async def process_response_chunk(
    resp: ChatCompletionChunk,
    output_message: Message,
    init_event: bool,
    content_index: Optional[int],
    cumulated: List[ChatCompletionChunk],
    tool_calls_result: bool = False,
    valid_components: Optional[Dict[str, Union[Component, Callable]]] = None,
    **kwargs: Any,
) -> AsyncGenerator[Union[Message, Content], None]:
    """
    Process a single response chunk from LLM stream and yield appropriate
    messages and content.

    Args:
        resp: The chat completion chunk response to process
        init_event: Whether this is the initial event in the stream
        output_message: The message object being built from the stream
        content_index: Current content index for delta content
        cumulated: List of accumulated response chunks
        tool_calls_result: Whether tool calls have been processed
        valid_components: Optional mapping of available tool components
        **kwargs: Additional keyword arguments for tool execution

    Yields:
        Union[Message, Content]: Message objects or content deltas
    """

    # generate init message
    if init_event:
        if (
            resp.choices[0].delta.tool_calls
            and resp.choices[0].finish_reason != "tool_calls"
        ):
            output_message.type = MessageType.FUNCTION_CALL
        else:
            output_message.role = Role.ASSISTANT
            output_message.type = MessageType.MESSAGE

        init_event = False

        yield (
            output_message.in_progress(),
            output_message,
            init_event,
            content_index,
            cumulated,
        )

    # cumulate resp
    cumulated.append(resp)

    # Process delta content first for streaming
    if resp.choices and resp.choices[0].delta.content:
        # Create delta content for streaming
        delta_content = Content.from_chat_completion_chunk(
            resp,
            content_index,
        )
        if delta_content:
            # Set status to in_progress for proper streaming
            delta_content.status = "in_progress"
            # Set msg_id to link with the message
            delta_content.msg_id = output_message.id
            delta_content = output_message.add_delta_content(
                new_content=delta_content,
            )
            content_index = delta_content.index
            yield (
                delta_content,
                output_message,
                init_event,
                content_index,
                cumulated,
            )

    # record usage for text message
    if resp.usage and output_message.type == MessageType.MESSAGE:
        yield output_message.content_completed(
            content_index,
        ), output_message, init_event, content_index, cumulated
        output_message.usage = resp.usage.model_dump()
        yield (
            output_message.completed(),
            output_message,
            init_event,
            content_index,
            cumulated,
        )
        return

    # record usage for tool call
    elif (
        resp.usage
        and output_message.type == MessageType.FUNCTION_CALL
        and tool_calls_result
    ):
        delta_content = output_message.content_completed(
            content_index,
        )
        yield (
            delta_content,
            output_message,
            init_event,
            content_index,
            cumulated,
        )
        output_message.usage = resp.usage.model_dump()
        yield (
            output_message.completed(),
            output_message,
            init_event,
            content_index,
            cumulated,
        )

        # tool execution
        if valid_components:
            tool_responses: List[OpenAIMessage] = []
            if len(tool_responses) > 1:
                # TODO: only support one tool response
                tool_output_message = Message.from_openai_message(
                    tool_responses[1],
                )
                yield (
                    tool_output_message.completed(),
                    output_message,
                    init_event,
                    content_index,
                    cumulated,
                )

    # return when no response choices and handled usage
    if not resp.choices:
        return

    if len(resp.choices) > 0 and resp.choices[0].finish_reason == "tool_calls":
        tool_calls_result = True


def get_message_text_content(message: Message) -> Optional[str]:
    """
    Extract the first text content from the message.

    :return: First text string found in the content, or None if no text
    content
    """
    if message.content is None:
        return None

    for item in message.content:
        if isinstance(item, TextContent):
            return item.text
    return None


def get_message_image_content(message: Message) -> Optional[str]:
    """
    Extract the first image content from the message.

    :return: First image URL or data found in the content, or None if no image
    content
    """
    if message.content is None:
        return None

    for item in message.content:
        # Check if the item has image_url attribute (for image content)
        if hasattr(item, "image_url") and item.image_url:
            if isinstance(item.image_url, str):
                return item.image_url
    return None


def unpack_message(input_message: Message) -> Optional[Message]:
    """
    Unpack a message from JSON string format back to a Message object.

    Args:
        input_message: The message containing JSON string in its text content

    Returns:
        A new Message object reconstructed from the JSON string, or None if
        input is invalid or cannot be parsed
    """
    if input_message is None:
        return None

    # Extract text content from input message
    text_content = get_message_text_content(input_message)
    if text_content is None:
        return None

    # Parse JSON string back to dict
    message_dict = json.loads(text_content)

    # Create new Message object from dict
    output_message = Message(**message_dict)

    return output_message


def pack_message(input_message: Message) -> Optional[Message]:
    """
    Pack a message into JSON string format within a new output message.

    Args:
        input_message: The message to be packed into JSON format

    Returns:
        A new Message containing the JSON string representation of the
        input message in its text content, or None if input is invalid
    """
    if input_message is None:
        return None

    # Convert message to dict with safe handling of complex objects
    # Use mode='json' to ensure proper serialization without warnings
    message_dict = input_message.model_dump(
        exclude_unset=True,
        exclude_none=False,
        mode="json",
    )
    message_string = json.dumps(message_dict, ensure_ascii=False)

    # Create new message directly to avoid model_copy serialization warnings
    # Only copy essential fields to prevent Pydantic validation issues
    output_message = Message(
        id=input_message.id,
        role=input_message.role,
        type=MessageType.MESSAGE,
        content=[TextContent(text=message_string)],
        status=getattr(input_message, "status", None),
        code=getattr(input_message, "code", None),
        message=getattr(input_message, "message", None),
        usage=getattr(input_message, "usage", None),
    )

    return output_message
