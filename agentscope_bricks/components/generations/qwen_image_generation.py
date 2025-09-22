# -*- coding: utf-8 -*-
import asyncio
import os
import uuid
from distutils.util import strtobool
from typing import Any, Optional

from dashscope import AioMultiModalConversation
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils import TraceType
from agentscope_bricks.utils.tracing_utils import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.mcp_util import MCPUtil


class QwenImageGenInput(BaseModel):
    """
    Qwen Image Edit Input
    """

    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成图像中期望包含的元素和视觉特点, 超过800个字符自动截断",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制，超过500个字符自动截断",
    )
    size: str = Field(
        default=None,
        description="输出图像的分辨率，格式为宽*高。默认分辨率为1328*1328",
    )
    n: int = Field(
        default=None,
        description="生成图片的数量。默认值为1。",
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


class QwenImageGenOutput(BaseModel):
    """
    Qwen Image Edit Output
    """

    results: list[str] = Field(
        title="Results",
        description="输出的图片url列表",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class QwenImageGen(Component[QwenImageGenInput, QwenImageGenOutput]):
    """
    Qwen Image Generation Component for AI-powered image editing.
    """

    name: str = "modelstudio_qwen_image_gen"
    description: str = (
        "通义千问-文生图模型是一款通用图像生成模型，支持多种艺术风格，尤其擅长复杂文本渲染，特别是中英文文本渲染。"
    )

    @trace(trace_type=TraceType.AIGC, trace_name="qwen_image_gen")
    async def arun(
        self,
        args: QwenImageGenInput,
        **kwargs: Any,
    ) -> QwenImageGenOutput:
        """Qwen Image Edit using MultiModalConversation API

        This method uses DashScope's MultiModalConversation service to edit
        images based on text prompts. The API supports various image editing
        operations through natural language instructions.

        Args:
            args: QwenImageGenInput containing text_prompt,
                watermark, and negative_prompt.
            **kwargs: Additional keyword arguments including request_id,
                trace_event, model_name, api_key.

        Returns:
            QwenImageEditOutput containing the edited image URL and request ID.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid.
            RuntimeError: If the API call fails or returns an error.
        """

        trace_event = kwargs.pop("trace_event", None)
        request_id = MCPUtil._get_mcp_dash_request_id(args.ctx)

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!")

        model_name = kwargs.get(
            "model_name",
            os.getenv("QWEN_IMAGE_GENERATION_MODEL_NAME", "qwen-image"),
        )
        watermark_env = os.getenv("QWEN_IMAGE_GENERATION_ENABLE_WATERMARK")
        if watermark_env is not None:
            watermark = strtobool(watermark_env)
        else:
            watermark = kwargs.pop("watermark", True)

        # Prepare messages in the format expected by MultiModalConversation
        messages = [
            {
                "role": "user",
                "content": [
                    {"text": args.prompt},
                ],
            },
        ]

        parameters = {}
        if args.negative_prompt:
            parameters["negative_prompt"] = args.negative_prompt
        if args.size:
            parameters["size"] = args.size
        if args.n is not None:
            parameters["n"] = args.n
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if watermark is not None:
            parameters["watermark"] = watermark

        # Call the AioMultiModalConversation API asynchronously
        try:
            response = await AioMultiModalConversation.call(
                api_key=api_key,
                model=model_name,
                messages=messages,
                **parameters,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to call Qwen Image Edit API: {str(e)}")

        # Check response status
        if response.status_code != 200:
            error_msg = (
                f"HTTP status code: {response.status_code}, "
                f"Error code: {getattr(response, 'code', 'Unknown')}, "
                f"Error message:"
                f" {getattr(response, 'message', 'Unknown error')}"
            )
            raise RuntimeError(f"Qwen Image Edit API error: {error_msg}")

        # Extract the edited image URLs from response
        try:
            # The response structure may vary, try different possible locations
            results = []

            # Try to get from output.choices[0].message.content
            if hasattr(response, "output") and response.output:
                choices = getattr(response.output, "choices", [])
                if choices:
                    message = getattr(choices[0], "message", {})
                    if hasattr(message, "content"):
                        content = message.content
                        if isinstance(content, list):
                            # Look for image content in the list
                            for item in content:
                                if isinstance(item, dict) and "image" in item:
                                    results.append(item["image"])
                        elif isinstance(content, str):
                            results.append(content)
                        elif isinstance(content, dict) and "image" in content:
                            results.append(content["image"])

            if not results:
                raise RuntimeError(
                    f"Could not extract edited image URLs from response: "
                    f"{response}",
                )

        except Exception as e:
            raise RuntimeError(
                f"Failed to parse response from Qwen Image Edit API: {str(e)}",
            )

        # Get request ID
        if request_id == "":
            request_id = getattr(response, "request_id", None) or str(
                uuid.uuid4(),
            )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "qwen_image_edit_result": {
                            "status_code": response.status_code,
                            "results": results,
                        },
                    },
                },
            )

        return QwenImageGenOutput(
            results=results,
            request_id=request_id,
        )


if __name__ == "__main__":
    qwen_image_gen = QwenImageGen()

    async def main() -> None:
        import time

        test_inputs = [
            QwenImageGenInput(
                prompt="沙滩上小男孩和一只金毛并排坐着",
                negative_prompt="",
            ),
            QwenImageGenInput(
                prompt="沙滩上小女孩和一只柯基并排坐着",
            ),
        ]

        start_time = time.time()

        try:
            tasks = [
                qwen_image_gen.arun(test_input) for test_input in test_inputs
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            end_time = time.time()
            total_time = end_time - start_time

            print(f"\nAll calls completed in {total_time:.2f} seconds")
            print("=" * 60)

            # Process and display results
            for i, result in enumerate(results, 1):
                print(f" 🆔 Request ID: {result.request_id}")
                print(f"\n📝 Call {i} Result:")
                if isinstance(result, Exception):
                    print(f"   ❌ Error: {str(result)}")
                else:
                    print(f"   🔗 Results: {result.results}")
                print("-" * 40)

        except Exception as e:
            print(f"❌ Unexpected error during concurrent execution: {str(e)}")

    asyncio.run(main())
