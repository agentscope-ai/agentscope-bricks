# -*- coding: utf-8 -*-
import uuid
from typing import Any, Optional
from dashscope import AioMultiModalConversation
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace, TraceType
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.tracing_utils import TracingUtil


class ZImageGenerationInput(BaseModel):
    """
    Input schema for Z-Image text-to-image generation.
    """

    prompt: str = Field(
        ...,
        description="正向提示词，描述期望生成的图像内容，建议详细且清晰。超过800字符将被截断。",
    )
    size: Optional[str] = Field(
        default="1024*1536",
        description="输出图像的分辨率。默认 1024*1536",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启 Prompt 智能改写。将使用大模型优化正向提示词。true: 开启，false：不开启（默认）。",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，用于结果复现。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context for MCP "
        "internal use only, do not generate it.",
    )


class ZImageGenerationOutput(BaseModel):
    """
    Output schema for Z-Image text-to-image generation.
    """

    results: list[str] = Field(
        title="Results",
        description="生成的图片URL列表。",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="本次请求的唯一标识。",
    )


class ZImageGeneration(
    Component[ZImageGenerationInput, ZImageGenerationOutput],
):
    """
    Z-Image Text-to-Image Generation Tool (based on z-image-turbo).
    Uses the 'z-image-turbo' model from DashScope to
    generate high-quality images from text prompts.
    Supports custom resolution, negative prompts, batch generation, and more.
    """

    name: str = "modelstudio_z_image_generation"
    description: str = (
        " 基于通义Z-Image大模型的智能图像生成服务，是一款轻量级文生图模型，"
        "可快速生成图像，支持中英文字渲染，并灵活适配多种分辨率与宽高比例。"
    )

    @trace(trace_type=TraceType.AIGC, trace_name="z_image_generation")
    async def arun(
        self,
        args: ZImageGenerationInput,
        **kwargs: Any,
    ) -> ZImageGenerationOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()
        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")
        model_name = "z-image-turbo"
        messages = [
            {
                "role": "user",
                "content": [{"text": args.prompt}],
            },
        ]
        parameters = {}
        if args.size and args.size != "1024*1536":
            parameters["size"] = args.size
        if args.seed is not None:
            parameters["seed"] = args.seed
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend

        try:
            response = await AioMultiModalConversation.call(
                api_key=api_key,
                model=model_name,
                messages=messages,
                **parameters,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to call Z-Image (z-image-turbo) API: {str(e)}",
            ) from e

        if response.status_code != 200 or not response.output:
            raise RuntimeError(f"Z-Image generation failed: {response}")
        results = []
        try:
            choices = getattr(response.output, "choices", [])
            if choices:
                message = getattr(choices[0], "message", {})
                content = getattr(message, "content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "image" in item:
                            results.append(item["image"])
                elif isinstance(content, str):
                    results.append(content)
                elif isinstance(content, dict) and "image" in content:
                    results.append(content["image"])
        except Exception as e:
            raise RuntimeError(
                f"Failed to parse Z-Image API response: {str(e)}",
            ) from e

        if not results:
            raise RuntimeError(
                f"No image URLs found in Z-Image response: {response}",
            )

        if not request_id:
            request_id = getattr(response, "request_id", None) or str(
                uuid.uuid4(),
            )

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "z_image_generation_result": {
                            "status_code": response.status_code,
                            "results": results,
                        },
                    },
                },
            )

        return ZImageGenerationOutput(
            results=results,
            request_id=request_id,
        )
