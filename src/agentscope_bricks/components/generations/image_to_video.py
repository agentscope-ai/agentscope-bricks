# -*- coding: utf-8 -*-
import asyncio
import os
import time
import uuid
from distutils.util import strtobool
from http import HTTPStatus
from typing import Any, Optional

from dashscope.aigc.video_synthesis import AioVideoSynthesis
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace

from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.mcp_util import MCPUtil


class ImageToVideoInput(BaseModel):
    """
    Image to video generation input model
    """

    image_url: str = Field(
        ...,
        description="输入图像，支持公网URL、Base64编码或本地文件路径",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="正向提示词，用来描述生成视频中期望包含的元素和视觉特点",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在视频画面中看到的内容",
    )
    template: Optional[str] = Field(
        default=None,
        description="视频特效模板，可选值：squish（解压捏捏）、flying（魔法悬浮）、carousel（时光木马）等",
    )
    resolution: Optional[str] = Field(
        default=None,
        description="视频分辨率，默认不设置",
    )
    duration: Optional[int] = Field(
        default=None,
        description="视频生成时长，单位为秒，通常为5秒",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启prompt智能改写，开启后使用大模型对输入prompt进行智能改写",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class ImageToVideoOutput(BaseModel):
    """
    Image to video generation output model
    """

    video_url: str = Field(
        title="Video URL",
        description="输出的视频url",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageToVideo(Component[ImageToVideoInput, ImageToVideoOutput]):
    """
    Image to video generation service that converts images into videos
    using DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_image_to_video"
    description: str = (
        "通义万相-图生视频模型根据首帧图像和文本提示词，生成时长为5秒的无声视频。"
        "同时支持特效模板，可添加“魔法悬浮”、“气球膨胀”等效果，适用于创意视频制作、娱乐特效展示等场景。"
    )

    @trace(trace_type="AIGC", trace_name="image_to_video")
    async def arun(
        self,
        args: ImageToVideoInput,
        **kwargs: Any,
    ) -> ImageToVideoOutput:
        """
        Generate video from image using DashScope VideoSynthesis

        This method wraps DashScope's VideoSynthesis service to generate videos
        based on input images. It uses async call pattern for better
        performance and supports polling for task completion.

        Args:
            args: ImageToVideoInput containing required image_url and optional
                  parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to wan2.2-i2v-flash)
                - api_key: DashScope API key for authentication

        Returns:
            ImageToVideoOutput containing the generated video URL
                and request ID

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            TimeoutError: If video generation takes too long
            RuntimeError: If video generation fails
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = MCPUtil._get_mcp_dash_request_id(args.ctx)

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = kwargs.get(
            "model_name",
            os.getenv("IMAGE_TO_VIDEO_MODEL_NAME", "wan2.2-i2v-flash"),
        )
        watermark_env = os.getenv("IMAGE_TO_VIDEO_ENABLE_WATERMARK")
        if watermark_env is not None:
            watermark = strtobool(watermark_env)
        else:
            watermark = kwargs.pop("watermark", True)

        parameters = {}
        if args.resolution is not None:
            parameters["resolution"] = args.resolution
        if args.duration is not None:
            parameters["duration"] = args.duration
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if watermark is not None:
            parameters["watermark"] = watermark

        # Create AioVideoSynthesis instance
        aio_video_synthesis = AioVideoSynthesis()

        # Submit async task
        task_response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            img_url=args.image_url,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            template=args.template,
            **parameters,
        )

        # Poll for task completion using async methods
        max_wait_time = 600  # 10 minutes timeout for video generation
        poll_interval = 5  # 5 seconds polling interval
        start_time = time.time()

        while True:
            # Wait before polling
            await asyncio.sleep(poll_interval)

            # Fetch task result using async method
            res = await aio_video_synthesis.fetch(
                api_key=api_key,
                task=task_response,
            )

            # Check task completion status
            if res.status_code == HTTPStatus.OK:
                if hasattr(res.output, "task_status"):
                    if res.output.task_status == "SUCCEEDED":
                        break
                    elif res.output.task_status in ["FAILED", "CANCELED"]:
                        print(f"error response: {res}")
                        raise RuntimeError(
                            f"Video generation failed: task_status="
                            f"{res.output.task_status}, response={res}",
                        )
                else:
                    # If no task_status field, assume completed
                    break

            # Check timeout
            if time.time() - start_time > max_wait_time:
                raise TimeoutError(
                    f"Video generation timeout after {max_wait_time}s",
                )

        # Handle request ID
        if not request_id:
            request_id = (
                res.request_id if res.request_id else str(uuid.uuid4())
            )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "image_to_video_result": res,
                    },
                },
            )

        # Extract video URL from response
        if res.status_code == HTTPStatus.OK:
            video_url = res.output.video_url
            return ImageToVideoOutput(
                video_url=video_url,
                request_id=request_id,
            )
        else:
            raise RuntimeError(f"Failed to get video URL: {res.message}")


if __name__ == "__main__":
    image_to_video = ImageToVideo()

    async def main() -> None:
        import time

        image_url = (
            "https://dashscope.oss-cn-beijing.aliyuncs.com"
            "/images/dog_and_girl.jpeg"
        )

        test_inputs = [
            ImageToVideoInput(
                image_url=image_url,
                prompt="女孩把小狗抱起来",
                resolution="1080P",
                prompt_extend=True,
                # template="flying",
            ),
            ImageToVideoInput(
                image_url=image_url,
                prompt="小狗把女孩抱起来",
                resolution="480P",
                prompt_extend=True,
                # template="carousel"
            ),
        ]

        start_time = time.time()

        try:
            # Execute concurrent calls using asyncio.gather
            tasks = [
                image_to_video.arun(test_input) for test_input in test_inputs
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            end_time = time.time()
            total_time = end_time - start_time

            print(f"\nConcurrent execution completed in {total_time:.2f}s")
            print("=" * 60)

            # Process and display results
            for i, result in enumerate(results, 1):
                print(f"\n🎬 Task {i} Result:")
                if isinstance(result, Exception):
                    print(f"   ❌ Error: {str(result)}")
                else:
                    print("   ✅ Success:")
                    print(f"   🔗 Video URL: {result.video_url}")
                    print(f"   🆔 Request ID: {result.request_id}")
                print("-" * 40)

        except Exception as e:
            print(f"❌ Unexpected error during concurrent execution: {str(e)}")

    asyncio.run(main())
