# -*- coding: utf-8 -*-
from typing import Callable, Any

from agentscope_bricks.components.realtime_clients.azure_asr_client import (
    AzureAsrClient,
    AzureAsrCallbacks,
)
from agentscope_bricks.components.realtime_clients.modelstudio_asr_client import (  # noqa
    ModelstudioAsrClient,
    ModelstudioAsrCallbacks,
)
from agentscope_bricks.utils.schemas.realtime import (
    AsrConfig,
    ModelstudioAsrConfig,
    AzureAsrConfig,
    AsrVendor,
)


class AsrClientFactory:
    """
    Factory class for creating ASR client
    """

    @staticmethod
    def get_config(asr_vendor: AsrVendor, asr_config: AsrConfig):
        if asr_vendor == AsrVendor.MODELSTUDIO:
            return ModelstudioAsrConfig.model_validate(
                asr_config.model_dump(exclude_unset=True, exclude_none=True),
            )
        elif asr_vendor == AsrVendor.AZURE:
            return AzureAsrConfig.model_validate(
                asr_config.model_dump(exclude_unset=True, exclude_none=True),
            )
        else:
            return None

    @staticmethod
    def create_client(
        asr_vendor: AsrVendor,
        asr_config: Any,
        asr_callbacks: dict[str, Callable],
    ):
        if asr_vendor == AsrVendor.MODELSTUDIO:
            callbacks = ModelstudioAsrCallbacks.model_validate(asr_callbacks)
            return ModelstudioAsrClient(asr_config, callbacks)
        elif asr_vendor == AsrVendor.AZURE:
            callbacks = AzureAsrCallbacks.model_validate(asr_callbacks)
            return AzureAsrClient(asr_config, callbacks)
        else:
            return None
