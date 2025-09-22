# -*- coding: utf-8 -*-
from abc import abstractmethod
from enum import Enum
from typing import Any

from .__base import BaseComponent

"""
Support different model type and mainly support llm model
"""


class ModelType(Enum):
    """Enumeration of supported AI model types."""

    LLM = "llm"
    TEXT_EMBEDDING = "text-embedding"
    RERANK = "rerank"
    SPEECH2TEXT = "speech2text"
    MODERATION = "moderation"
    TTS = "tts"
    TEXT2IMG = "text2img"
    MULTIMODAL_EMBEDDING = "multimodal-embedding"


class AIModel(BaseComponent):
    """Base class for AI models with different capabilities."""

    model_type: ModelType

    def __init__(self, model_type: ModelType, **kwargs: Any):
        """Initialize the AI model with specified type.

        Args:
            model_type (ModelType): The type of AI model.
            **kwargs: Additional keyword arguments.
        """
        self.model_type = model_type

    @abstractmethod
    async def arun(self, *args: Any, **kwargs: Any) -> Any:
        """Run the AI model asynchronously.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Any: The result of the model execution.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError
