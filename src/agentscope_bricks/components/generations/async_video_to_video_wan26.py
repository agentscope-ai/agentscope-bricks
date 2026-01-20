# -*- coding: utf-8 -*-
import uuid
import json
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


class VideoToVideoGenerationWan26Input(BaseModel):
    """
    Input model for Alibaba Cloud Wan 2.6 Reference Video to Video Generation.
    """

    prompt: str = Field(
        ...,
        description="文本提示词，描述期望生成的视频内容。"
        "使用 character1, character2 模型仅通过此方式引用参考视频中的角色。",
    )
    reference_video_urls: list[str] = Field(
        ...,
        description="参考视频 URL 列表（1~3个），每个视频应只包含一个角色。传入多个视频时，按照数组顺序定义视频角色的顺序。"
        "第1个对应 character1，第2个对应 character2，依此类推。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，长度不超过500字符，超过部分会自动截断。",
    )
    size: Optional[str] = Field(
        default="1920*1080",
        description="视频分辨率，可选分辨率：720P、1080P对应的所有分辨率。"
        "默认为 1920*1080。",
    )
    duration: Optional[int] = Field(
        default=5,
        description="视频时长，单位秒。可选值：5 或 10。默认为 5。",
    )
    shot_type: Optional[str] = Field(
        default="single",
        description="镜头类型：'single'（单镜头）或 'multi'（多镜头）。默认为 'single'。"
        "参数优先级： shot_type > prompt 。例如，若 shot_type  设置为'single'，"
        "即使 prompt 中包含“生成多镜头视频”，模型仍会输出单镜头视频。",
    )
    watermark: Optional[bool] = Field(
        default=False,
        description="是否添加右下角水印 'AI 生成'。默认为 False。",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，取值范围 [0, 2147483647]，用于提升可复现性。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers "
        "for mcp only, don't generate it",
    )


class VideoToVideoGenerationWan26Output(BaseModel):
    task_id: str = Field(
        ...,
        description="异步视频生成任务 ID，可用于后续查询任务状态和结果。",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="请求唯一 ID，用于日志追踪。",
    )


class VideoToVideoW26Submit(
    Component[
        VideoToVideoGenerationWan26Input,
        VideoToVideoGenerationWan26Output,
    ],
):
    name: str = "modelstudio_video_to_video_wan26_submit_task"
    description: str = (
        "[版本: wan2.6] 通义万相参考生视频模型（wan2.6-r2v]）异步任务提交工具，"
        "基于参考视频的角色形象生成新视频，返回 task_id 供后续查询。"
    )

    @trace(trace_type="AIGC", trace_name="video_to_video_wan26_submit_task")
    async def arun(
        self,
        args: VideoToVideoGenerationWan26Input,
        **kwargs: Any,
    ) -> VideoToVideoGenerationWan26Output:
        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        input_data = {
            "prompt": args.prompt,
            "reference_video_urls": args.reference_video_urls,
        }
        if args.negative_prompt is not None:
            input_data["negative_prompt"] = args.negative_prompt
        parameters = {
            "size": args.size,
            "duration": args.duration,
            "shot_type": args.shot_type,
            "watermark": args.watermark,
        }
        if args.seed is not None:
            parameters["seed"] = args.seed

        payload = {
            "model": "wan2.6-r2v",
            "input": input_data,
            "parameters": parameters,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        create_url = f"{DASHSCOPE_API_BASE}/services/aigc/video-generation/video-synthesis"  # noqa

        async with aiohttp.ClientSession() as session:
            async with session.post(
                create_url,
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status != HTTPStatus.OK:
                    error_text = await resp.text()
                    raise RuntimeError(
                        f"Failed to create video task: {error_text}",
                    )

                response_json = await resp.json()
                task_id = response_json["output"]["task_id"]

        request_id = TracingUtil.get_request_id() or str(uuid.uuid4())

        return VideoToVideoGenerationWan26Output(
            task_id=task_id,
            request_id=request_id,
        )
