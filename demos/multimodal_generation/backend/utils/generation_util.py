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


async def generate_image_t2i(model: str, prompt: str) -> str:
    """
    Generate a single image based on the given prompt

    Args:
        model: model name
        prompt: Text description for image generation

    Returns:
        Generated image URL
    """
    if model.startswith("qwen"):
        image_gen = QwenImageGen()
        image_gen_input = QwenImageGenInput(
            prompt=prompt,
        )

        image_gen_output = await image_gen.arun(
            image_gen_input,
            model_name=model,
            **{"watermark": False},
        )

        if image_gen_output.results:
            return image_gen_output.results[0]
        else:
            logger.error(f"Failed to generate image for prompt: {prompt}")
            return ""
    else:
        image_gen = ImageGeneration()

        image_gen_input = ImageGenInput(
            prompt=prompt,
        )

        image_gen_output = await image_gen.arun(
            image_gen_input,
            model_name=model,
            **{"watermark": False},
        )

        if image_gen_output.results:
            return image_gen_output.results[0]
        else:
            logger.error(f"Failed to generate image for prompt: {prompt}")
            return ""
