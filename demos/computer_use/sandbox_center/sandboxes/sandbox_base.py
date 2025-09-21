# -*- coding: utf-8 -*-
import enum
import logging
from abc import ABC, abstractmethod
from typing import Callable

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler("cloud_log.log")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class DeviceType(enum.Enum):
    SANDBOX = "sandbox"
    CLOUD_COMPUTER = "cloud_computer"
    CLOUD_PHONE = "cloud_phone"


class OperationStatus(enum.Enum):
    DEVICE_UN_SUPPORTED_OPERATION = "Device did not supported this operation !"
    DEVICE_UN_SUPPORTED = "Did not supported this device !"


class SandboxBase(ABC):

    @abstractmethod
    async def run_command(
        self,
        command: str,
        background: bool = False,
        timeout: int = 5,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def go_home(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def press_key(
        self,
        key: str = None,
        key_combination: list[str] = None,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def long_press(self, x: int, y: int, press_time: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def type_text(self, text: str, ope_type: str = None) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    def click_element(
        self,
        query: str,
        click_command: Callable,
        action_name: str = "click",
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def click(
        self,
        x: int = 0,
        y: int = 0,
        count: int = 1,
        query: str = "",
        action_name: str = "click",
        ope_type: str = None,
        x2: int = 0,
        y2: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def right_click(
        self,
        x: int,
        y: int,
        count: int = 1,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def click_and_type(
        self,
        x: int,
        y: int,
        text: str,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def append_text(
        self,
        x: int,
        y: int,
        text: str,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def launch_app(self, app: str, ope_type: str = None) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    # @abstractmethod
    # def wait(self, ms: int = None, ope_type: str = None) -> str:
    #     """等待指定的时间（秒）"""
    #     if ms:
    #         time.sleep(ms)
    #         return f"The system has waited for {ms} seconds."
    #     else:
    #         wait_time = os.environ.get("OPERATION_WAIT_TIME", 15)
    #         time.sleep(int(wait_time))
    #         return f"This has been wait {wait_time} second"

    @abstractmethod
    async def slide(self, x1: int, y1: int, x2: int, y2: int) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def back(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def menu(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def enter(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    async def kill_front_app(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    @abstractmethod
    def execute_wait_time_set(self, execute_wait_time: int = 5) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value
