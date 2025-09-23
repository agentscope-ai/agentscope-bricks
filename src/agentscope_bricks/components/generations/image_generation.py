# -*- coding: utf-8 -*-
import asyncio
import os
import time
import uuid
from distutils.util import strtobool
from http import HTTPStatus
from typing import Any, Optional

from dashscope.aigc.image_synthesis import AioImageSynthesis
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace

from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.mcp_util import MCPUtil


class ImageGenInput(BaseModel):
    """
    文生图Input
    """

    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成图像中期望包含的元素和视觉特点,超过800自动截断",
    )
    size: Optional[str] = Field(
        default=None,
        description="输出图像的分辨率。默认值是1024*1024 最高可达200万像素",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制，超过500个字符自动截断",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启prompt智能改写，开启后使用大模型对输入prompt进行智能改写",
    )
    n: Optional[int] = Field(
        default=1,
        description="生成图片的数量。取值范围为1~4张 默认1",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class ImageGenOutput(BaseModel):
    """
    文生图 Output.
    """

    results: list[str] = Field(title="Results", description="输出图片url 列表")
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageGeneration(Component[ImageGenInput, ImageGenOutput]):
    """
    文生图调用.
    """

    name: str = "modelstudio_image_gen"
    description: str = (
        "AI绘画（图像生成）服务，输入文本描述和图像分辨率，返回根据文本信息绘制的图片URL。"
    )

    @trace(trace_type="AIGC", trace_name="image_generation")
    async def arun(self, args: ImageGenInput, **kwargs: Any) -> ImageGenOutput:
        """Modelstudio Images generation from text prompts

        This method wrap DashScope's ImageSynthesis service to generate images
        based on text descriptions. It supports various image sizes and can
        generate multiple images in a single request.

        Args:
            args: ImageGenInput containing the prompt, size, and number of
                images to generate.
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - trace_event: Optional trace event for logging
                - model_name: Model name to use (defaults to wan2.2-t2i-flash)
                - api_key: DashScope API key for authentication

        Returns:
            ImageGenOutput containing the list of generated image URLs and
            request ID.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid.
        """

        trace_event = kwargs.pop("trace_event", None)
        request_id = MCPUtil._get_mcp_dash_request_id(args.ctx)

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = kwargs.get(
            "model_name",
            os.getenv("IMAGE_GENERATION_MODEL_NAME", "wan2.2-t2i-flash"),
        )
        watermark_env = os.getenv("IMAGE_GENERATION_ENABLE_WATERMARK")
        if watermark_env is not None:
            watermark = strtobool(watermark_env)
        else:
            watermark = kwargs.pop("watermark", True)
        # 🔄 使用DashScope的异步任务API实现真正的并发
        # 1. 提交异步任务

        parameters = {}
        if args.size:
            parameters["size"] = args.size
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.n is not None:
            parameters["n"] = args.n
        if watermark is not None:
            parameters["watermark"] = watermark

        task_response = await AioImageSynthesis.async_call(
            model=model_name,
            api_key=api_key,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            **parameters,
        )

        # 2. 循环异步查询任务状态
        max_wait_time = 300  # 5分钟超时
        poll_interval = 2  # 2秒轮询间隔
        start_time = time.time()

        while True:
            # 异步等待
            await asyncio.sleep(poll_interval)

            # 查询任务结果
            res = await AioImageSynthesis.fetch(
                api_key=api_key,
                task=task_response,
            )

            # 检查任务是否完成
            if res.status_code == HTTPStatus.OK:
                if hasattr(res.output, "task_status"):
                    if res.output.task_status == "SUCCEEDED":
                        break
                    elif res.output.task_status in ["FAILED", "CANCELED"]:
                        raise RuntimeError(
                            f"Image generation failed: "
                            f"{res.output.task_status}",
                        )
                else:
                    # 如果没有task_status字段，认为已完成
                    break

            # 超时检查
            if time.time() - start_time > max_wait_time:
                raise TimeoutError(
                    f"Image generation timeout after {max_wait_time}s",
                )

        if request_id == "":
            request_id = (
                res.request_id if res.request_id else str(uuid.uuid4())
            )

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "image_query_result": res,
                    },
                },
            )
        results = []
        if res.status_code == HTTPStatus.OK:
            for result in res.output.results:
                results.append(result.url)
        return ImageGenOutput(results=results, request_id=request_id)


if __name__ == "__main__":

    image_generation = ImageGeneration()

    image_gent_input = ImageGenInput(
        prompt="帮我画一个国宝熊猫,",
    )

    async def main() -> None:
        image_gent_output = await image_generation.arun(
            image_gent_input,
            model_name="qwen-image",
        )
        print(image_gent_output)
        print(image_generation.function_schema.model_dump())

    asyncio.run(main())
