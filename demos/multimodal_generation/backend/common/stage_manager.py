# -*- coding: utf-8 -*-
from enum import Enum
from typing import Optional

from agentscope_runtime.engine.schemas.agent_schemas import (
    TextContent,
    Message,
)

from demos.multimodal_generation.backend.utils.message_util import (
    parse_storyboard,
    parse_role_description,
    parse_first_frame_description,
    parse_video_description,
    parse_line,
    get_message_text_content,
    get_message_image_content,
)


class Stage(str, Enum):
    TOPIC = "Topic"
    SCRIPT = "Script"
    STORYBOARD = "Storyboard"
    ROLE_DESCRIPTION = "RoleDescription"
    ROLE_IMAGE = "RoleImage"
    FIRST_FRAME_DESCRIPTION = "FirstFrameDescription"
    FIRST_FRAME_IMAGE = "FirstFrameImage"
    VIDEO_DESCRIPTION = "VideoDescription"
    VIDEO = "Video"
    LINE = "Line"
    AUDIO = "Audio"
    FILM = "Film"


STAGE_ORDER = [
    Stage.TOPIC,
    Stage.SCRIPT,
    Stage.STORYBOARD,
    Stage.ROLE_DESCRIPTION,
    Stage.ROLE_IMAGE,
    Stage.FIRST_FRAME_DESCRIPTION,
    Stage.FIRST_FRAME_IMAGE,
    Stage.VIDEO_DESCRIPTION,
    Stage.VIDEO,
    Stage.LINE,
    Stage.AUDIO,
    Stage.FILM,
]


class StageSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.stages: dict[Stage, Message] = {}

    def get_session_id(self):
        """
        Get the session ID

        Returns:
            str: The session ID
        """
        return self.session_id

    def set_stage_message(self, stage: Stage, message: Message):
        """
        Set messages in a specific stage

        Args:
            stage (Stage): The stage to update message in
            message (Message): The updated message
        """
        self.stages[stage] = message

    def get_stage_message(self, stage: Stage) -> Optional[Message]:
        """
        Get messages from a specific stage

        Args:
            stage (Stage): The stage to get messages from

        Returns:
            Optional[Message]: The message from the specified stage
        """
        return self.stages.get(stage, None)

    def get_current_stage(self) -> Optional[Stage]:
        """
        Get the highest completed stage in the current session.

        Returns:
            Optional[Stage]: Highest completed stage in STAGE_ORDER or None
            if no stage has been completed yet.
        """
        if not self.stages:
            return None

        completed_stages = set(self.stages.keys())
        highest_completed_index = -1

        for i, stage in enumerate(STAGE_ORDER):
            if stage in completed_stages:
                highest_completed_index = i

        if highest_completed_index >= 0:
            return STAGE_ORDER[highest_completed_index]
        return None

    def delete_stage(self, stage: Stage) -> None:
        """
        Delete a specific stage from the current session

        Args:
            stage (Stage): The stage to delete

        Returns:
            bool: True if the stage was deleted, False if the stage
            was not found
        """
        if stage in self.stages:
            del self.stages[stage]

    def get_next_stage(self) -> Optional[Stage]:
        """
        Get the next stage based on the current completed stages

        Returns:
            Optional[Stage]: The next stage in STAGE_ORDER
        """
        if not self.stages:
            # If no stages are completed, return the first stage
            return STAGE_ORDER[0] if STAGE_ORDER else None

        # Find the highest completed stage in STAGE_ORDER
        completed_stages = set(self.stages.keys())
        highest_completed_index = -1

        for i, stage in enumerate(STAGE_ORDER):
            if stage in completed_stages:
                highest_completed_index = i

        # Return the next stage if not at the end
        if 0 <= highest_completed_index < len(STAGE_ORDER) - 1:
            return STAGE_ORDER[highest_completed_index + 1]
        else:
            return None  # Already at the last stage or no stages completed

    def set_all_stages(self, stages: dict[Stage, Message]) -> None:
        """
        Set all stages in the current session

        Args:
            stages (dict[Stage, Message]): The updated stages
        """
        self.stages = stages

    def get_all_stages(self) -> dict[Stage, Message]:
        """
        Get all stages in the current session

        Returns:
            dict[Stage, Message]: All stages in the current session
        """
        return self.stages

    def get_topic(self) -> Optional[tuple[str, str]]:
        topic_message = self.stages.get(Stage.TOPIC)
        if not topic_message:
            raise ValueError("No topic message found in stages")

        topic_text = get_message_text_content(topic_message)
        topic_image = get_message_image_content(topic_message)

        return topic_text, topic_image

    def get_script(self) -> Optional[str]:
        script_message = self.stages.get(Stage.SCRIPT)
        if not script_message:
            raise ValueError("No script message found in stages")

        script = script_message.content[0].data["script"]

        return "剧情如下:\n" + script

    def set_storyboard(self, message: Message) -> None:
        """
        Set storyboard message by parsing the input message content

        Args:
            message (Message): The message containing storyboard content
        """
        if not message or not message.content:
            raise ValueError("Message content is empty")

        # Get the text content from the first content item
        first_content = message.content[0]
        if not isinstance(first_content, TextContent):
            raise ValueError("First content item is not TextContent")

        storyboard_text = first_content.text
        if not storyboard_text:
            raise ValueError("Storyboard text content is empty")

        # Parse the storyboard text into individual storyboard items
        storyboard_items = parse_storyboard(storyboard_text)

        storyboard_contents = []
        for i, item_text in enumerate(storyboard_items):
            text_content = TextContent(text=item_text, index=i)
            storyboard_contents.append(text_content)

        # Create a single Message with all storyboard contents
        storyboard_message = Message(
            content=storyboard_contents,
            role=message.role,
        )

        # Set the storyboard message in the stages
        self.set_stage_message(Stage.STORYBOARD, storyboard_message)

    def get_storyboard(self) -> Optional[str]:
        """
        Get storyboard message as formatted string

        Returns:
            Optional[str]: The formatted storyboard string with prefixes
        """
        storyboard_message = self.stages.get(Stage.STORYBOARD)
        if not storyboard_message:
            raise ValueError("No storyboard message found in stages")

        if not storyboard_message.content:
            raise ValueError("No content found in storyboard message")

        storyboard_parts = []
        for i, content in enumerate(storyboard_message.content, 1):
            if isinstance(content, TextContent) and content.text:
                prefix = f"分镜{i}"
                storyboard_parts.append(f"{prefix}：{content.text}")

        if not storyboard_parts:
            raise ValueError("No text content found in storyboard message")

        return "分镜如下\n\n" + "\n\n".join(storyboard_parts)

    def set_role_description(self, message: Message) -> None:
        """
        Set role description message by parsing the input message content

        Args:
            message (Message): The message containing role description content
        """
        if not message or not message.content:
            raise ValueError("Message content is empty")

        # Get the text content from the first content item
        first_content = message.content[0]
        if not isinstance(first_content, TextContent):
            raise ValueError("First content item is not TextContent")

        role_description_text = first_content.text
        if not role_description_text:
            raise ValueError("Role description text content is empty")

        # Parse the role description text into individual role items
        role_items = parse_role_description(role_description_text)

        role_contents = []
        for i, item_text in enumerate(role_items):
            text_content = TextContent(text=item_text, index=i)
            role_contents.append(text_content)

        # Create a single Message with all role description contents
        role_message = Message(
            content=role_contents,
            role=message.role,
        )

        # Set the role description message in the stages
        self.set_stage_message(Stage.ROLE_DESCRIPTION, role_message)

    def get_role_description(self) -> Optional[str]:
        """
        Get role description message as formatted string

        Returns:
            Optional[str]: The formatted role description string with prefixes
        """
        role_message = self.stages.get(Stage.ROLE_DESCRIPTION)
        if not role_message:
            raise ValueError("No role description message found in stages")

        if not role_message.content:
            raise ValueError("No content found in role description message")

        role_parts = []
        for i, content in enumerate(role_message.content, 1):
            if isinstance(content, TextContent) and content.text:
                prefix = f"角色{i}"
                role_parts.append(f"{prefix}：{content.text}")

        if not role_parts:
            raise ValueError(
                "No text content found in role description message",
            )

        return "角色描述如下\n\n" + "\n\n".join(role_parts)

    def set_first_frame_description(self, message: Message) -> None:
        """
        Set first frame description message by parsing the input message

        Args:
            message (Message): The message containing first frame description
        """
        if not message or not message.content:
            raise ValueError("Message content is empty")

        # Get the text content from the first content item
        first_content = message.content[0]
        if not isinstance(first_content, TextContent):
            raise ValueError("First content item is not TextContent")

        first_frame_text = first_content.text
        if not first_frame_text:
            raise ValueError("First frame description text content is empty")

        # Parse the first frame description text into individual frame items
        frame_items = parse_first_frame_description(first_frame_text)

        frame_contents = []
        for i, item_text in enumerate(frame_items):
            text_content = TextContent(text=item_text, index=i)
            frame_contents.append(text_content)

        # Create a single Message with all first frame description contents
        frame_message = Message(
            content=frame_contents,
            role=message.role,
        )

        # Set the first frame description message in the stages
        self.set_stage_message(Stage.FIRST_FRAME_DESCRIPTION, frame_message)

    def get_first_frame_description(self) -> Optional[str]:
        """
        Get first frame description message as formatted string

        Returns:
            Optional[str]: The formatted first frame description string
        """
        frame_message = self.stages.get(Stage.FIRST_FRAME_DESCRIPTION)
        if not frame_message:
            raise ValueError(
                "No first frame description message found in stages",
            )

        if not frame_message.content:
            raise ValueError(
                "No content found in first frame description message",
            )

        frame_parts = []
        for i, content in enumerate(frame_message.content, 1):
            if isinstance(content, TextContent) and content.text:
                prefix = f"首帧{i}"
                frame_parts.append(f"{prefix}：{content.text}")

        if not frame_parts:
            raise ValueError(
                "No text content found in first frame description message",
            )

        return "首帧描述如下\n\n" + "\n\n".join(frame_parts)

    def set_video_description(self, message: Message) -> None:
        """
        Set video description message by parsing the input message

        Args:
            message (Message): The message containing video description
        """
        if not message or not message.content:
            raise ValueError("Message content is empty")

        # Get the text content from the first content item
        first_content = message.content[0]
        if not isinstance(first_content, TextContent):
            raise ValueError("First content item is not TextContent")

        video_text = first_content.text
        if not video_text:
            raise ValueError("Video description text content is empty")

        # Parse the video description text into individual video items
        video_items = parse_video_description(video_text)

        video_contents = []
        for i, item_text in enumerate(video_items):
            text_content = TextContent(text=item_text, index=i)
            video_contents.append(text_content)

        # Create a single Message with all video description contents
        video_message = Message(
            content=video_contents,
            role=message.role,
        )

        # Set the video description message in the stages
        self.set_stage_message(Stage.VIDEO_DESCRIPTION, video_message)

    def get_video_description(self) -> Optional[str]:
        """
        Get video description message as formatted string

        Returns:
            Optional[str]: The formatted video description string
        """
        video_message = self.stages.get(Stage.VIDEO_DESCRIPTION)
        if not video_message:
            raise ValueError(
                "No video description message found in stages",
            )

        if not video_message.content:
            raise ValueError(
                "No content found in video description message",
            )

        video_parts = []
        for i, content in enumerate(video_message.content, 1):
            if isinstance(content, TextContent) and content.text:
                prefix = f"视频{i}"
                video_parts.append(f"{prefix}：{content.text}")

        if not video_parts:
            raise ValueError(
                "No text content found in video description message",
            )

        return "视频描述如下\n\n" + "\n\n".join(video_parts)

    def set_line(self, message: Message) -> None:
        """
        Set line message by parsing the input message content

        Args:
            message (Message): The message containing line content
        """
        if not message or not message.content:
            raise ValueError("Message content is empty")

        # Get the text content from the first content item
        first_content = message.content[0]
        if not isinstance(first_content, TextContent):
            raise ValueError("First content item is not TextContent")

        line_text = first_content.text
        if not line_text:
            raise ValueError("Line text content is empty")

        # Parse the line text into individual role and dialogue items
        line_items = parse_line(line_text)

        line_contents = []
        for i, item_text in enumerate(line_items):
            text_content = TextContent(text=item_text, index=i)
            line_contents.append(text_content)

        # Create a single Message with all line contents
        line_message = Message(
            content=line_contents,
            role=message.role,
        )

        # Set the line message in the stages
        self.set_stage_message(Stage.LINE, line_message)

    def get_line(self) -> Optional[str]:
        """
        Get line message as formatted string

        Returns:
            Optional[str]: The formatted line string with storyboard prefixes
        """
        line_message = self.stages.get(Stage.LINE)
        if not line_message:
            raise ValueError("No line message found in stages")

        if not line_message.content:
            raise ValueError("No content found in line message")

        # Group content into triplets (role, dialogue, voice)
        line_parts = []
        content_list = [
            content
            for content in line_message.content
            if isinstance(content, TextContent) and content.text
        ]

        if not content_list:
            raise ValueError("No text content found in line message")

        # Process content in triplets (role, dialogue, voice)
        for i in range(0, len(content_list), 3):
            if i + 2 < len(content_list):
                role = content_list[i].text
                dialogue = content_list[i + 1].text
                voice = content_list[i + 2].text
                storyboard_num = (i // 3) + 1
                line_parts.append(
                    f"分镜{storyboard_num}：\n角色：{role}\n"
                    f'中文台词："{dialogue}"\n音色：{voice}',
                )

        if not line_parts:
            raise ValueError(
                "No valid role-dialogue-voice triplets found in line message",
            )

        return "\n\n".join(line_parts)


def get_stage_session(session_id: str) -> StageSession:
    if session_id not in _stage_manager:
        stage_session = StageSession(session_id)
        _stage_manager[session_id] = stage_session

    return _stage_manager.get(session_id)


def destroy_stage_session(session_id: str) -> None:
    if session_id in _stage_manager:
        del _stage_manager[session_id]


_stage_manager: dict[str, StageSession] = {}
