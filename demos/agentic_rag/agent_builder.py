# -*- coding: utf-8 -*-
"""
Agent协议数据生成器

提供分层Builder模式的工具来生成符合types/agent定义的流式响应数据
"""

import time
from typing import Any, Dict, Generator, List, Optional
from uuid import uuid4

from .agent import (
    AgentResponse,
    AudioContent,
    Content,
    ContentType,
    DataContent,
    FileContent,
    ImageContent,
    Message,
    RefusalContent,
    Role,
    TextContent,
)


class ContentBuilder:
    """
    内容构建器

    负责构建和管理单个Content对象，支持Text、Image、Data三种内容类型
    """

    def __init__(
        self,
        message_builder: "MessageBuilder",
        content_type: str = ContentType.TEXT,
        index: int = 0,
    ):
        """
        初始化内容构建器

        Args:
            message_builder: 关联的MessageBuilder对象
            content_type: 内容类型 ('text', 'image', 'data')
            index: 内容索引，默认为0
        """
        self.message_builder = message_builder
        self.content_type = content_type
        self.index = index

        # 根据内容类型初始化相应的数据结构和content对象
        if content_type == ContentType.TEXT:
            self.text_tokens: List[str] = []
            self.content = TextContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            ).created()
        elif content_type == ContentType.IMAGE:
            self.content = ImageContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            ).created()
        elif content_type == ContentType.DATA:
            self.data_deltas: List[Dict[str, Any]] = []
            self.content = DataContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            ).created()
        elif content_type == ContentType.REFUSAL:
            self.content = RefusalContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            ).created()
        elif content_type == ContentType.FILE:
            self.content = FileContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            ).created()
        elif content_type == ContentType.AUDIO:
            self.content = AudioContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            ).created()
        else:
            raise ValueError(f"Unsupported content type: {content_type}")

    def add_text_delta(self, text: str) -> TextContent:
        """
        添加文本增量 (仅适用于text类型)

        Args:
            text: 文本片段

        Returns:
            增量内容对象
        """
        if self.content_type != ContentType.TEXT:
            raise ValueError("add_text_delta only supported for text content")

        self.text_tokens.append(text)

        # 创建delta内容
        delta_content = TextContent(
            type=self.content_type,
            index=self.index,
            delta=True,
            msg_id=self.message_builder.message.id,
            text=text,
        ).in_progress()

        return delta_content

    def set_text(self, text: str) -> TextContent:
        """
        设置完整文本内容 (仅适用于text类型)

        Args:
            text: 完整文本内容

        Returns:
            内容对象
        """
        if self.content_type != ContentType.TEXT:
            raise ValueError("set_text only supported for text content")

        self.content.text = text
        self.content.in_progress()
        return self.content

    def set_refusal(self, text: str) -> RefusalContent:
        """
        设置完整文本内容 (仅适用于text类型)

        Args:
            text: 完整文本内容

        Returns:
            内容对象
        """
        if self.content_type != ContentType.REFUSAL:
            raise ValueError("set_text only supported for text content")

        self.content.refusal = text
        self.content.in_progress()
        return self.content

    def set_image_url(self, image_url: str) -> ImageContent:
        """
        设置图片URL (仅适用于image类型)

        Args:
            image_url: 图片URL

        Returns:
            内容对象
        """
        if self.content_type != ContentType.IMAGE:
            raise ValueError("set_image_url only supported for image content")

        self.content.image_url = image_url
        self.content.in_progress()
        return self.content

    def set_data(self, data: Dict[str, Any]) -> DataContent:
        """
        设置数据内容 (仅适用于data类型)

        Args:
            data: 数据字典

        Returns:
            内容对象
        """
        if self.content_type != ContentType.DATA:
            raise ValueError("set_data only supported for data content")

        self.content.data = data
        self.content.in_progress()
        return self.content

    def update_data(self, key: str, value: Any) -> DataContent:
        """
        更新数据内容的特定字段 (仅适用于data类型)

        Args:
            key: 数据键
            value: 数据值

        Returns:
            内容对象
        """
        if self.content_type != ContentType.DATA:
            raise ValueError("update_data only supported for data content")

        if self.content.data is None:
            self.content.data = {}
        self.content.data[key] = value
        self.content.in_progress()
        return self.content

    def add_data_delta(self, delta_data: Dict[str, Any]) -> DataContent:
        """
        添加数据增量 (仅适用于data类型)

        Args:
            delta_data: 增量数据字典

        Returns:
            增量内容对象
        """
        if self.content_type != ContentType.DATA:
            raise ValueError("add_data_delta only supported for data content")

        self.data_deltas.append(delta_data)

        # 创建delta内容对象
        delta_content = DataContent(
            type=self.content_type,
            index=self.index,
            delta=True,
            msg_id=self.message_builder.message.id,
            data=delta_data,
        ).in_progress()

        return delta_content

    def _merge_data_incrementally(
        self,
        base_data: Dict[str, Any],
        delta_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        智能合并数据增量

        Args:
            base_data: 基础数据
            delta_data: 增量数据

        Returns:
            合并后的数据
        """
        result = base_data.copy() if base_data else {}

        for key, delta_value in delta_data.items():
            if key not in result:
                # 新key，直接添加
                result[key] = delta_value
            else:
                base_value = result[key]
                # 根据数据类型进行增量合并
                if isinstance(base_value, str) and isinstance(
                    delta_value,
                    str,
                ):
                    # 字符串拼接
                    result[key] = base_value + delta_value
                elif (
                    isinstance(base_value, (int, float))
                    and isinstance(delta_value, (int, float))
                    and not isinstance(base_value, bool)
                    and not isinstance(delta_value, bool)
                ):
                    # 数字累加（排除bool类型，因为bool是int的子类）
                    result[key] = base_value + delta_value
                elif isinstance(base_value, list) and isinstance(
                    delta_value,
                    list,
                ):
                    # 列表合并
                    result[key] = base_value + delta_value
                elif isinstance(base_value, dict) and isinstance(
                    delta_value,
                    dict,
                ):
                    # 字典递归合并
                    result[key] = self._merge_data_incrementally(
                        base_value,
                        delta_value,
                    )
                else:
                    # 其他情况直接替换（包括bool、不同类型等）
                    result[key] = delta_value

        return result

    def add_delta(self, text: str) -> TextContent:
        """
        添加文本增量 (向后兼容方法)

        Args:
            text: 文本片段

        Returns:
            增量内容对象
        """
        return self.add_text_delta(text)

    def complete(self) -> Message:
        """
        完成内容构建

        Returns:
            完整内容对象的字典表示
        """
        if self.content_type == ContentType.TEXT:
            # 对于文本内容，合并已设置的文本和tokens
            if hasattr(self, "text_tokens") and self.text_tokens:
                # 获取现有文本，如果没有则为空字符串
                existing_text = self.content.text or ""
                token_text = "".join(self.text_tokens)
                self.content.text = existing_text + token_text
            self.content.delta = False
        elif self.content_type == ContentType.DATA:
            # 对于数据内容，合并已设置的数据和增量数据
            if hasattr(self, "data_deltas") and self.data_deltas:
                # 获取现有数据，如果没有则为空字典
                existing_data = self.content.data or {}

                # 逐步合并所有增量数据
                final_data = existing_data
                for delta_data in self.data_deltas:
                    final_data = self._merge_data_incrementally(
                        final_data,
                        delta_data,
                    )

                self.content.data = final_data
            self.content.delta = False

        # 设置完成状态
        self.content.completed()

        # 更新message的content列表
        self.message_builder.add_content(self.content)

        return self.content

    def get_content_data(self) -> Content:
        """
        获取当前content的字典表示

        Returns:
            内容对象
        """
        return self.content


class MessageBuilder:
    """
    消息构建器

    负责构建和管理单个Message对象，并更新关联的Response
    """

    def __init__(
        self,
        response_builder: "ResponseBuilder",
        role: str = Role.ASSISTANT,
    ):
        """
        初始化消息构建器

        Args:
            response_builder: 关联的ResponseBuilder对象
            role: 消息角色，默认为assistant
        """
        self.response_builder = response_builder
        self.role = role
        self.message_id = f"msg_{uuid4()}"
        self.content_builders: List[ContentBuilder] = []

        # 创建message对象
        self.message = Message(
            id=self.message_id,
            role=self.role,
        ).created()

        # 立即添加到response的output中
        self.response_builder.add_message(self.message)

    def create_content_builder(
        self,
        content_type: str = ContentType.TEXT,
    ) -> ContentBuilder:
        """
        创建内容构建器

        Args:
            content_type: 内容类型 ('text', 'image', 'data')

        Returns:
            新创建的ContentBuilder实例
        """
        index = len(self.content_builders)
        content_builder = ContentBuilder(self, content_type, index)
        self.content_builders.append(content_builder)
        return content_builder

    def add_content(self, content: Content):
        """
        添加内容到message

        Args:
            content: Content对象
        """
        if self.message.content is None:
            self.message.content = []

        # 检查是否已存在相同index的content，如果存在则替换
        existing_index = None
        for i, existing_content in enumerate(self.message.content):
            if (
                hasattr(existing_content, "index")
                and existing_content.index == content.index
            ):
                existing_index = i
                break

        if existing_index is not None:
            self.message.content[existing_index] = content
        else:
            self.message.content.append(content)

        # 通知response builder更新
        self.response_builder.update_message(self.message)

    def get_message_data(self) -> Message:
        """
        获取当前message的字典表示

        Returns:
            消息对象
        """
        return self.message

    def complete(self) -> Message:
        """
        完成消息构建

        Returns:
            完整消息对象的字典表示
        """
        self.message.completed()

        # 通知response builder更新
        self.response_builder.update_message(self.message)

        return self.message


class ResponseBuilder:
    """
    响应构建器

    负责构建和管理AgentResponse对象，协调MessageBuilder的工作
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        response_id: Optional[str] = None,
    ):
        """
        初始化响应构建器

        Args:
            session_id: 会话ID，可选
        """
        self.session_id = session_id
        self.response_id = response_id
        self.created_at = int(time.time())
        self.message_builders: List[MessageBuilder] = []

        # 创建response对象
        self.response = AgentResponse(
            id=self.response_id,
            session_id=self.session_id,
            created_at=self.created_at,
            output=[],
        )

    def reset(self):
        """
        重置构建器状态，生成新的ID和对象实例
        """
        self.response_id = f"response_{uuid4()}"
        self.created_at = int(time.time())
        self.message_builders = []

        # 重新创建response对象
        self.response = AgentResponse(
            id=self.response_id,
            session_id=self.session_id,
            created_at=self.created_at,
            output=[],
        )

    def get_response_data(self) -> AgentResponse:
        """
        获取当前response的字典表示

        Returns:
            响应对象
        """
        return self.response

    def created(self) -> AgentResponse:
        """
        设置响应状态为created

        Returns:
            响应对象
        """
        self.response.created()
        return self.response

    def in_progress(self) -> AgentResponse:
        """
        设置响应状态为in_progress

        Returns:
            响应对象
        """
        self.response.in_progress()
        return self.response

    def completed(self) -> AgentResponse:
        """
        设置响应状态为completed

        Returns:
            响应对象
        """
        self.response.completed()
        return self.response

    def create_message_builder(
        self,
        role: str = Role.ASSISTANT,
        message_type: str = "message",
    ) -> MessageBuilder:
        """
        创建消息构建器

        Args:
            role: 消息角色，默认为assistant
            message_type: 消息类型，默认为message

        Returns:
            新创建的MessageBuilder实例
        """
        message_builder = MessageBuilder(self, role)

        # Set the message type
        message_builder.message.type = message_type

        self.message_builders.append(message_builder)
        return message_builder

    def add_message(self, message: Message):
        """
        添加message到response的output列表

        Args:
            message: Message对象
        """
        # 检查是否已存在相同ID的message，如果存在则替换
        existing_index = None
        for i, existing_message in enumerate(self.response.output):
            if existing_message.id == message.id:
                existing_index = i
                break

        if existing_index is not None:
            self.response.output[existing_index] = message
        else:
            self.response.output.append(message)

    def update_message(self, message: Message):
        """
        更新response中的message

        Args:
            message: 更新后的Message对象
        """
        for i, existing_message in enumerate(self.response.output):
            if existing_message.id == message.id:
                self.response.output[i] = message
                break

    def generate_streaming_response(
        self,
        text_tokens: List[str],
        role: str = Role.ASSISTANT,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        生成完整的流式响应序列

        Args:
            text_tokens: 文本片段列表
            role: 消息角色，默认为assistant

        Yields:
            按顺序生成的响应对象字典
        """
        # 重置状态
        self.reset()

        # 1. 创建响应 (created)
        yield self.created()

        # 2. 开始响应 (in_progress)？
        yield self.in_progress()

        # 3. 创建消息构建器
        message_builder = self.create_message_builder(role)
        yield message_builder.get_message_data()

        # 4. 创建内容构建器
        content_builder = message_builder.create_content_builder()

        # 5. 流式输出文本片段
        for token in text_tokens:
            yield content_builder.add_delta(token)

        # 6. 完成内容
        yield content_builder.complete()

        # 7. 完成消息
        yield message_builder.complete()

        # 8. 完成响应
        yield self.completed()


# 为了保持向后兼容，提供别名
StreamingResponseBuilder = ResponseBuilder
