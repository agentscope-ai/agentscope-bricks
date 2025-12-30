# -*- coding: utf-8 -*-
import os
import uuid
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


class ImageOutPaintingSubmitInput(BaseModel):
    """
    Input model for submitting an image out-painting (expansion) task.
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


class ImageOutPaintingSubmitOutput(BaseModel):
    task_id: str = Field(
        title="Task ID",
        description="异步任务的唯一标识符，有效期 24 小时。",
    )
    task_status: str = Field(
        title="Task Status",
        description="任务状态：PENDING（排队中）、RUNNING（处理中）、"
        "SUCCEEDED（成功）、FAILED（失败）等。",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求唯一 ID，用于日志追踪。",
    )


class ImageOutPaintingSubmit(
    Component[ImageOutPaintingSubmitInput, ImageOutPaintingSubmitOutput],
):
    name: str = "modelstudio_image_out_painting_submit"
    description: str = (
        "图像画面扩展（扩图）异步任务提交工具，基于image-out-painting 模型。\n"
        "支持三种扩图方式（按优先级）：\n"
        "1. 按宽高比（output_ratio）\n"
        "2. 按比例缩放（x_scale / y_scale）\n"
        "3. 指定方向像素填充（top/bottom/left/right_offset）\n"
        "可选旋转（angle），先旋转后扩图。"
    )

    @trace(trace_type="AIGC", trace_name="image_out_painting_submit")
    async def arun(
        self,
        args: ImageOutPaintingSubmitInput,
        **kwargs: Any,
    ) -> ImageOutPaintingSubmitOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        # 构建 parameters 字典（只包含非 None 值）
        parameters: Dict[str, Any] = {}
        if args.angle is not None:
            parameters["angle"] = args.angle
        if args.output_ratio is not None:
            parameters["output_ratio"] = args.output_ratio
        if args.x_scale is not None:
            parameters["x_scale"] = args.x_scale
        if args.y_scale is not None:
            parameters["y_scale"] = args.y_scale
        if args.top_offset is not None:
            parameters["top_offset"] = args.top_offset
        if args.bottom_offset is not None:
            parameters["bottom_offset"] = args.bottom_offset
        if args.left_offset is not None:
            parameters["left_offset"] = args.left_offset
        if args.right_offset is not None:
            parameters["right_offset"] = args.right_offset
        if args.best_quality is not None:
            parameters["best_quality"] = args.best_quality
        if args.limit_image_size is not None:
            parameters["limit_image_size"] = args.limit_image_size
        if args.add_watermark is not None:
            parameters["add_watermark"] = args.add_watermark

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
                    "step_suffix": "submit_response",
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

        output = response_json["output"]
        task_id = output["task_id"]
        task_status = output["task_status"]
        actual_request_id = (
            response_json.get("request_id") or request_id or str(uuid.uuid4())
        )

        return ImageOutPaintingSubmitOutput(
            task_id=task_id,
            task_status=task_status,
            request_id=actual_request_id,
        )


# ==================== Fetch Result ====================


class ImageOutPaintingFetchInput(BaseModel):
    task_id: str = Field(
        ...,
        description="要查询的扩图任务 ID。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing "
        "headers for mcp only, don't generate it",
    )


class ImageOutPaintingFetchOutput(BaseModel):
    output_image_url: str = Field(
        ...,
        description="扩图后生成的图像公网 URL（PNG/JPG 等格式）。",
    )
    task_id: str = Field(
        ...,
        description="任务 ID，与输入一致。",
    )
    task_status: str = Field(
        ...,
        description="任务最终状态，成功时为 SUCCEEDED。",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="请求 ID，用于追踪。",
    )


class ImageOutPaintingFetch(
    Component[ImageOutPaintingFetchInput, ImageOutPaintingFetchOutput],
):
    name: str = "modelstudio_image_out_painting_fetch"
    description: str = (
        "查询图像画面扩展（扩图）任务的结果。\n"
        "输入 Task ID，返回扩图后的图像 URL 和任务状态。\n"
        "请在提交任务后轮询此接口，直到状态变为 SUCCEEDED。"
    )

    @trace(trace_type="AIGC", trace_name="image_out_painting_fetch")
    async def arun(
        self,
        args: ImageOutPaintingFetchInput,
        **kwargs: Any,
    ) -> ImageOutPaintingFetchOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{DASHSCOPE_API_BASE}/tasks/{args.task_id}",
                headers=headers,
            ) as resp:
                status_code = resp.status
                response_json = await resp.json()

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "fetch_response",
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
                f"Failed to fetch out-painting result: {error_msg} (code: {status_code})",  # noqa
            )

        output = response_json["output"]
        task_status = output["task_status"]

        if task_status in ["FAILED", "CANCELED"]:
            error_msg = output.get("message", "Task failed")
            raise RuntimeError(f"Out-painting task failed: {error_msg}")

        if task_status != "SUCCEEDED":
            raise RuntimeError(
                f"Task not completed yet. Current status: {task_status}",
            )

        output_image_url = output["output_image_url"]
        actual_request_id = (
            response_json.get("request_id") or request_id or str(uuid.uuid4())
        )

        return ImageOutPaintingFetchOutput(
            output_image_url=output_image_url,
            task_id=output["task_id"],
            task_status=task_status,
            request_id=actual_request_id,
        )
