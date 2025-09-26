# -*- coding: utf-8 -*-
import asyncio
import os
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.client.base_api import BaseAsyncAioApi
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.mcp_util import MCPUtil


class SpeechToVideoSubmitInput(BaseModel):
    """
    Speech to video generation input model
    """

    image_url: str = Field(
        ...,
        description="上传的图片URL。图像格式：支持jpg，jpeg，png，bmp，webp。"
        "图像分辨率：图像的宽度和高度范围为[400, 7000]像素。"
        "上传图片仅支持公网可访问的HTTP/HTTPS链接。",
    )
    audio_url: str = Field(
        ...,
        description="上传的音频文件URL。音频格式：格式为wav、mp3。"
        "音频限制：文件<15M，时长＜20s。"
        "音频内容：音频中需包含清晰、响亮的人声语音，并去除了环境噪音、"
        "背景音乐等声音干扰信息。上传音频仅支持公网可访问的HTTP/HTTPS链接。",
    )
    resolution: Optional[str] = Field(
        default=None,
        description="视频分辨率，默认不设置",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class SpeechToVideoSubmitOutput(BaseModel):
    """
    Speech to video generation output model
    """

    task_id: str = Field(
        title="Task ID",
        description="语音生成视频的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="语音生成视频的任务状态，PENDING：任务排队中，RUNNING：任务处理中，"
        "SUCCEEDED：任务执行成功，FAILED：任务执行失败，CANCELED：任务取消成功，"
        "UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class SpeechToVideoSubmit(
    Component[SpeechToVideoSubmitInput, SpeechToVideoSubmitOutput],
):
    """
    Speech to video generation service that converts speech and image into
    videos using DashScope's wan2.2-s2v API.
    """

    name: str = "modelstudio_speech_to_video_submit_task"
    description: str = (
        "数字人wan2.2-s2v模型的异步任务提交工具。能基于单张图片和音频，生成动作自然的说话、"
        "唱歌或表演视频。通过输入的人声音频，驱动静态图片中的人物实现口型、表情和动作与音频同步。"
        "支持说话、唱歌、表演三种对口型场景，支持真人及卡通人物，提供480P、720P两档分辨率选项。"
    )

    @staticmethod
    async def _async_call(
        model: str,
        api_key: str,
        image_url: str,
        audio_url: str,
        **parameters: Any,
    ) -> Any:
        """
        Submit async task for speech to video generation using BaseAsyncAioApi

        Args:
            model: Model name to use
            api_key: DashScope API key for authentication
            image_url: URL of the input image
            audio_url: URL of the input audio
            **parameters: Additional parameters like resolution

        Returns:
            Response containing task_id for polling
        """
        # Prepare input data
        input = {
            "image_url": image_url,
            "audio_url": audio_url,
        }

        result = await BaseAsyncAioApi.async_call(
            model=model,
            input=input,
            task_group="aigc",
            task="image2video",
            function="video-synthesis",
            api_key=api_key,
            **parameters,
        )

        return result

    @trace(trace_type="AIGC", trace_name="speech_to_video_submit")
    async def arun(
        self,
        args: SpeechToVideoSubmitInput,
        **kwargs: Any,
    ) -> SpeechToVideoSubmitOutput:
        """
        Submit speech to video generation task using DashScope wan2.2-s2v API

        This method wraps DashScope's wan2.2-s2v service to submit video
        generation tasks based on input image and audio. It uses async call
        pattern for better performance.

        Args:
            args: SpeechToVideoSubmitInput containing image_url, audio_url and
                  optional parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to wan2.2-s2v)
                - api_key: DashScope API key for authentication

        Returns:
            SpeechToVideoSubmitOutput containing the task ID, status and
            request ID

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            RuntimeError: If task submission fails
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = MCPUtil._get_mcp_dash_request_id(args.ctx)

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = kwargs.get(
            "model_name",
            os.getenv("SPEECH_TO_VIDEO_MODEL_NAME", "wan2.2-s2v"),
        )

        parameters = {}
        if args.resolution:
            parameters["resolution"] = args.resolution

        # Submit async task
        response = await self._async_call(
            model=model_name,
            api_key=api_key,
            image_url=args.image_url,
            audio_url=args.audio_url,
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

        # Extract task information from response
        if hasattr(response, "output") and hasattr(response.output, "task_id"):
            task_id = response.output.task_id
            task_status = getattr(response.output, "task_status", "PENDING")
        else:
            # Handle dict-style response
            if isinstance(response.output, dict):
                task_id = response.output.get("task_id")
                task_status = response.output.get("task_status", "PENDING")
            else:
                raise RuntimeError(f"Unexpected response format: {response}")

        result = SpeechToVideoSubmitOutput(
            request_id=request_id,
            task_id=task_id,
            task_status=task_status,
        )
        return result


class SpeechToVideoFetchInput(BaseModel):
    """
    Speech to video fetch task input model
    """

    task_id: str = Field(
        title="Task ID",
        description="语音生成视频的任务ID",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class SpeechToVideoFetchOutput(BaseModel):
    """
    Speech to video fetch task output model
    """

    video_url: Optional[str] = Field(
        default=None,
        title="Video URL",
        description="生成的视频文件URL，仅在任务成功完成时有值",
    )

    task_id: str = Field(
        title="Task ID",
        description="语音生成视频的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="语音生成视频的任务状态，PENDING：任务排队中，RUNNING：任务处理中，"
        "SUCCEEDED：任务执行成功，FAILED：任务执行失败，CANCELED：任务取消成功，"
        "UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )

    video_duration: Optional[float] = Field(
        default=None,
        title="Video Duration",
        description="视频时长（秒），用于计费",
    )


class SpeechToVideoFetch(
    Component[SpeechToVideoFetchInput, SpeechToVideoFetchOutput],
):
    """
    Speech to video fetch service that retrieves video generation results
    using DashScope's wan2.2-s2v API.
    """

    name: str = "modelstudio_speech_to_video_fetch_result"
    description: str = (
        "数字人wan2.2-s2v模型的异步任务结果查询工具，根据Task ID查询任务结果。"
    )

    @staticmethod
    async def _fetch(
        api_key: str,
        task: Any,
    ) -> Any:
        """
        Fetch task result using BaseAsyncAioApi

        Args:
            api_key: DashScope API key for authentication
            task: Task response containing task_id

        Returns:
            Response containing task status and result
        """
        # Use BaseAsyncAioApi.fetch directly with await
        result = await BaseAsyncAioApi.fetch(
            api_key=api_key,
            task=task,
        )

        return result

    @trace(trace_type="AIGC", trace_name="speech_to_video_fetch")
    async def arun(
        self,
        args: SpeechToVideoFetchInput,
        **kwargs: Any,
    ) -> SpeechToVideoFetchOutput:
        """
        Fetch speech to video generation result using DashScope wan2.2-s2v API

        This method wraps DashScope's wan2.2-s2v fetch service to retrieve
        video generation results based on task ID. It uses async call pattern
        for better performance.

        Args:
            args: SpeechToVideoFetchInput containing task_id parameter
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            SpeechToVideoFetchOutput containing the video URL, task status,
            request ID and video duration

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

        response = await self._fetch(
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

        # Extract task information from response
        if isinstance(response.output, dict):
            task_id = response.output.get("task_id", args.task_id)
            task_status = response.output.get("task_status", "UNKNOWN")

            # For completed tasks, extract video URL from results
            video_url = None
            if task_status == "SUCCEEDED" and "results" in response.output:
                results = response.output["results"]
                if isinstance(results, dict):
                    video_url = results.get("video_url")
                else:
                    video_url = getattr(results, "video_url", None)

                if not video_url:
                    raise RuntimeError(
                        f"Failed to extract video URL from response: "
                        f"{response}",
                    )
            elif task_status == "SUCCEEDED":
                # If task succeeded but no results found
                raise RuntimeError(
                    f"Task succeeded but no video URL found in response: "
                    f"{response.output}",
                )
            # For PENDING/RUNNING tasks, video_url will remain None
        else:
            raise RuntimeError(
                f"Unexpected response format: {response.output}",
            )

        # Extract video duration from usage
        video_duration = None
        if hasattr(response, "usage") and response.usage:
            if isinstance(response.usage, dict):
                video_duration = response.usage.get("duration")
            else:
                video_duration = getattr(response.usage, "duration", None)

        result = SpeechToVideoFetchOutput(
            video_url=video_url,
            task_id=task_id,
            task_status=task_status,
            request_id=request_id,
            video_duration=video_duration,
        )

        return result


if __name__ == "__main__":
    speech_to_video_submit = SpeechToVideoSubmit()
    speech_to_video_fetch = SpeechToVideoFetch()

    async def main() -> None:
        import time

        image_url = (
            "https://img.alicdn.com/imgextra/i3/O1CN011FObkp1T7Ttow"
            "oq4F_!!6000000002335-0-tps-1440-1797.jpg"
        )

        audio_url = (
            "https://help-static-aliyun-doc.aliyuncs.com/"
            "file-manage-files/zh-CN/20250825/iaqpio/input_audio.MP3"
        )

        test_inputs = [
            SpeechToVideoSubmitInput(
                image_url=image_url,
                audio_url=audio_url,
                resolution="480P",
            ),
            # SpeechToVideoSubmitInput(
            #     image_url=image_url,
            #     audio_url=audio_url,
            #     resolution="720P",
            # ),
        ]

        start_time = time.time()

        try:
            # Step 1: Submit async tasks concurrently
            print("📤 提交语音生成视频任务...")
            submit_tasks = [
                speech_to_video_submit.arun(
                    test_input,
                    model_name="wan2.2-s2v",
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
                print(f"\n📋 任务 {i} 提交结果:")
                if isinstance(result, Exception):
                    print(f"   ❌ 错误: {str(result)}")
                else:
                    print("   ✅ 已提交:")
                    print(f"   🆔 任务ID: {result.task_id}")
                    print(f"   📊 状态: {result.task_status}")
                    task_ids.append(result.task_id)

            if not task_ids:
                print("❌ 没有成功提交的任务")
                return

            # Step 3: Poll for task completion using SpeechToVideoFetch
            print(f"\n🔄 轮询 {len(task_ids)} 个任务的完成状态...")
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
                    speech_to_video_fetch.arun(
                        SpeechToVideoFetchInput(task_id=task_id),
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
                            f"⚠️  任务 {task_id} 查询错误: "
                            f"{str(fetch_result)}",
                        )
                        continue

                    status = fetch_result.task_status
                    print(f"📊 任务 {task_id}: {status}")

                    if status == "SUCCEEDED":
                        completed_tasks[task_id] = fetch_result
                        if fetch_result.video_url:
                            print(f"   ✅ 视频URL: {fetch_result.video_url}")
                        if fetch_result.video_duration:
                            print(
                                f"   ⏱️ 视频时长: {fetch_result.video_duration}秒",
                            )
                    elif status in ["FAILED", "CANCELED"]:
                        completed_tasks[task_id] = fetch_result
                        print(f"   ❌ 任务失败，状态: {status}")
                    # For PENDING/RUNNING, continue polling

                # Check timeout
                if time.time() - poll_start_time > max_wait_time:
                    print(f"⏰ 轮询超时，超过 {max_wait_time}秒")
                    break

            end_time = time.time()
            total_time = end_time - start_time

            print(f"\n🎯 执行完成，耗时 {total_time:.2f}秒")
            print("=" * 60)

            # Display final results
            for i, task_id in enumerate(task_ids, 1):
                print(f"\n🎬 任务 {i} 最终结果:")
                if task_id in completed_tasks:
                    result = completed_tasks[task_id]
                    if result.task_status == "SUCCEEDED":
                        print("   ✅ 成功:")
                        if result.video_url:
                            print(f"   🔗 视频URL: {result.video_url}")
                        print(f"   🆔 请求ID: {result.request_id}")
                        if result.video_duration:
                            print(f"   ⏱️ 视频时长: {result.video_duration}秒")
                    else:
                        print(
                            f"   ❌ 失败，状态: {result.task_status}",
                        )
                else:
                    print("   ⏳ 未完成（超时）")
                print("-" * 40)

        except Exception as e:
            print(f"❌ 执行过程中发生意外错误: {str(e)}")

    asyncio.run(main())
