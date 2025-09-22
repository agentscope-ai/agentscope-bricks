# -*- coding: utf-8 -*-
import asyncio
import os
import uuid
from typing import Any, Optional

import dashscope
from dashscope import AioMultiModalConversation
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.utils.tracing_utils.wrapper import trace
from agentscope_bricks.utils.api_key_util import ApiNames, get_api_key
from agentscope_bricks.utils.mcp_util import MCPUtil


class QwenTextToSpeechInput(BaseModel):
    """
    Qwen Image Edit Input
    """

    text: str = Field(
        ...,
        description="要合成的文本，支持中文、英文、中英混合输入。最长输入为512 Token",
    )
    voice: Optional[str] = Field(
        default=None,
        description="使用的音色，可选值Cherry,Serena,Ethan,Chelsie等",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class QwenTextToSpeechOutput(BaseModel):
    """
    Qwen Image Edit Output
    """

    result: str = Field(
        title="Results",
        description="输出的音频url",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class QwenTextToSpeech(
    Component[QwenTextToSpeechInput, QwenTextToSpeechOutput],
):
    """
    Qwen Text To Speech Component for AI-powered speech synthesis.
    """

    name: str = "modelstudio_qwen_tts"
    description: str = (
        "Qwen-TTS 是通义千问系列的语音合成模型，支持输入中文、英文、中英混合的文本，并流式输出音频。"
    )

    @trace(trace_type="AIGC", trace_name="qwen_tts")
    async def arun(
        self,
        args: QwenTextToSpeechInput,
        **kwargs: Any,
    ) -> QwenTextToSpeechOutput:
        """Qwen TTS using MultiModalConversation API

        This method uses DashScope service to synthesis audio based on text.

        Args:
            args: TextToSpeechInput containing text and voice.
            **kwargs: Additional keyword arguments including request_id,
                trace_event, model_name, api_key.

        Returns:
            TextToSpeechOutput containing the audio URL and request ID.

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
            os.getenv("QWEN_TEXT_TO_SPEECH_MODEL_NAME", "qwen-tts"),
        )

        try:
            response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
                api_key=api_key,
                model=model_name,
                text=args.text,
                voice=args.voice,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to call Qwen TTS API: {str(e)}")

        # Check response status
        if response.status_code != 200:
            error_msg = (
                f"HTTP status code: {response.status_code}, "
                f"Error code: {getattr(response, 'code', 'Unknown')}, "
                f"Error message:"
                f" {getattr(response, 'message', 'Unknown error')}"
            )
            raise RuntimeError(f"Qwen TTS API error: {error_msg}")

        # Extract the edited image URLs from response
        try:
            # The response structure may vary, try different possible locations
            result = response.output.audio["url"]

            if not result:
                raise RuntimeError(
                    f"Could not extract audio URLs from response: "
                    f"{response}",
                )

        except Exception as e:
            raise RuntimeError(
                f"Failed to parse response from Qwen TTS API: {str(e)}",
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
                        "qwen_tts_result": {
                            "status_code": response.status_code,
                            "result": result,
                        },
                    },
                },
            )

        return QwenTextToSpeechOutput(
            result=result,
            request_id=request_id,
        )


if __name__ == "__main__":
    qwen_text_to_speech = QwenTextToSpeech()

    async def main() -> None:
        import time

        test_inputs = [
            QwenTextToSpeechInput(
                text="沙滩上小男孩和一只金毛并排坐着",
            ),
            QwenTextToSpeechInput(
                text="沙滩上小女孩和一只柯基并排坐着",
            ),
        ]

        start_time = time.time()

        try:
            tasks = [
                qwen_text_to_speech.arun(test_input)
                for test_input in test_inputs
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
