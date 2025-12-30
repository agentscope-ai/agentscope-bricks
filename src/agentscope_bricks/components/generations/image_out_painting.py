# -*- coding: utf-8 -*-
import os
import uuid
import asyncio
from http import HTTPStatus
from typing import Any, Optional, Dict

import aiohttp
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.tracing_utils import TracingUtil


DASHSCOPE_API_BASE = "https://dashscope.aliyuncs.com/api/v1"


class ImageOutPaintingAutoInput(BaseModel):
    """
    Input for auto-submit-and-fetch image out-painting task.
    """

    image_url: str = Field(
        ...,
        description="输入图像的公网可访问 URL。",
    )
    angle: Optional[float] = Field(
        default=None,
        description="逆时针旋转角度，取值范围 [0, 359]。默认为 0（不旋转）。",
    )
    output_ratio: Optional[str] = Field(
        default=None,
        description='目标宽高比，可选值：["", "1:1", "3:4", "4:3", "9:16", "16:9"]。'
        '默认值为""，表示不设置输出图像的宽高比。',
    )
    x_scale: Optional[float] = Field(
        default=None,
        description="水平方向扩展比例（居中扩展），默认 1.0。可以与 y_scale 搭配使用。取值范围 [1.0, 3.0]。"
        "例如：输入图像分辨率为1000×1000（宽×高），x_scale=2.0，扩展后的图像分辨率为2000×1000（宽×高）。"
        "保持高度不变，左右各添加500个像素。",
    )
    y_scale: Optional[float] = Field(
        default=None,
        description="垂直方向扩展比例（居中扩展），默认 1.0。可以选择与 x_scale 搭配使用。取值范围 [1.0, 3.0]。"
        "例如：输入图像分辨率为1000×1000（宽×高），y_scale=2.0，扩展后的图像分辨率为1000×2000（宽×高）。"
        "保持宽度不变，上下各添加500个像素。",
    )
    top_offset: Optional[float] = Field(
        default=None,
        description="在图像上方添加的像素数。默认值为0,"
        "需满足 top_offset + bottom_offset < 3 × 原图高度。"
        "输入图像分辨率为1000×1000（宽×高），top_offset=500，扩展后的图像分辨率为1000×1500（宽×高）。"
        "保持宽度不变，只在图像上方添加500个像素。",
    )
    bottom_offset: Optional[float] = Field(
        default=None,
        description="在图像下方添加的像素数。默认值为0，"
        "需满足 top_offset + bottom_offset < 3 × 原图高度。"
        "例如：输入图像分辨率为1000×1000（宽×高），bottom_offset=500，扩展后的图像分辨率为1000×1500（宽×高）。"
        "保持宽度不变，只在图像下方添加500个像素。",
    )
    left_offset: Optional[float] = Field(
        default=None,
        description="在图像左侧添加的像素数。默认值为0，"
        "需满足 left_offset + right_offset < 3 × 原图宽度。"
        "例如：输入图像分辨率为1000×1000（宽×高），left_offset=500，扩展后的图像分辨率为1500×1000（宽×高）。"
        "保持高度不变，只在图像左侧添加500个像素。",
    )
    right_offset: Optional[float] = Field(
        default=None,
        description="在图像右侧添加的像素数。默认值为0，"
        "需满足 left_offset + right_offset < 3 × 原图宽度。"
        "例如：输入图像分辨率为1000×1000（宽×高），right_offset=500，扩展后的图像分辨率为1500×1000（宽×高）。"
        "保持高度不变，只在图像右侧添加500个像素。",
    )
    best_quality: Optional[bool] = Field(
        default=None,
        description="是否启用最佳质量模式。默认 false（速度优先），设为 true 可提升细节但耗时增加。",
    )
    limit_image_size: Optional[bool] = Field(
        default=None,
        description="是否限制输出图像大小（≤5MB）。默认 true，建议保持开启。"
        "模型生成的图像需要经过一层安全过滤后才能输出，当前不支持大于10M的图像处理。",
    )
    add_watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印,True：默认值,添加水印,False：不添加水印。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing "
        "headers for mcp only, don't generate it",
    )


class ImageOutPaintingAutoOutput(BaseModel):
    output_image_url: str = Field(
        ...,
        description="扩图后生成的图像公网 URL（PNG/JPG 等格式），有效期 24 小时。",
    )
    task_id: str = Field(
        ...,
        description="异步任务的唯一标识符。",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="请求 ID，用于日志追踪。",
    )


class ImageOutPaintingAuto(
    Component[ImageOutPaintingAutoInput, ImageOutPaintingAutoOutput],
):
    name: str = "modelstudio_image_out_painting_auto"
    description: str = (
        "图像画面扩展（扩图）同步自动执行工具。\n"
        "提交扩图任务并内部轮询结果，直接返回扩图后的图像 URL。\n"
        "无需手动查询任务状态，适合需要端到端结果的场景。"
    )

    @trace(trace_type="AIGC", trace_name="image_out_painting_auto")
    async def arun(
        self,
        args: ImageOutPaintingAutoInput,
        **kwargs: Any,
    ) -> ImageOutPaintingAutoOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        # 构建 parameters（仅非 None 值）
        parameters: Dict[str, Any] = {}
        for field in [
            "angle",
            "output_ratio",
            "x_scale",
            "y_scale",
            "top_offset",
            "bottom_offset",
            "left_offset",
            "right_offset",
            "best_quality",
            "limit_image_size",
            "add_watermark",
        ]:
            value = getattr(args, field)
            if value is not None:
                parameters[field] = value

        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-Async": "enable",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "image-out-painting",
            "input": {"image_url": args.image_url},
            "parameters": parameters,
        }

        # Step 1: Submit task
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DASHSCOPE_API_BASE}/services/aigc/image2image/out-painting",
                headers=headers,
                json=payload,
            ) as resp:
                status_code = resp.status
                response_json = await resp.json()

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "submit",
                    "payload": {
                        "request_id": request_id,
                        "response": response_json,
                        "status_code": status_code,
                    },
                },
            )

        if status_code != HTTPStatus.OK or "output" not in response_json:
            error_msg = response_json.get("message", "Unknown error")
            raise RuntimeError(
                f"Failed to submit out-painting task: {error_msg} (code: {status_code})",  # noqa
            )

        task_id = response_json["output"]["task_id"]
        request_id = (
            response_json.get("request_id") or request_id or str(uuid.uuid4())
        )

        # Step 2: Poll until completion
        max_retries = 60  # 最多等待 2 分钟（60 * 2s）
        retry_interval = 2  # 每 2 秒查询一次

        fetch_headers = {"Authorization": f"Bearer {api_key}"}

        for attempt in range(max_retries):
            await asyncio.sleep(retry_interval)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{DASHSCOPE_API_BASE}/tasks/{task_id}",
                    headers=fetch_headers,
                ) as resp:
                    fetch_status = resp.status
                    fetch_response = await resp.json()

            if fetch_status != HTTPStatus.OK or "output" not in fetch_response:
                error_msg = fetch_response.get(
                    "message",
                    "Unknown fetch error",
                )
                raise RuntimeError(
                    f"Failed to poll task: {error_msg} (code: {fetch_status})",
                )

            output = fetch_response["output"]
            task_status = output["task_status"]

            if task_status == "SUCCEEDED":
                output_image_url = output["output_image_url"]
                final_request_id = (
                    fetch_response.get("request_id") or request_id
                )

                if trace_event:
                    trace_event.on_log(
                        "",
                        **{
                            "step_suffix": "success",
                            "payload": {
                                "output_image_url": output_image_url,
                                "request_id": final_request_id,
                            },
                        },
                    )

                return ImageOutPaintingAutoOutput(
                    output_image_url=output_image_url,
                    task_id=task_id,
                    request_id=final_request_id,
                )

            elif task_status in ("FAILED", "CANCELED"):
                error_msg = output.get(
                    "message",
                    "Task failed without details",
                )
                raise RuntimeError(
                    f"Out-painting task failed: {error_msg} (task_id: {task_id})",  # noqa
                )

            # else: PENDING / RUNNING → continue polling

        # Timeout
        raise TimeoutError(
            f"Out-painting task did not complete within {max_retries * retry_interval} seconds "  # noqa
            f"(task_id: {task_id}). Current status may still be PENDING/RUNNING.",  # noqa
        )
