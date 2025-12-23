# -*- coding: utf-8 -*-
import os
import uuid
from typing import Any, Optional

from dashscope import AioMultiModalConversation
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.tracing_utils import TracingUtil


class QwenImageEditNewInput(BaseModel):
    """
    Qwen Image Edit New Input (Supports multiple images for fusion)
    """

    image_urls: list[str] = Field(
        ...,
        description=(
            "输入图像的URL地址列表，每个URL需为公网可访问地址，例如：['http://example.com/image1.jpg', 'http://example.com/image2.jpg']"  # noqa
        ),
    )
    prompt: str = Field(
        ...,
        description=(
            "正向提示词，用来描述生成图像中期望包含的元素和视觉特点，"
            "例如：'将两张图融合成一个赛博朋克城市夜景'。超过800个字符自动截断"
        ),
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description=(
            "反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制，"
            "超过500个字符自动截断"
        ),
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印，默认不设置。可设置为True或False。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description=(
            "HTTP request context containing headers for mcp only, "
            "don't generate it"
        ),
    )


class QwenImageEditNewOutput(BaseModel):
    """
    Qwen Image Edit New Output
    """

    results: list[str] = Field(
        title="Results",
        description="输出的融合后图片URL列表，仅包含1个URL",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class QwenImageEditNew(
    Component[QwenImageEditNewInput, QwenImageEditNewOutput],
):
    """
    Qwen Image Edit New Component for AI-powered multi-image fusion.
    Takes multiple input images and fuses them into a single output image
    based on the provided prompt.
    """

    name: str = "modelstudio_qwen_image_edit_new"
    description: str = (
        "通义千问-多图融合模型，基于 qwen-image-edit，支持将多张图像按提示词语义融合为一张新图。"
        "可用于风格混合、场景合成、元素组合等复杂图像生成任务。"
    )

    @trace(trace_type="AIGC", trace_name="qwen_image_edit_new")
    async def arun(
        self,
        args: QwenImageEditNewInput,
        **kwargs: Any,
    ) -> QwenImageEditNewOutput:
        """Qwen Image Edit using MultiModalConversation API

        This method uses DashScope's MultiModalConversation service to edit
        images based on text prompts. The API supports various image editing
        operations through natural language instructions.

        Args:
            args: QwenImageEditInput containing image_url, text_prompt,
                watermark, and negative_prompt.
            **kwargs: Additional keyword arguments including request_id,
                trace_event, model_name, api_key.

        Returns:
            QwenImageEditOutput containing the edited image URL and request ID.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid.
            RuntimeError: If the API call fails or returns an error.
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = kwargs.get(
            "model_name",
            os.getenv("QWEN_IMAGE_EDIT_MODEL_NAME", "qwen-image-edit"),
        )

        parameters = {}
        if args.negative_prompt:
            parameters["negative_prompt"] = args.negative_prompt
        if args.watermark is not None:
            parameters["watermark"] = args.watermark
        content = [{"image": url} for url in args.image_urls]
        content.append({"text": args.prompt})

        messages = [
            {
                "role": "user",
                "content": content,
            },
        ]

        try:
            response = await AioMultiModalConversation.call(
                api_key=api_key,
                model=model_name,
                messages=messages,
                **parameters,
            )
        except Exception as e:
            raise RuntimeError(f"Multi-image fusion API call failed: {str(e)}")

        if response.status_code != 200 or not response.output:
            raise RuntimeError(f"Invalid API response: {response}")
        try:
            choices = getattr(response.output, "choices", [])
            if not choices:
                raise RuntimeError("No choices in model response")

            message = getattr(choices[0], "message", {})
            content_output = getattr(message, "content", [])
            result_url = None
            if isinstance(content_output, str):
                result_url = content_output
            elif (
                isinstance(content_output, dict) and "image" in content_output
            ):
                result_url = content_output["image"]
            elif isinstance(content_output, list):
                for item in content_output:
                    if isinstance(item, dict) and "image" in item:
                        result_url = item["image"]
                        break

            if not result_url:
                raise RuntimeError("No image URL found in response")

        except Exception as parse_error:
            raise RuntimeError(f"Failed to parse fusion result: {parse_error}")

        if request_id == "":
            request_id = str(uuid.uuid4())

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "qwen_image_edit_new_result": {
                            "status": "success",
                            "result_count": 1,
                        },
                    },
                },
            )

        return QwenImageEditNewOutput(
            results=[result_url],
            request_id=request_id,
        )
