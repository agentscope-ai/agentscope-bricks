# -*- coding: utf-8 -*-
import uuid
import json
from http import HTTPStatus
from typing import Any, Optional, Dict, AsyncGenerator
import aiohttp
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.tracing_utils import TracingUtil


DASHSCOPE_API_BASE = "https://dashscope.aliyuncs.com/api/v1"


class WanImageInterleaveGenerationInput(BaseModel):
    """
    Input model for Alibaba Cloud
      Wan 2.6 Image Interleaved (Text + Image) Generation.
    """

    prompt: str = Field(
        ...,
        description="用户输入的文本指令，例如 '给我一个3张图辣椒炒肉教程'。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，描述不希望出现的内容，如低质量、模糊、文字等。",
    )
    image: Optional[str] = Field(
        default=None,
        description="可选的参考图像 URL，图片和prompt要有关系，否则会被忽略。",
    )
    max_images: Optional[int] = Field(
        default=5,
        description="期望生成的最大图像数量取值范围：1～5，默认值为 5,该参数仅代表“数量上限”。"
        "实际生成的图像数量由模型推理决定，可能会少于设定值。",
    )
    size: Optional[str] = Field(
        default="1280*1280",
        description="输出图像的分辨率。默认值是1280*1280，可不填。",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印,false：默认值，不添加水印,true：添加水印。",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，用于结果可复现。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing "
        "headers for mcp only, don't generate it",
    )


class WanImageInterleaveGenerationOutput(BaseModel):
    full_text: str = Field(
        ...,
        description="模型生成的完整文本内容（不含图片占位符）。",
    )
    image_urls: list[str] = Field(
        ...,
        description="按顺序生成的图像公网 URL 列表。",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="请求唯一 ID，用于日志追踪。",
    )


class WanImageInterleaveGeneration(
    Component[
        WanImageInterleaveGenerationInput,
        WanImageInterleaveGenerationOutput,
    ],
):
    name: str = "modelstudio_wan_text_image_interleave_generation"
    description: str = (
        "[版本: wan2.6] 通义万相图文混排生成工具（wan2.6-image），支持文本+图像混合生成。\n"
        "支持传入最多1张参考图用于风格/背景引导。"
    )

    @trace(
        trace_type="AIGC",
        trace_name="wan_image_interleave_generation_stream",
    )
    async def astream(
        self,
        args: WanImageInterleaveGenerationInput,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        content: list[Dict[str, str]] = [{"text": args.prompt}]
        if args.image:
            content.append({"image": args.image})
        parameters = {
            "enable_interleave": True,  # 必须为 true
            "stream": True,  # 启用流式
            "max_images": args.max_images,
            "size": args.size,
            "watermark": args.watermark,
        }

        # 可选参数：仅当非 None 时传入
        if args.negative_prompt is not None:
            parameters["negative_prompt"] = args.negative_prompt
        if args.seed is not None:
            parameters["seed"] = args.seed

        payload = {
            "model": "wan2.6-image",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    },
                ],
            },
            "parameters": parameters,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Sse": "enable",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DASHSCOPE_API_BASE}/services/aigc/multimodal-generation/generation",  # noqa
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status != HTTPStatus.OK:
                    error_text = await resp.text()
                    raise RuntimeError(f"SSE request failed: {error_text}")

                async for line_bytes in resp.content:
                    line = line_bytes.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        contents = chunk["output"]["choices"][0]["message"][
                            "content"
                        ]
                        for item in contents:
                            if item.get("type") == "text":
                                yield {"type": "text", "value": item["text"]}
                            elif item.get("type") == "image":
                                img_url = item.get("image")
                                if isinstance(img_url, str):
                                    yield {"type": "image", "value": img_url}
                    except (
                        KeyError,
                        IndexError,
                        TypeError,
                        json.JSONDecodeError,
                    ):
                        continue

    @trace(trace_type="AIGC", trace_name="wan_image_interleave_generation")
    async def arun(
        self,
        args: WanImageInterleaveGenerationInput,
        **kwargs: Any,
    ) -> WanImageInterleaveGenerationOutput:
        full_text = ""
        image_urls: list[str] = []
        request_id = TracingUtil.get_request_id() or str(uuid.uuid4())

        # 复用 astream 逻辑来聚合结果（避免重复代码）
        async for chunk in self.astream(args, **kwargs):
            if chunk["type"] == "text":
                full_text += chunk["value"]
            elif chunk["type"] == "image":
                image_urls.append(chunk["value"])

        return WanImageInterleaveGenerationOutput(
            full_text=full_text,
            image_urls=image_urls,
            request_id=request_id,
        )
