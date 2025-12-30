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


class ImageGenInput(BaseModel):
    """
    Input schema for Wanx 2.6 image editing generation.
    """

    prompt: str = Field(
        ...,
        description="正向提示词，描述期望生成的图像内容",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，描述不希望出现的内容，如低质量、模糊、文字等。",
    )
    size: Optional[str] = Field(
        default=None,
        description="输出图像的分辨率。默认值是1280*1280，可不填。",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启 Prompt 智能改写。将使用大模型优化正向提示词。true: 开启（默认），false：不开启。",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，用于结果复现。",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印,false：默认值，不添加水印,true：添加水印。",
    )
    n: Optional[int] = Field(
        default=4,
        description="生成图片的数量。取值范围为1~4张 默认4",
    )
    images: list[str] = Field(
        ...,
        description=(
            "参考图像URL列表，用于图像编辑。\n" "必须提供至少1张参考图像。"
        ),
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context for "
        "MCP internal use only, do not generate it.",
    )


class ImageGenOutput(BaseModel):
    """
    Output schema for Wanx 2.6 image generation.
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


class ImageEditWan26(
    Component[ImageGenInput, ImageGenOutput],
):
    """
    Wanx 2.6 Image Editing Generation Tool.
    Supports:
      - Image editing mode (with 1-3 reference images)
    Uses the 'wan2.6-image' model from DashScope.
    """

    name: str = "modelstudio_image_edit_wan26"
    description: str = (
        "[版本: wan2.6] 通义万相文生图模型（wan2.6-image）。\n"
        "图像编辑,基于1～4张输入图像进行编辑、风格迁移或主体一致性生成。返回编辑后的图片URL列表。"
    )

    @trace(trace_type=TraceType.AIGC, trace_name="wanx26_image_generation")
    async def arun(
        self,
        args: ImageGenInput,
        **kwargs: Any,
    ) -> ImageGenOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = "wan2.6-image"

        # 构造多模态 content：文本 + 可选图像
        content = [{"text": args.prompt}]
        images = args.images or []  # 安全处理 None
        for img_url in images:
            content.append({"image": img_url})

        messages = [
            {
                "role": "user",
                "content": content,
            },
        ]
        parameters = {}
        if args.negative_prompt:
            parameters["negative_prompt"] = args.negative_prompt
        if args.size and args.size != "1280*1280":
            parameters["size"] = args.size
        if args.seed is not None:
            parameters["seed"] = args.seed
        if args.watermark is not None:
            parameters["watermark"] = args.watermark
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.n is not None and args.n != 4:
            parameters["n"] = args.n
        try:
            response = await AioMultiModalConversation.call(
                api_key=api_key,
                model=model_name,
                messages=messages,
                enable_interleave=False,
                **parameters,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to call Wanx 2.6 image generation API: {str(e)}",
            ) from e

        if response.status_code != 200 or not response.output:
            raise RuntimeError(f"Wanx 2.6 image generation failed: {response}")

        results = []

        try:
            if hasattr(response, "output") and response.output:
                choices = getattr(response.output, "choices", [])
                if choices:
                    for choice in choices:
                        message = getattr(choice, "message", {})
                        msg_content = getattr(message, "content", [])
                        if isinstance(msg_content, list):
                            # 遍历当前 choice 的 content
                            for item in msg_content:
                                if isinstance(item, dict) and "image" in item:
                                    results.append(item["image"])
                                elif isinstance(item, str) and item.startswith(
                                    ("http://", "https://"),
                                ):
                                    results.append(item)
                        elif isinstance(
                            msg_content,
                            str,
                        ) and msg_content.startswith(
                            ("http://", "https://"),
                        ):
                            results.append(msg_content)
                        elif (
                            isinstance(msg_content, dict)
                            and "image" in msg_content
                        ):
                            results.append(msg_content["image"])
                    # --- 修改结束 ---
        except Exception as e:
            raise RuntimeError(
                f"Failed to parse Wanx 2.6 API response: {str(e)}",
            ) from e

        if not results:
            raise RuntimeError(f"No image found in response: {response}")

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
                        "wanx26_image_generation_result": {
                            "status_code": response.status_code,
                            "results": results,
                        },
                    },
                },
            )

        return ImageGenOutput(
            results=results,
            request_id=request_id,
        )
