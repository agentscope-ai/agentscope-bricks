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


class TextToVideoInput(BaseModel):
    """
    Text to video generation input model
    """

    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成视频中期望包含的元素和视觉特点, 超过800个字符自动截断",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在视频画面中看到的内容，可以对视频画面进行限制，超过500个字符自动截断",
    )
    size: Optional[str] = Field(
        default=None,
        description="视频分辨率，默认不设置",
    )
    duration: Optional[int] = Field(
        default=None,
        description="视频生成时长，单位为秒",
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


class TextToVideoOutput(BaseModel):
    """
    Text to video generation output model
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


class TextToVideo(Component[TextToVideoInput, TextToVideoOutput]):
    """
    Text to video generation service that converts text into videos
    using DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_text_to_video"
    description: str = (
        "通义万相-文生视频模型可根据文本生成5秒无声视频，支持 480P、720P、1080P 多种分辨率档位，"
        "并在各档位下提供多个具体尺寸选项，以适配不同业务场景。"
    )

    @trace(trace_type="AIGC", trace_name="text_to_video")
    async def arun(
        self,
        args: TextToVideoInput,
        **kwargs: Any,
    ) -> TextToVideoOutput:
        """
        Generate video from text prompt using DashScope VideoSynthesis

        This method wraps DashScope's VideoSynthesis service to generate videos
        based on text descriptions. It uses async call pattern for better
        performance and supports polling for task completion.

        Args:
            args: TextToVideoInput containing optional parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to wan2.2-t2v-plus)
                - api_key: DashScope API key for authentication

        Returns:
            TextToVideoOutput containing the generated video URL and request ID

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
            os.getenv("TEXT_TO_VIDEO_MODEL_NAME", "wan2.2-t2v-plus"),
        )

        watermark_env = os.getenv("TEXT_TO_VIDEO_ENABLE_WATERMARK")
        if watermark_env is not None:
            watermark = strtobool(watermark_env)
        else:
            watermark = kwargs.pop("watermark", True)

        parameters = {}
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.size:
            parameters["size"] = args.size
        if args.duration is not None:
            parameters["duration"] = args.duration
        if watermark is not None:
            parameters["watermark"] = watermark

        # Create AioVideoSynthesis instance
        aio_video_synthesis = AioVideoSynthesis()

        # Submit async task
        task_response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
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
                        "text_to_video_result": res,
                    },
                },
            )

        # Extract video URL from response
        if res.status_code == HTTPStatus.OK:
            video_url = res.output.video_url
            return TextToVideoOutput(
                video_url=video_url,
                request_id=request_id,
            )
        else:
            raise RuntimeError(f"Failed to get video URL: {res.message}")


if __name__ == "__main__":
    text_to_video = TextToVideo()

    async def main() -> None:
        import time

        test_inputs = [
            TextToVideoInput(
                prompt="A cute panda playing in a bamboo forest, "
                "peaceful nature scene",
                size="1920*1080",
                negative_prompt="dark, scary, violent",
                prompt_extend=True,
            ),
            TextToVideoInput(
                prompt="A golden retriever running on a beach during sunset",
                size="1920*1080",
                prompt_extend=True,
            ),
        ]

        start_time = time.time()

        try:
            # Execute concurrent calls using asyncio.gather
            tasks = [
                text_to_video.arun(test_input) for test_input in test_inputs
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
