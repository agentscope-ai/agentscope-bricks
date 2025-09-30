# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Type, Optional

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    ImageContent,
    DataContent,
)
from agentscope_bricks.utils.logger_util import logger
from demos.multimodal_generation.backend.common.handler import Handler
from demos.multimodal_generation.backend.common.stage_manager import (
    StageSession,
    Stage,
    STAGE_ORDER,
)


async def test_handler(
    handler_class: Type[Handler],
    input_message: Message,
    stage_session: StageSession,
) -> None:
    try:
        logger.info("=== Handler Started ===")

        handler = handler_class(stage_session)

        async for response in handler.handle(input_message):
            logger.info(
                "handler response: %s"
                % json.dumps(response.model_dump(), ensure_ascii=False),
            )
        # Convert Message objects to dict for JSON serialization
        stages_data = {}
        for stage, message in stage_session.get_all_stages().items():
            stages_data[stage] = (
                message.model_dump()
                if hasattr(message, "model_dump")
                else str(message)
            )
        logger.info(
            "stage session: %s",
            json.dumps(stages_data, ensure_ascii=False),
        )
        logger.info("=== Handler Completed ===")
    except Exception as e:
        logger.error(f"handler execution error: {e}")


def mock_stages() -> dict[Stage, Message]:
    """
    Load mock data from mock.json and convert to the expected return type

    Returns:
        dict[Stage, Message]: Dictionary Stage to Message
    """
    # Get the directory of current file to build relative path
    current_dir = Path(__file__).parent
    mock_json_path = current_dir / "mock.json"

    # Load mock data from JSON file
    try:
        with open(mock_json_path, "r", encoding="utf-8") as f:
            mock_stages_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Mock data file not found: {mock_json_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing mock data JSON: {e}")
        return {}

    result = {}

    for stage_name, msg_data in mock_stages_data.items():
        # Convert stage name to Stage enum
        try:
            stage = Stage(stage_name)
        except ValueError:
            # Skip invalid stage names
            continue

        # Create content list
        content_list = []
        if msg_data.get("content"):
            for content_data in msg_data["content"]:
                content_type = content_data["type"]

                if content_type == "text":
                    content = TextContent(
                        type="text",
                        object="content",
                        text=content_data.get("text", ""),
                        index=content_data.get("index"),
                        delta=content_data.get("delta", False),
                        msg_id=content_data.get("msg_id"),
                    )
                elif content_type == "image":
                    content = ImageContent(
                        type="image",
                        object="content",
                        image_url=content_data.get("image_url"),
                        index=content_data.get("index"),
                        delta=content_data.get("delta", False),
                        msg_id=content_data.get("msg_id"),
                    )
                else:
                    # Handle nested content in data field (like image in data)
                    if content_type == "data" and content_data.get("data"):
                        nested_data = content_data["data"]
                        nested_type = nested_data.get("type")

                        if nested_type == "image":
                            content = ImageContent(
                                type="image",
                                object="content",
                                image_url=nested_data.get("image_url"),
                                index=nested_data.get("index"),
                                delta=nested_data.get("delta", False),
                                msg_id=nested_data.get("msg_id"),
                            )
                        else:
                            content = DataContent(
                                type="data",
                                object="content",
                                data=nested_data,
                                index=nested_data.get("index"),
                                delta=nested_data.get("delta", False),
                                msg_id=nested_data.get("msg_id"),
                            )
                    else:
                        content = DataContent(
                            type="data",
                            object="content",
                            data=content_data,
                            index=content_data.get("index"),
                            delta=content_data.get("delta", False),
                            msg_id=content_data.get("msg_id"),
                        )
                content_list.append(content)

        # Create Message object
        message = Message(
            id=msg_data.get("id", ""),
            object=msg_data.get("object", "message"),
            type=msg_data.get("type", "message"),
            status=msg_data.get("status", "created"),
            role=msg_data.get("role"),
            content=content_list,
            code=msg_data.get("code"),
            message=msg_data.get("message"),
            usage=msg_data.get("usage"),
        )

        result[stage] = message

    return result


def mock_stage_session(
    session_id: Optional[str] = None,
    stage: Optional[Stage] = None,
) -> StageSession:
    """
    Create a mock StageSession object with mock data

    Args:
        session_id: Optional session ID to use. If None, uses default
                    "mock_session_id".
        stage: Optional dictionary of stages to include in the session.
                If None, creates an empty session.

    Returns:
        StageSession: Mock StageSession object
    """
    if session_id is None:
        session_id = "mock_session_id"

    stage_session = StageSession(session_id)

    if stage:
        input_stages = {}
        all_stages = mock_stages()

        for stage_name in STAGE_ORDER:
            if stage_name == stage:
                break
            if stage_name in all_stages:
                input_stages[stage_name] = all_stages[stage_name]

        stage_session.set_all_stages(input_stages)

    return stage_session


async def main():
    """
    Main function to execute multiple handlers in sequence
    """
    from demos.multimodal_generation.backend.common.stage_manager import (
        STAGE_ORDER,
        Stage,
    )
    from demos.multimodal_generation.backend.common.handler_factory import (
        _handler_map,
    )

    stage_session = mock_stage_session(stage=Stage.SCRIPT)

    initial_message = stage_session.get_stage_message(Stage.TOPIC)

    logger.info("=== Starting Film Generation Pipeline ===")

    # Execute handlers in sequence according to STAGE_ORDER
    for stage in STAGE_ORDER:
        logger.info(f"=== Executing {stage} Handler ===")

        handler_class = _handler_map[stage]

        if handler_class is None:
            continue

        try:
            await test_handler(handler_class, initial_message, stage_session)

        except Exception as e:
            logger.error(f"Error executing {stage} handler: {e}")
            # Continue with next stage even if current one fails
            break

    logger.info("=== Film Generation Pipeline Completed ===")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
