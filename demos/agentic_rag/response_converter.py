# -*- coding: utf-8 -*-
"""
响应协议转换器

将agentic rag服务的内部响应格式转换为符合agent协议的响应格式
"""

import json
import uuid
from typing import Any, Dict, Generator, List, Optional

# 使用相对导入
try:
    from .agent_builder import ResponseBuilder
    from .agent import MessageType, Role
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from agent_builder import ResponseBuilder
    from agent import MessageType, Role


class AgenticRagResponseConverter:
    """Agentic RAG响应转换器"""

    def __init__(self):
        self.response_builder = ResponseBuilder()

    def convert_intermediate_response(
        self,
        internal_response: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        """
        转换中间响应为符合agent协议的流式响应

        Args:
            internal_response: 内部响应字典

        Yields:
            符合agent协议的响应对象
        """
        # 重置响应构建器
        self.response_builder.reset()

        # 1. 创建响应 (created)
        created_response = self.response_builder.created()
        yield created_response.model_dump()

        # 2. 开始响应 (in_progress)
        in_progress_response = self.response_builder.in_progress()
        yield in_progress_response.model_dump()

        # 3. 处理thinking模块 - 使用REASONING类型
        if internal_response.get("thinking"):
            thinking_message_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.REASONING,
                )
            )
            # 发送消息开始
            yield thinking_message_builder.get_message_data().model_dump()

            thinking_content_builder = (
                thinking_message_builder.create_content_builder()
            )
            # 发送内容开始
            yield thinking_content_builder.get_content_data().model_dump()

            thinking_content = thinking_content_builder.set_text(
                json.dumps(internal_response["thinking"], ensure_ascii=False),
            )
            yield thinking_content.model_dump()

            completed_content = thinking_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = thinking_message_builder.complete()
            yield completed_message.model_dump()

        # 4. 处理task_list模块 - 使用MESSAGE类型
        if internal_response.get("task_list"):
            task_message_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.MESSAGE,
                )
            )
            # 发送消息开始
            yield task_message_builder.get_message_data().model_dump()

            task_content_builder = (
                task_message_builder.create_content_builder()
            )
            # 发送内容开始
            yield task_content_builder.get_content_data().model_dump()

            # 一次性输出任务列表，而不是字符级别流式输出
            task_content = task_content_builder.set_text(
                json.dumps(internal_response["task_list"], ensure_ascii=False),
            )
            yield task_content.model_dump()

            completed_content = task_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = task_message_builder.complete()
            yield completed_message.model_dump()

        # 5. 处理search模块 - 使用PLUGIN_CALL和PLUGIN_CALL_OUTPUT类型
        if internal_response.get("search"):
            # PLUGIN_CALL消息
            search_call_builder = self.response_builder.create_message_builder(
                role=Role.ASSISTANT,
                message_type=MessageType.PLUGIN_CALL,
            )
            # 发送消息开始
            yield search_call_builder.get_message_data().model_dump()

            search_call_content_builder = (
                search_call_builder.create_content_builder()
            )
            # 发送内容开始
            yield search_call_content_builder.get_content_data().model_dump()

            # 生成关联ID
            search_correlation_id = str(uuid.uuid4())

            search_call_content = search_call_content_builder.set_text(
                json.dumps(
                    {
                        "name": "web_search",
                        "query": internal_response["search"].get("query", ""),
                        "status": internal_response["search"].get("status", 0),
                        "correlation_id": search_correlation_id,
                    },
                    ensure_ascii=False,
                ),
            )
            yield search_call_content.model_dump()

            completed_content = search_call_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = search_call_builder.complete()
            yield completed_message.model_dump()

            # PLUGIN_CALL_OUTPUT消息
            search_output_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.PLUGIN_CALL_OUTPUT,
                )
            )
            # 发送消息开始
            yield search_output_builder.get_message_data().model_dump()

            search_output_content_builder = (
                search_output_builder.create_content_builder()
            )
            # 发送内容开始
            yield search_output_content_builder.get_content_data().model_dump()

            # 添加关联ID到搜索输出
            search_output_data = internal_response["search"].copy()
            search_output_data["correlation_id"] = search_correlation_id

            # 一次性输出搜索结果，而不是字符级别流式输出
            search_output_content = search_output_content_builder.set_text(
                json.dumps(search_output_data, ensure_ascii=False),
            )
            yield search_output_content.model_dump()

            completed_content = search_output_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = search_output_builder.complete()
            yield completed_message.model_dump()

        # 6. 处理rag模块 - 使用PLUGIN_CALL和PLUGIN_CALL_OUTPUT类型
        if internal_response.get("rag"):
            # PLUGIN_CALL消息
            rag_call_builder = self.response_builder.create_message_builder(
                role=Role.ASSISTANT,
                message_type=MessageType.PLUGIN_CALL,
            )
            # 发送消息开始
            yield rag_call_builder.get_message_data().model_dump()

            rag_call_content_builder = (
                rag_call_builder.create_content_builder()
            )
            # 发送内容开始
            yield rag_call_content_builder.get_content_data().model_dump()

            # 生成关联ID
            correlation_id = str(uuid.uuid4())

            rag_call_content = rag_call_content_builder.set_text(
                json.dumps(
                    {
                        "name": "rag_retrieval",
                        "query": internal_response["rag"].get("query", ""),
                        "status": internal_response["rag"].get("status", 0),
                        "correlation_id": correlation_id,
                    },
                    ensure_ascii=False,
                ),
            )
            yield rag_call_content.model_dump()

            completed_content = rag_call_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = rag_call_builder.complete()
            yield completed_message.model_dump()

            # PLUGIN_CALL_OUTPUT消息
            rag_output_builder = self.response_builder.create_message_builder(
                role=Role.ASSISTANT,
                message_type=MessageType.PLUGIN_CALL_OUTPUT,
            )
            # 发送消息开始
            yield rag_output_builder.get_message_data().model_dump()

            rag_output_content_builder = (
                rag_output_builder.create_content_builder()
            )
            # 发送内容开始
            yield rag_output_content_builder.get_content_data().model_dump()

            # 添加关联ID到RAG输出
            rag_output_data = internal_response["rag"].copy()
            rag_output_data["correlation_id"] = correlation_id

            # 一次性输出RAG结果，而不是字符级别流式输出
            rag_output_content = rag_output_content_builder.set_text(
                json.dumps(rag_output_data, ensure_ascii=False),
            )
            yield rag_output_content.model_dump()

            completed_content = rag_output_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = rag_output_builder.complete()
            yield completed_message.model_dump()

        # 7. 处理final_response - 使用MESSAGE类型
        if internal_response.get("final_response"):
            final_message_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.MESSAGE,
                )
            )
            # 发送消息开始
            yield final_message_builder.get_message_data().model_dump()

            final_content_builder = (
                final_message_builder.create_content_builder()
            )

            # 一次性输出最终响应，而不是字符级别流式输出
            final_content = final_content_builder.set_text(
                internal_response["final_response"],
            )
            yield final_content.model_dump()

            completed_content = final_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = final_message_builder.complete()
            yield completed_message.model_dump()

        # 8. 完成响应
        completed_response = self.response_builder.completed()
        yield completed_response.model_dump()

    def convert_final_response(
        self,
        internal_response: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        """
        转换最终响应为符合agent协议的响应

        Args:
            internal_response: 内部响应字典

        Yields:
            符合agent协议的响应对象
        """
        # 重置响应构建器
        self.response_builder.reset()

        # 1. 创建响应 (created)
        created_response = self.response_builder.created()
        yield created_response.model_dump()

        # 2. 开始响应 (in_progress)
        in_progress_response = self.response_builder.in_progress()
        yield in_progress_response.model_dump()

        # 3. 处理thinking模块 - 使用REASONING类型
        if internal_response.get("thinking"):
            thinking_message_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.REASONING,
                )
            )
            # 发送消息开始
            yield thinking_message_builder.get_message_data().model_dump()

            thinking_content_builder = (
                thinking_message_builder.create_content_builder()
            )
            # 发送内容开始
            yield thinking_content_builder.get_content_data().model_dump()

            # 一次性输出思考过程，而不是字符级别流式输出
            thinking_content = thinking_content_builder.set_text(
                json.dumps(internal_response["thinking"], ensure_ascii=False),
            )
            yield thinking_content.model_dump()

            completed_content = thinking_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = thinking_message_builder.complete()
            yield completed_message.model_dump()

        # 4. 处理task_list模块 - 使用MESSAGE类型
        if internal_response.get("task_list"):
            task_message_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.MESSAGE,
                )
            )
            # 发送消息开始
            yield task_message_builder.get_message_data().model_dump()

            task_content_builder = (
                task_message_builder.create_content_builder()
            )
            # 发送内容开始
            yield task_content_builder.get_content_data().model_dump()

            # 一次性输出任务列表，而不是字符级别流式输出
            task_content = task_content_builder.set_text(
                json.dumps(internal_response["task_list"], ensure_ascii=False),
            )
            yield task_content.model_dump()

            completed_content = task_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = task_message_builder.complete()
            yield completed_message.model_dump()

        # 5. 处理search模块 - 使用PLUGIN_CALL和PLUGIN_CALL_OUTPUT类型
        if internal_response.get("search"):
            # PLUGIN_CALL消息
            search_call_builder = self.response_builder.create_message_builder(
                role=Role.ASSISTANT,
                message_type=MessageType.PLUGIN_CALL,
            )
            # 发送消息开始
            yield search_call_builder.get_message_data().model_dump()

            search_call_content_builder = (
                search_call_builder.create_content_builder()
            )
            # 发送内容开始
            yield search_call_content_builder.get_content_data().model_dump()

            # 生成关联ID
            search_correlation_id = str(uuid.uuid4())

            search_call_content = search_call_content_builder.set_text(
                json.dumps(
                    {
                        "name": "web_search",
                        "query": internal_response["search"].get("query", ""),
                        "status": internal_response["search"].get("status", 0),
                        "correlation_id": search_correlation_id,
                    },
                    ensure_ascii=False,
                ),
            )
            yield search_call_content.model_dump()

            completed_content = search_call_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = search_call_builder.complete()
            yield completed_message.model_dump()

            # PLUGIN_CALL_OUTPUT消息
            search_output_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.PLUGIN_CALL_OUTPUT,
                )
            )
            # 发送消息开始
            yield search_output_builder.get_message_data().model_dump()

            search_output_content_builder = (
                search_output_builder.create_content_builder()
            )
            # 发送内容开始
            yield search_output_content_builder.get_content_data().model_dump()

            # 添加关联ID到搜索输出
            search_output_data = internal_response["search"].copy()
            search_output_data["correlation_id"] = search_correlation_id

            # 一次性输出搜索结果，而不是字符级别流式输出
            search_output_content = search_output_content_builder.set_text(
                json.dumps(search_output_data, ensure_ascii=False),
            )
            yield search_output_content.model_dump()

            completed_content = search_output_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = search_output_builder.complete()
            yield completed_message.model_dump()

        # 6. 处理rag模块 - 使用PLUGIN_CALL和PLUGIN_CALL_OUTPUT类型
        if internal_response.get("rag"):
            # PLUGIN_CALL消息
            rag_call_builder = self.response_builder.create_message_builder(
                role=Role.ASSISTANT,
                message_type=MessageType.PLUGIN_CALL,
            )
            # 发送消息开始
            yield rag_call_builder.get_message_data().model_dump()

            rag_call_content_builder = (
                rag_call_builder.create_content_builder()
            )
            # 发送内容开始
            yield rag_call_content_builder.get_content_data().model_dump()

            # 生成关联ID
            correlation_id = str(uuid.uuid4())

            rag_call_content = rag_call_content_builder.set_text(
                json.dumps(
                    {
                        "name": "rag_retrieval",
                        "query": internal_response["rag"].get("query", ""),
                        "status": internal_response["rag"].get("status", 0),
                        "correlation_id": correlation_id,
                    },
                    ensure_ascii=False,
                ),
            )
            yield rag_call_content.model_dump()

            completed_content = rag_call_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = rag_call_builder.complete()
            yield completed_message.model_dump()

            # PLUGIN_CALL_OUTPUT消息
            rag_output_builder = self.response_builder.create_message_builder(
                role=Role.ASSISTANT,
                message_type=MessageType.PLUGIN_CALL_OUTPUT,
            )
            # 发送消息开始
            yield rag_output_builder.get_message_data().model_dump()

            rag_output_content_builder = (
                rag_output_builder.create_content_builder()
            )
            # 发送内容开始
            yield rag_output_content_builder.get_content_data().model_dump()

            # 添加关联ID到RAG输出
            rag_output_data = internal_response["rag"].copy()
            rag_output_data["correlation_id"] = correlation_id

            # 一次性输出RAG结果，而不是字符级别流式输出
            rag_output_content = rag_output_content_builder.set_text(
                json.dumps(rag_output_data, ensure_ascii=False),
            )
            yield rag_output_content.model_dump()

            completed_content = rag_output_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = rag_output_builder.complete()
            yield completed_message.model_dump()

        # 7. 处理final_response - 使用MESSAGE类型
        if internal_response.get("final_response"):
            final_message_builder = (
                self.response_builder.create_message_builder(
                    role=Role.ASSISTANT,
                    message_type=MessageType.MESSAGE,
                )
            )
            # 发送消息开始
            yield final_message_builder.get_message_data().model_dump()

            final_content_builder = (
                final_message_builder.create_content_builder()
            )

            # 一次性输出最终响应，而不是字符级别流式输出
            final_content = final_content_builder.set_text(
                internal_response["final_response"],
            )
            yield final_content.model_dump()

            completed_content = final_content_builder.complete()
            yield completed_content.model_dump()

            completed_message = final_message_builder.complete()
            yield completed_message.model_dump()

        # 8. 完成响应
        completed_response = self.response_builder.completed()
        yield completed_response.model_dump()
