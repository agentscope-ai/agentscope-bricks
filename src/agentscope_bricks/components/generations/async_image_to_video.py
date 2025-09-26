# -*- coding: utf-8 -*-
import asyncio
import os
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


class ImageToVideoSubmitInput(BaseModel):
    """
    Input model for image-to-video generation submission.

    This model defines the input parameters required for submitting an
    image-to-video generation task to the DashScope API.
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


class ImageToVideoSubmitOutput(BaseModel):
    """
    Output model for image-to-video generation submission.

    This model contains the response data after successfully submitting
    an image-to-video generation task.
    """

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="视频生成的任务状态，PENDING：任务排队中，RUNNING：任务处理中，SUCCEEDED：任务执行成功，"
        "FAILED：任务执行失败，CANCELED：任务取消成功，UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageToVideoSubmit(
    Component[ImageToVideoSubmitInput, ImageToVideoSubmitOutput],
):
    """
    Service for submitting image-to-video generation tasks.

    This component provides functionality to submit asynchronous
    image-to-video generation tasks using DashScope's VideoSynthesis API.
    It supports various video effects and customization options.
    """

    name: str = "modelstudio_image_to_video_submit_task"
    description: str = (
        "通义万相-图生视频模型的异步任务提交工具。根据首帧图像和文本提示词，生成时长为5秒的无声视频。"
        "同时支持特效模板，可添加“魔法悬浮”、“气球膨胀”等效果，适用于创意视频制作、娱乐特效展示等场景。"
    )

    @trace(trace_type="AIGC", trace_name="image_to_video_submit")
    async def arun(
        self,
        args: ImageToVideoSubmitInput,
        **kwargs: Any,
    ) -> ImageToVideoSubmitOutput:
        """
        Submit an image-to-video generation task using DashScope API.

        This method asynchronously submits an image-to-video generation task
        to DashScope's VideoSynthesis service. It supports various video
        effects, resolution settings, and prompt enhancements.

        Args:
            args: ImageToVideoSubmitInput containing required image_url and
                  optional parameters for video generation
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name (defaults to wan2.2-i2v-flash)
                - api_key: DashScope API key for authentication

        Returns:
            ImageToVideoSubmitOutput containing the task ID, current status,
            and request ID for tracking the submission

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            RuntimeError: If video generation submission fails
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
        if args.resolution:
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
        response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            img_url=args.image_url,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            template=args.template,
            **parameters,
        )

        # Log trace event if provided
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

        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        result = ImageToVideoSubmitOutput(
            request_id=request_id,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
        )
        return result


class ImageToVideoFetchInput(BaseModel):
    """
    Input model for fetching image-to-video generation results.

    This model defines the input parameters required for retrieving
    the status and results of a previously submitted video generation task.
    """

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class ImageToVideoFetchOutput(BaseModel):
    """
    Output model for fetching image-to-video generation results.

    This model contains the response data including video URL, task status,
    and other metadata after fetching a video generation task result.
    """

    video_url: str = Field(
        title="Video URL",
        description="输出的视频url",
    )

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="视频生成的任务状态，PENDING：任务排队中，RUNNING：任务处理中，SUCCEEDED：任务执行成功，"
        "FAILED：任务执行失败，CANCELED：任务取消成功，UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageToVideoFetch(
    Component[ImageToVideoFetchInput, ImageToVideoFetchOutput],
):
    """
    Service for fetching image-to-video generation results.

    This component provides functionality to retrieve the status and
    results of asynchronous image-to-video generation tasks using
    DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_image_to_video_fetch_result"
    description: str = (
        "通义万相-图生视频模型的异步任务结果查询工具，根据Task ID查询任务结果。"
    )

    @trace(trace_type="AIGC", trace_name="image_to_video_fetch")
    async def arun(
        self,
        args: ImageToVideoFetchInput,
        **kwargs: Any,
    ) -> ImageToVideoFetchOutput:
        """
        Fetch the results of an image-to-video generation task.

        This method asynchronously retrieves the status and results of a
        previously submitted image-to-video generation task using the
        task ID returned from the submission.

        Args:
            args: ImageToVideoFetchInput containing the task_id parameter
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            ImageToVideoFetchOutput containing the video URL, current task
            status, and request ID

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            RuntimeError: If video fetch fails or response status is not OK
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = MCPUtil._get_mcp_dash_request_id(args.ctx)

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        # Create AioVideoSynthesis instance
        aio_video_synthesis = AioVideoSynthesis()

        response = await aio_video_synthesis.fetch(
            api_key=api_key,
            task=args.task_id,
        )

        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(f"Failed to get video URL: {response}")

        # Log trace event if provided
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

        # Handle request ID
        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        result = ImageToVideoFetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=request_id,
        )

        return result


if __name__ == "__main__":
    image_to_video_submit = ImageToVideoSubmit()
    image_to_video_fetch = ImageToVideoFetch()

    async def main() -> None:
        import time

        image_url = (
            "https://dashscope.oss-cn-beijing.aliyuncs.com"
            "/images/dog_and_girl.jpeg"
        )

        test_inputs = [
            ImageToVideoSubmitInput(
                image_url=image_url,
                prompt="女孩把小狗抱起来",
                resolution="1080P",
                prompt_extend=True,
            ),
            # ImageToVideoSubmitInput(
            #     image_url=image_url,
            #     prompt="小狗把女孩抱起来",
            #     resolution="480P",
            #     prompt_extend=True,
            # ),
        ]

        start_time = time.time()

        try:
            # Step 1: Submit async tasks concurrently
            print("📤 Submitting video generation tasks...")
            submit_tasks = [
                image_to_video_submit.arun(
                    test_input,
                )
                for test_input in test_inputs
            ]

            submit_results = await asyncio.gather(
                *submit_tasks,
                return_exceptions=True,
            )

            # Step 2: Extract task_ids from successful submissions
            task_ids = []
            for i, result in enumerate(submit_results, 1):
                print(f"\n📋 Task {i} Submission:")
                if isinstance(result, Exception):
                    print(f"   ❌ Error: {str(result)}")
                else:
                    print("   ✅ Submitted:")
                    print(f"   🆔 Task ID: {result.task_id}")
                    print(f"   📊 Status: {result.task_status}")
                    task_ids.append(result.task_id)

            if not task_ids:
                print("❌ No tasks were successfully submitted")
                return

            # Step 3: Poll for task completion using ImageToVideoFetch
            print(f"\n🔄 Polling for {len(task_ids)} task completions...")
            max_wait_time = 600  # 10 minutes timeout for video generation
            poll_interval = 5  # 5 seconds polling interval
            completed_tasks = {}

            poll_start_time = time.time()

            while len(completed_tasks) < len(task_ids):
                # Wait before polling
                await asyncio.sleep(poll_interval)

                # Create fetch tasks for incomplete tasks only
                remaining_task_ids = [
                    task_id
                    for task_id in task_ids
                    if task_id not in completed_tasks
                ]

                if not remaining_task_ids:
                    break

                fetch_tasks = [
                    image_to_video_fetch.arun(
                        ImageToVideoFetchInput(task_id=task_id),
                    )
                    for task_id in remaining_task_ids
                ]

                fetch_results = await asyncio.gather(
                    *fetch_tasks,
                    return_exceptions=True,
                )

                # Process fetch results
                for task_id, fetch_result in zip(
                    remaining_task_ids,
                    fetch_results,
                ):
                    if isinstance(fetch_result, Exception):
                        print(
                            f"⚠️  Task {task_id} fetch error: "
                            f"{str(fetch_result)}",
                        )
                        continue

                    status = fetch_result.task_status
                    print(f"📊 Task {task_id}: {status}")

                    if status == "SUCCEEDED":
                        completed_tasks[task_id] = fetch_result
                        print(f"   ✅ Video URL: {fetch_result.video_url}")
                    elif status in ["FAILED", "CANCELED"]:
                        completed_tasks[task_id] = fetch_result
                        print(f"   ❌ Task failed with status: {status}")
                    # For PENDING/RUNNING, continue polling

                # Check timeout
                if time.time() - poll_start_time > max_wait_time:
                    print(f"⏰ Polling timeout after {max_wait_time}s")
                    break

            end_time = time.time()
            total_time = end_time - start_time

            print(f"\n🎯 Execution completed in {total_time:.2f}s")
            print("=" * 60)

            # Display final results
            for i, task_id in enumerate(task_ids, 1):
                print(f"\n🎬 Task {i} Final Result:")
                if task_id in completed_tasks:
                    result = completed_tasks[task_id]
                    if result.task_status == "SUCCEEDED":
                        print("   ✅ Success:")
                        print(f"   🔗 Video URL: {result.video_url}")
                        print(f"   🆔 Request ID: {result.request_id}")
                    else:
                        print(
                            f"   ❌ Failed with status: {result.task_status}",
                        )
                else:
                    print("   ⏳ Incomplete (timeout)")
                print("-" * 40)

        except Exception as e:
            print(f"❌ Unexpected error during execution: {str(e)}")

    asyncio.run(main())
