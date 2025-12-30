# -*- coding: utf-8 -*-
import os
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.aigc.video_synthesis import AioVideoSynthesis
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.tracing_utils import TracingUtil


class ImageToVideoByFirstAndLastFrameWan22SubmitInput(BaseModel):
    """
    Input model for submitting a
    keyframe-to-video task using wan2.2-kf2v-flash.
    """

    first_frame_url: str = Field(
        ...,
        description="首帧图像，支持公网URL、Base64编码。",
    )
    last_frame_url: str = Field(
        ...,
        description="尾帧图像，支持公网URL、Base64编码。",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="正向提示词，描述希望视频中发生的动作或变化，例如“镜头缓慢推进，风吹动树叶”。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用于排除不希望出现的内容，例如“模糊、闪烁、变形、水印”。",
    )
    resolution: Optional[str] = Field(
        default=None,
        description="视频分辨率，可选值：'480P'、'720P'、'1080P'。默认为 '720P'。",
    )
    template: Optional[str] = Field(
        default=None,
        description="不同模型支持不同的特效模板。调用前请查阅视频特效列表，以免调用失败。",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="Prompt 智能改写。开启后可提升生成效果。默认值为 true。",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印。false（默认）：不添加；true：添加。",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，取值范围 [0, 2147483647]。用于提升结果可复现性，但不保证完全一致。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing "
        "headers for mcp only, don't generate it",
    )


class ImageToVideoByFirstAndLastFrameWan22SubmitOutput(BaseModel):
    """
    Output of the keyframe-to-video task submission.
    """

    task_id: str = Field(
        title="Task ID",
        description="异步任务的唯一标识符。",
    )
    task_status: str = Field(
        title="Task Status",
        description="视频生成的任务状态，PENDING：任务排队中，RUNNING：任务处理中，SUCCEEDED：任务执行成功，"
        "FAILED：任务执行失败，CANCELED：任务取消成功，UNKNOWN：任务不存在或状态未知",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="本次请求的唯一ID，可用于日志追踪。",
    )


class ImageToVideoByFirstAndLastFrameWan22Submit(
    Component[
        ImageToVideoByFirstAndLastFrameWan22SubmitInput,
        ImageToVideoByFirstAndLastFrameWan22SubmitOutput,
    ],
):
    """
    Submit a keyframe-to-video generation
    task using the wan2.2-kf2v-flash model.
    """

    name: str = (
        "modelstudio_image_to_video_by_first_and_last_frame_wan22_submit_task"
    )
    description: str = (
        "[版本: wan2.2] 通义万相首尾帧生视频模型（wan2.2-kf2v-flash）异步任务提交工具。\n"
        "基于首帧与尾帧图像及文本提示，生成一段流畅的无声视频（当前不支持音频输出）。\n"
    )

    @trace(
        trace_type="AIGC",
        trace_name="image_to_video_by_first_and_last_frame_wan22_submit",
    )
    async def arun(
        self,
        args: ImageToVideoByFirstAndLastFrameWan22SubmitInput,
        **kwargs: Any,
    ) -> ImageToVideoByFirstAndLastFrameWan22SubmitOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = kwargs.get(
            "model_name",
            os.getenv("IMAGE_TO_VIDEO_KF2V_MODEL_NAME", "wan2.2-kf2v-flash"),
        )

        # 构建 parameters（全部为可选参数）
        parameters = {}
        if args.resolution:
            parameters["resolution"] = args.resolution
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.watermark is not None:
            parameters["watermark"] = args.watermark
        if args.seed is not None:
            parameters["seed"] = args.seed
        if args.template:
            parameters["template"] = args.template
        aio_video_synthesis = AioVideoSynthesis()

        response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            first_frame_url=args.first_frame_url,
            last_frame_url=args.last_frame_url,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            **parameters,
        )

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "submit_task": response,
                    },
                },
            )

        if (
            response.status_code != HTTPStatus.OK
            or not response.output
            or response.output.task_status in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(
                f"Failed to submit keyframe-to-video task: {response}",
            )

        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        result = ImageToVideoByFirstAndLastFrameWan22SubmitOutput(
            request_id=request_id,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
        )
        return result


# ========== Fetch 部分 ==========


class ImageToVideoByFirstAndLastFrameWan22FetchInput(BaseModel):
    task_id: str = Field(
        title="Task ID",
        description="要查询的视频生成任务ID。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing "
        "headers for mcp only, don't generate it",
    )


class ImageToVideoByFirstAndLastFrameWan22FetchOutput(BaseModel):
    video_url: str = Field(
        title="Video URL",
        description="生成视频的公网可访问URL（MP4格式，无声）。有效期24小时，请及时下载。",
    )
    task_id: str = Field(
        title="Task ID",
        description="任务ID，与输入一致。",
    )
    task_status: str = Field(
        title="Task Status",
        description="任务最终状态，成功时为 SUCCEEDED。",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID，用于追踪。",
    )


class ImageToVideoByFirstAndLastFrameWan22Fetch(
    Component[
        ImageToVideoByFirstAndLastFrameWan22FetchInput,
        ImageToVideoByFirstAndLastFrameWan22FetchOutput,
    ],
):
    name: str = (
        "modelstudio_image_to_video_by_first_and_last_frame_wan22_fetch_result"
    )
    description: str = (
        "查询通义万相 wan2.2-kf2v-flash 首尾帧生视频任务的结果。\n"
        "输入 Task ID，返回生成的视频 URL 及任务状态。\n"
        "请在提交任务后轮询此接口，直到任务状态变为 SUCCEEDED。\n"
        "注意：video_url 有效期为 24 小时。"
    )

    @trace(
        trace_type="AIGC",
        trace_name="image_to_video_by_first_and_last_frame_wan22_fetch",
    )
    async def arun(
        self,
        args: ImageToVideoByFirstAndLastFrameWan22FetchInput,
        **kwargs: Any,
    ) -> ImageToVideoByFirstAndLastFrameWan22FetchOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        aio_video_synthesis = AioVideoSynthesis()

        response = await aio_video_synthesis.fetch(
            api_key=api_key,
            task=args.task_id,
        )

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": response.request_id,
                        "fetch_result": response,
                    },
                },
            )

        if (
            response.status_code != HTTPStatus.OK
            or not response.output
            or response.output.task_status in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(
                f"Failed to fetch keyframe-to-video result: {response}",
            )

        request_id = response.request_id or request_id or str(uuid.uuid4())

        return ImageToVideoByFirstAndLastFrameWan22FetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=request_id,
        )
