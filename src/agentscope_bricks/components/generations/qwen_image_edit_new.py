# -*- coding: utf-8 -*-
import asyncio
import os
import uuid
from typing import Any, Optional, List

from dashscope import AioMultiModalConversation
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.tracing_utils import TracingUtil


class QwenImageEditNewInput(BaseModel):
    """
    Qwen Image Edit New Input (Supports multiple images)
    """

    image_urls: List[str] = Field(
        ...,
        description="输入图像的URL地址列表，每个URL需为公网可访问地址，支持 HTTP 或 HTTPS "
        "协议。格式：JPG、JPEG、PNG、BMP、TIFF、WEBP，分辨率[384, 3072]，大小不超过10MB。"
        "URL不能包含中文字符。",
    )
    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成图像中期望包含的元素和视觉特点，超过800个字符自动截断",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制，超过500个字符自动截断",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印，默认不设置。可设置为true或false。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, don't generate it",
    )


class QwenImageEditNewOutput(BaseModel):
    """
    Qwen Image Edit New Output
    """

    results: List[str] = Field(
        title="Results",
        description="输出的编辑后图片URL列表，顺序与输入 image_urls 一致",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class QwenImageEditNew(Component[QwenImageEditNewInput, QwenImageEditNewOutput]):
    """
    Qwen Image Edit New Component for AI-powered batch image editing.
    Supports multiple input images with the same editing instruction.
    """

    name: str = "modelstudio_qwen_image_edit_new"  # ⚠️ 必须唯一！
    description: str = (
        "通义千问-图像编辑模型（新版），支持批量处理多张图像。"
        "通过统一的文本指令对多张图像执行相同的编辑操作，如增删物体、调色、风格迁移等。"
    )

    @trace(trace_type="AIGC", trace_name="qwen_image_edit_new")
    async def arun(
        self,
        args: QwenImageEditNewInput,
        **kwargs: Any,
    ) -> QwenImageEditNewOutput:
        """Batch edit multiple images using Qwen Image Edit API.

        Each image in `image_urls` will be edited independently using the same prompt.

        Args:
            args: Contains image_urls (list), prompt, negative_prompt, watermark.
            **kwargs: Includes request_id, trace_event, model_name, api_key.

        Returns:
            QwenImageEditNewOutput with list of edited image URLs.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is missing.
            RuntimeError: If any API call fails or response is invalid.
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = kwargs.get(
            "model_name",
            os.getenv("QWEN_IMAGE_EDIT_MODEL_NAME", "qwen-image-edit"),
        )

        parameters = {}
        if args.negative_prompt:
            parameters["negative_prompt"] = args.negative_prompt
        if args.watermark is not None:
            parameters["watermark"] = args.watermark

        async def edit_single_image(image_url: str) -> str:
            """Edit one image and return its result URL."""
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": image_url},
                        {"text": args.prompt},
                    ],
                },
            ]
            try:
                response = await AioMultiModalConversation.call(
                    api_key=api_key,
                    model=model_name,
                    messages=messages,
                    **parameters,
                )
            except Exception as e:
                raise RuntimeError(f"API call failed for image {image_url}: {str(e)}")

            if response.status_code != 200 or not response.output:
                raise RuntimeError(f"Invalid response for {image_url}: {response}")

            # Parse response to extract image URL
            try:
                choices = getattr(response.output, "choices", [])
                if not choices:
                    raise RuntimeError("No choices in response")

                message = getattr(choices[0], "message", {})
                content = getattr(message, "content", [])

                if isinstance(content, str):
                    return content
                elif isinstance(content, dict) and "image" in content:
                    return content["image"]
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "image" in item:
                            return item["image"]
                raise RuntimeError("No image found in response content")
            except Exception as parse_error:
                raise RuntimeError(
                    f"Failed to parse response for {image_url}: {parse_error}"
                )

        # Concurrently process all images
        try:
            tasks = [edit_single_image(url) for url in args.image_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            raise RuntimeError(f"Batch processing failed: {str(e)}")

        # Handle exceptions in individual results
        final_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                # You may choose to skip, raise, or use placeholder
                raise RuntimeError(
                    f"Image {i} ({args.image_urls[i]}) failed: {res}"
                )
            else:
                final_results.append(res)

        if request_id == "":
            request_id = str(uuid.uuid4())

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "qwen_image_edit_new_result": {
                            "status": "success",
                            "result_count": len(final_results),
                        },
                    },
                },
            )

        return QwenImageEditNewOutput(
            results=final_results,
            request_id=request_id,
        )


if __name__ == "__main__":
    editor = QwenImageEditNew()

    async def main() -> None:
        # 示例：使用公开可访问的测试图片（请替换为你自己的公开图片）
        test_image_urls = [
            "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/1x6k9vz8h4b3a0/7c8e4f2a-9b1d-4f3e-8c7a-1e2d3f4g5h6i.png?Expires=...&OSSAccessKeyId=...&Signature=...",  # ❌ 注意：此链接可能失效
            # 建议改用你自己上传的公开图片，例如：
            # "https://your-public-bucket.oss-cn-shanghai.aliyuncs.com/test1.jpg",
            # "https://your-public-bucket.oss-cn-shanghai.aliyuncs.com/test2.jpg",
        ]

        # 如果没有可用的公开图片，先注释掉上面并使用单图测试
        if not test_image_urls or "dashscope-result" in test_image_urls[0]:
            print("⚠️ 警告：示例图片 URL 可能无权限访问，请替换为你的公开图片！")
            return

        input_data = QwenImageEditNewInput(
            image_urls=test_image_urls,
            prompt="给图中的每只狗戴上一顶红色的帽子",
            negative_prompt="模糊, 低质量, 失真",
            watermark=False,
        )

        try:
            start = asyncio.get_event_loop().time()
            output = await editor.arun(input_data)
            elapsed = asyncio.get_event_loop().time() - start

            print(f"✅ 成功编辑 {len(output.results)} 张图片，耗时: {elapsed:.2f} 秒")
            print(f"🆔 Request ID: {output.request_id}")
            for i, url in enumerate(output.results, 1):
                print(f"🔗 图片 {i}: {url}")

        except Exception as e:
            print(f"❌ 错误: {e}")

    asyncio.run(main())
