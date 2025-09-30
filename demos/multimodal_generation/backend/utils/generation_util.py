# -*- coding: utf-8 -*-
from agentscope_bricks.components.generations.image_generation import (
    ImageGenInput,
    ImageGeneration,
)
from agentscope_bricks.components.generations.qwen_image_generation import (
    QwenImageGenInput,
    QwenImageGen,
)
from agentscope_bricks.utils.logger_util import logger


async def generate_image_t2i(
    model: str,
    prompt: str,
    index: int = None,
) -> tuple[int, str] | str:
    """
    Generate a single image based on the given prompt

    Args:
        model: model name
        prompt: Text description for image generation
        index: Optional index to be returned with the result

    Returns:
        If index is provided: tuple of (index, Generated image URL)
        If index is None: Generated image URL (for backward compatibility)
    """
    if model.startswith("qwen"):
        image_gen = QwenImageGen()
        image_gen_input = QwenImageGenInput(
            prompt=prompt,
            size="1664*928",
        )

        image_gen_output = await image_gen.arun(
            image_gen_input,
            model_name=model,
            **{"watermark": False},
        )

        if image_gen_output.results:
            result = image_gen_output.results[0]
            return (index, result) if index is not None else result
        else:
            logger.error(f"Failed to generate image for prompt: {prompt}")
            error_result = ""
            return (index, error_result) if index is not None else error_result
    else:
        image_gen = ImageGeneration()

        image_gen_input = ImageGenInput(
            prompt=prompt,
            size="1280*720",
        )

        image_gen_output = await image_gen.arun(
            image_gen_input,
            model_name=model,
            **{"watermark": False},
        )

        if image_gen_output.results:
            result = image_gen_output.results[0]
            return (index, result) if index is not None else result
        else:
            logger.error(f"Failed to generate image for prompt: {prompt}")
            error_result = ""
            return (index, error_result) if index is not None else error_result
