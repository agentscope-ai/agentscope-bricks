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
    图生图Input
    """

    function: str = Field(
        ...,  # 必选
        description="图像编辑功能。支持 "
        "stylization_all、stylization_local、description_edit"
        "、description_edit_with_mask、remove_watermark、expand"
        "、super_resolution、colorization、doodle"
        "、control_cartoon_feature。",
    )
    base_image_url: str = Field(
        ...,  # 必选
        description="输入图像的URL地址，需为公网可访问地址，支持 HTTP 或 HTTPS "
        "协议。格式：JPG、JPEG、PNG、BMP、TIFF、WEBP，分辨率[512,"
        "4096]，大小不超过10MB。URL不能包含中文字符。",
    )
    mask_image_url: Optional[str] = Field(
        default=None,
        description="仅当function为description_edit_with_mask时必填，"
        "其余情况无需填写。要求：URL，分辨率与base_image_url一致，"
        "格式：JPG、JPEG、PNG、BMP、TIFF、WEBP，大小不超过10MB，"
        "白色为编辑区域，黑色为不变区域。",
    )
    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成图像中期望包含的元素和视觉特点,"
        "超过800自动截断",
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


class ImageEdit(Component[ImageGenInput, ImageGenOutput]):
    """
    图生图调用.
    """

    name: str = "modelstudio_image_edit"
    description: str = (
        "AI图像编辑（图生图）服务，输入原图URL、编辑功能、文本描述和分辨率，"
        "返回编辑后的图片URL。"
    )

    @trace(trace_type="AIGC", trace_name="image_edit")
    async def arun(self, args: ImageGenInput, **kwargs: Any) -> ImageGenOutput:
        """Modelstudio image editing from base image and text prompts

        This method wraps DashScope's ImageSynthesis service to generate new
        images based on the input image and editing instructions.  Supports
        various editing functions, resolutions, and batch generation.

        Args:
            args: ImageGenInput containing function, base_image_url,
                mask_image_url, prompt, size, n.
            **kwargs: Additional keyword arguments including request_id,
                trace_event, model_name, api_key.

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
            os.getenv("IMAGE_EDIT_MODEL_NAME", "wanx2.1-imageedit"),
        )

        watermark_env = os.getenv("IMAGE_EDIT_ENABLE_WATERMARK")
        if watermark_env is not None:
            watermark = strtobool(watermark_env)
        else:
            watermark = kwargs.pop("watermark", True)

        parameters = {}
        if args.n is not None:
            parameters["n"] = args.n
        if watermark is not None:
            parameters["watermark"] = watermark

        # 🔄 使用DashScope异步任务API实现真正的并发
        # 1. 提交异步任务
        task_response = await AioImageSynthesis.async_call(
            model=model_name,
            api_key=api_key,
            function=args.function,
            prompt=args.prompt,
            base_image_url=args.base_image_url,
            mask_image_url=args.mask_image_url,
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
                            f"Image editing failed: {res.output.task_status}",
                        )
                else:
                    # 如果没有task_status字段，认为已完成
                    break

            # 超时检查
            if time.time() - start_time > max_wait_time:
                raise TimeoutError(
                    f"Image editing timeout after {max_wait_time}s",
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

    image_generation = ImageEdit()

    image_gent_input = ImageGenInput(
        function="remove_watermark",
        base_image_url="https://mcdn.watermarkremover.ai/web-cdn"
        "/watermarkremover/production/anon-398e601a-53ca-4b50"
        "-959d-bc359ff85d31/img/1750251591975"
        "-b6b7cc6af66b4119371705687fc520b1.jpg",
        # mask_image_url="https://example.com/mask_image.jpg",
        prompt="去除图像中的水印",
        n=2,
    )

    async def main() -> None:
        image_gent_output = await image_generation.arun(image_gent_input)
        print(image_gent_output)
        print(image_generation.function_schema.model_dump())

    asyncio.run(main())
