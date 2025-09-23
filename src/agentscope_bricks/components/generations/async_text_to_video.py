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


class TextToVideoSubmitInput(BaseModel):
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


class TextToVideoSubmitOutput(BaseModel):
    """
    Text to video generation output model
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


class TextToVideoSubmit(
    Component[TextToVideoSubmitInput, TextToVideoSubmitOutput],
):
    """
    Text to video generation service that converts text into videos
    using DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_text_to_video_submit_task"
    description: str = (
        "通义万相-文生视频模型的异步任务提交工具。可根据文本生成5秒无声视频，支持 480P、720P、1080P 多种分辨率档位，"
        "并在各档位下提供多个具体尺寸选项，以适配不同业务场景。"
    )

    @trace(trace_type="AIGC", trace_name="text_to_video_submit")
    async def arun(
        self,
        args: TextToVideoSubmitInput,
        **kwargs: Any,
    ) -> TextToVideoSubmitOutput:
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
        response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
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

        result = TextToVideoSubmitOutput(
            request_id=request_id,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
        )
        return result


class TextToVideoFetchInput(BaseModel):
    """
    Text to video fetch task input model
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


class TextToVideoFetchOutput(BaseModel):
    """
    Text to video fetch task output model
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


class TextToVideoFetch(
    Component[TextToVideoFetchInput, TextToVideoFetchOutput],
):
    """
    Text to video fetch service that retrieves video generation results
    using DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_text_to_video_fetch_result"
    description: str = (
        "通义万相-文生视频模型的异步任务结果查询工具，根据Task ID查询任务结果。"
    )

    @trace(trace_type="AIGC", trace_name="text_to_video_fetch")
    async def arun(
        self,
        args: TextToVideoFetchInput,
        **kwargs: Any,
    ) -> TextToVideoFetchOutput:
        """
        Fetch video generation result using DashScope VideoSynthesis

        This method wraps DashScope's VideoSynthesis fetch service to retrieve
        video generation results based on task ID. It uses async call pattern
        for better performance.

        Args:
            args: TextToVideoFetchInput containing task_id parameter
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            TextToVideoFetchOutput containing the video URL, task status and
            request ID

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

        result = TextToVideoFetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=request_id,
        )

        return result


if __name__ == "__main__":
    text_to_video_submit = TextToVideoSubmit()
    text_to_video_fetch = TextToVideoFetch()

    async def main() -> None:
        import time

        test_inputs = [
            TextToVideoSubmitInput(
                prompt="A cute panda playing in a bamboo forest, "
                "peaceful nature scene",
                negative_prompt="dark, scary, violent",
                prompt_extend=True,
            ),
            # AsyncTextToVideoSubmitInput(
            #     prompt="A golden retriever running on a beach during sunset",
            #     size="1920*1080",
            #     prompt_extend=True,
            # ),
        ]

        start_time = time.time()

        try:
            # Step 1: Submit async tasks concurrently
            print("📤 Submitting video generation tasks...")
            submit_tasks = [
                text_to_video_submit.arun(
                    test_input,
                    model_name="wan2.2-t2v-plus",
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

            # Step 3: Poll for task completion using AsyncTextToVideoFetch
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
                    text_to_video_fetch.arun(
                        TextToVideoFetchInput(task_id=task_id),
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
