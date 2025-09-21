# -*- coding: utf-8 -*-
import os
import threading

import aiohttp
import asyncio
import argparse
import time
import logging
from PIL import Image
from io import BytesIO
from pydantic import BaseModel
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_eds_aic20230930.client import Client as eds_aic20230930Client
from alibabacloud_eds_aic20230930 import models as eds_aic_20230930_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from demos.computer_use.sandbox_center.utils.oss_client import OSSClient
from demos.computer_use.sandbox_center.sandboxes.sandbox_base import (
    SandboxBase,
    OperationStatus,
)
from typing import Callable, Tuple, Optional, Any, List
import uuid
from agentscope_bricks.utils.logger_util import logger


execute_wait_time_: int = 5


class ClientPool:
    """客户端池管理器 - 单例模式管理共享客户端实例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._eds_client = None
            self._oss_client = None
            self._client_lock = threading.Lock()
            self._initialized = True

    def get_eds_client(self) -> "EdsClient":
        """获取共享的EdsClient实例"""
        if self._eds_client is None:
            with self._client_lock:
                if self._eds_client is None:
                    self._eds_client = EdsClient()
        return self._eds_client

    def get_oss_client(self) -> OSSClient:
        """获取共享的OSSClient实例"""
        if self._oss_client is None:
            with self._client_lock:
                if self._oss_client is None:
                    bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
                    endpoint = os.environ.get("EDS_OSS_ENDPOINT")
                    self._oss_client = OSSClient(bucket_name, endpoint)
        return self._oss_client


class CloudPhone(SandboxBase):
    def __init__(self, instance_id: str = ""):
        # 📝 直接使用传入的 instance_id，不再使用本地缓存
        logger.info("开始创建云手机对象")
        if not instance_id:
            instance_id = os.environ.get("EDS_INSTANCE_ID")

        if not instance_id:
            raise Exception(
                "instance_id is required for CloudPhone initialization",
            )

        # Store instance_id for later async initialization
        self._instance_id = instance_id
        self.instance_manager = None
        self._initialized = False

    async def initialize(self) -> None:
        logger.info("开始初始化云手机对象")
        """Async initialization method that must be called after constructor"""
        if not self._initialized:
            self.instance_manager = await self.get_instance_manager(
                self._instance_id,
            )
            if self.instance_manager is None:
                raise Exception(
                    "get instance manager failed, no phone cache available",
                )
            self._initialized = True

    def _ensure_initialized(self) -> None:
        """Helper method to check if async initialization was called"""
        if not self._initialized:
            raise Exception(
                "CloudPhone not initialized. Call 'await"
                " cloud_phone.initialize()' first.",
            )

    # 抽象方法重写
    def execute_wait_time_set(self, execute_wait_time: int = 5) -> str:
        execute_wait_time_ = execute_wait_time
        print("set slot time to " + str(execute_wait_time_))
        return "wait time has been set"

    async def run_command(
        self,
        command: str,
        background: bool = False,
        timeout: int = 5,
        ope_type: str = None,
    ) -> str:
        self._ensure_initialized()
        status, output = await self.instance_manager.run_command(command)
        return output + "\n" + f"{status}"

    async def go_home(self, action: str) -> str:
        self._ensure_initialized()
        await self.instance_manager.home()
        return f"This {action} has been done"

    async def press_key(
        self,
        key: str = None,
        key_combination: list[str] = None,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    async def long_press(self, x: int, y: int, press_time: str) -> str:
        self._ensure_initialized()
        await self.instance_manager.long_press(x, y, press_time)
        return "The key has been pressed."

    async def type_text(self, text: str, ope_type: str = None) -> str:
        self._ensure_initialized()
        await self.instance_manager.type(text)
        return f"The text '{text}' has been typed."

    def click_element(
        self,
        query: str,
        click_command: Callable,
        action_name: str = "click",
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

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
        self._ensure_initialized()
        await self.instance_manager.tab__(x, y, x2, y2, width, height)
        return f"The mouse has clicked  at ({x}, {y},{x2}, {y2})."

    async def right_click(
        self,
        x: int,
        y: int,
        count: int = 1,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    async def click_and_type(
        self,
        x: int,
        y: int,
        text: str,
        ope_type: str = None,
    ) -> str:
        self._ensure_initialized()
        await self.instance_manager.type(text)
        return f"The text '{text}' has been typed."

    async def append_text(
        self,
        x: int,
        y: int,
        text: str,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    async def launch_app(self, app: str, ope_type: str = None) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    async def slide(self, x1: int, y1: int, x2: int, y2: int) -> str:
        self._ensure_initialized()
        await self.instance_manager.slide(x1, y1, x2, y2)
        return f"Slided from ({x1}, {y1}) to ({x2}, {y2})."

    async def back(self, action: str) -> str:
        self._ensure_initialized()
        await self.instance_manager.back()
        return f"This {action} has been done"

    async def menu(self, action: str) -> str:
        self._ensure_initialized()
        await self.instance_manager.menu()
        return f"This {action} has been done"

    async def enter(self, action: str) -> str:
        self._ensure_initialized()
        await self.instance_manager.enter()
        return f"This {action} has been done"

    async def kill_front_app(self, action: str) -> str:
        self._ensure_initialized()
        await self.instance_manager.kill_the_front_app()
        return f"This {action} has been done"

    # 抽象方法重写结束

    async def get_instance_manager(self, instance_id: str) -> Any:
        retry = 3
        while retry > 0:
            try:
                logger.info(f"开始初始化云手机实例，尝试调用次数{retry}")
                # 📝 直接传入 instance_id，不使用本地缓存逻辑
                manager = await asyncio.to_thread(
                    EdsInstanceManager,
                    instance_id,
                )
                await manager.initialize()
                return manager
            except Exception as e:
                retry -= 1
                print(f"get manager error, retrying: remain {retry}, {e}")
                logger.error(
                    f"get manager error, retrying: remain {retry}, {e}",
                )
                await asyncio.sleep(5)
                continue
        return None

    async def upload_file_and_sign(self, filepath: str, file_name: str) -> str:
        self._ensure_initialized()
        return await self.instance_manager.in_upload_file_and_sign(
            filepath,
            file_name,
        )

    async def get_screenshot_oss_phone(
        self,
        max_retry: int = 5,
        file_name: str = None,
    ) -> str:
        self._ensure_initialized()
        for _ in range(max_retry):
            screen_url = await self.instance_manager.get_screenshot_sdk()
            # if screen_url and screen_url != 'Error':
            #     # 上传到新的OSS地址
            #     new_url = self.upload_screenshot_to_new_oss
            #     (screen_url, file_name)
            #     return new_url
            return screen_url
        return "Error"

    async def upload_screenshot_to_new_oss(
        self,
        original_url: str,
        new_file_name: str = None,
    ) -> str:
        """
        将原始截图上传到新的OSS地址并返回新URL

        Args:
            original_url (str): 原始截图的OSS URL
            new_file_name (str, optional): 新文件名，默认使用uuid生成唯一文件名

        Returns:
            str: 新的OSS URL地址
        """
        self._ensure_initialized()

        # 如果没有提供新文件名，则生成一个唯一的文件名
        if not new_file_name:
            new_file_name = f"{uuid.uuid4().hex}_screenshot.png"
        else:
            new_file_name = f"{uuid.uuid4().hex}_{new_file_name}"
        # 解析原始URL获取文件内容
        async with aiohttp.ClientSession() as session:
            async with session.get(original_url) as response:
                response.raise_for_status()
                content = await response.read()

        # 上传到新的OSS地址
        oss_client = self.instance_manager.oss_client
        new_url = await oss_client.async_oss_upload_data_and_sign(
            data=content,
            file_name=new_file_name,
            expire=3600 * 24 * 7,
        )

        return new_url

    async def operate(
        self,
        dummy_action: dict,
    ) -> Tuple[Optional[str], Optional[Tuple[Any, ...]]]:
        self._ensure_initialized()
        print(dummy_action)
        action_type = None
        action_param = None
        try:
            content = dummy_action["arguments"]
            if content["action"] == "click":
                x = content["coordinate"][0]
                y = content["coordinate"][1]
                await self.instance_manager.tap(x, y)
                action_type, action_param = "click", (x, y)

            elif content["action"] == "long_press":
                x = content["coordinate"][0]
                y = content["coordinate"][1]
                press_time = content["time"]
                await self.instance_manager.long_press(x, y, press_time)
                action_type, action_param = "long_press", (x, y, press_time)

            elif content["action"] == "swipe":
                x1 = content["coordinate"][0]
                y1 = content["coordinate"][1]
                x2 = content["coordinate2"][0]
                y2 = content["coordinate2"][1]
                await self.instance_manager.slide(x1, y1, x2, y2)
                action_type = "swipe"
                action_param = (x1, y1, x2, y2)

            elif content["action"] == "type":
                parameter = content["text"]
                await self.instance_manager.type(parameter)
                action_type, action_param = "Type", parameter

            elif content["action"] == "system_button":
                if content["button"] == "Back":
                    await self.instance_manager.back()
                    action_type = "Back"
                if content["button"] == "Home":
                    await self.instance_manager.home()
                    action_type = "Home"
                if content["button"] == "Menu":
                    await self.instance_manager.menu()
                    action_type = "Menu"
                if content["button"] == "Enter":
                    await self.instance_manager.enter()
                    action_type = "Enter"

            elif content["action"] == "terminate":
                action_type = "Done"
                action_param = content["status"]

            # 📝 移除 phone_cache 相关调用
            # self.instance_manager.phone_cache.send_heartbeat()

        except Exception as e:
            print("=" * 30)
            print(e)
            await self.instance_manager.kill_the_front_app()

        return action_type, action_param

    async def clear(self) -> None:
        self._ensure_initialized()
        await self.instance_manager.kill_the_front_app()


class EdsDeviceInfo(BaseModel):
    # 云手机设备信息查询字段返回类
    android_instance_name: str
    android_instance_id: str
    network_interface_ip: str
    android_instance_status: str


class EdsClient:

    def __init__(self) -> None:
        config = open_api_models.Config(
            access_key_id=os.environ.get("EDS_ALIBABA_CLOUD_ACCESS_KEY_ID"),
            # 您的AccessKey Secret,
            access_key_secret=os.environ.get(
                "EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
        )
        # Endpoint 请参考 https://api.aliyun.com/product/eds-aic
        config.endpoint = os.environ.get("EDS_ALIBABA_CLOUD_ENDPOINT")
        config.read_timeout = 6000
        self.__client__ = eds_aic20230930Client(config)

    def client_ticket_create(self, instance_id: str) -> Tuple[str, str, str]:
        logger.info(f"[{instance_id}]: create ticket")
        batch_get_acp_connection_ticket_request = (
            eds_aic_20230930_models.BatchGetAcpConnectionTicketRequest(
                instance_ids=[
                    instance_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = self.__client__.batch_get_acp_connection_ticket_with_options(
                batch_get_acp_connection_ticket_request,
                runtime,
            )
            info = rsp.body.instance_connection_models[0]
            logger.info(
                f"[{instance_id}]: create ticket success",
            )
            return (
                info.ticket,
                info.persistent_app_instance_id,
                info.app_instance_id,
            )
        except Exception as error:
            logger.error(
                f"[{instance_id}]: error when create ticket error:{error}",
            )
            return "", "", ""

    async def client_ticket_create_async(
        self,
        instance_id: str,
    ) -> Tuple[str, str, str]:
        logger.info(f"[{instance_id}]: start to create ticket")
        batch_get_acp_connection_ticket_request = (
            eds_aic_20230930_models.BatchGetAcpConnectionTicketRequest(
                instance_ids=[
                    instance_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self.__client__.batch_get_acp_connection_ticket_with_options_async(  # noqa E501
                batch_get_acp_connection_ticket_request,
                runtime,
            )
            info = rsp.body.instance_connection_models[0]
            logger.info(f"[{instance_id}]: create ticket success")
            return (
                info.ticket,
                info.persistent_app_instance_id,
                info.app_instance_id,
            )
        except Exception as error:
            logger.error(
                f"[{instance_id}]: error when create ticket error:{error}",
            )
            return "", "", ""

    def execute_command(
        self,
        instance_ids: List[str],
        command: str,
        timeout: int = 60,
    ) -> tuple[str, str | None]:
        logger.info(f"[{instance_ids}]: start to execute command: {command}")
        # 执行命令
        run_command_request = eds_aic_20230930_models.RunCommandRequest(
            instance_ids=instance_ids,
            command_content=command,
            timeout=timeout,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.run_command_with_options(
                run_command_request,
                runtime,
            )
            assert rsp.status_code == 200
            logger.info(
                f"[{instance_ids}]: execute command success",
            )
            invoke_id = rsp.body.invoke_id
            request_id = rsp.body.request_id
            # logging.info(invoke_id, request_id)
            return invoke_id, request_id
        except Exception as error:
            logger.error(
                f"[{instance_ids}]: error when excute command:"
                f" {command}, error:{error}",
            )
            return "", ""

    async def execute_command_async(
        self,
        instance_ids: List[str],
        command: str,
        timeout: int = 60,
    ) -> tuple[str, str | None]:
        # 执行命令
        run_command_request = eds_aic_20230930_models.RunCommandRequest(
            instance_ids=instance_ids,
            command_content=command,
            timeout=timeout,
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = await self.__client__.run_command_with_options_async(
                run_command_request,
                runtime,
            )

            assert rsp.status_code == 200
            invoke_id = rsp.body.invoke_id
            request_id = rsp.body.request_id
            # logging.info(invoke_id, request_id)
            return invoke_id, request_id
        except Exception as error:
            logger.error(
                f"[{instance_ids}]: error when excute command:"
                f" {command}, error:{error}",
            )
            return "", ""

    def query_execute_state(
        self,
        instance_ids: List[str],
        message_id: str,
    ) -> Any:
        # 查询命令执行结果
        describe_invocations_request = (
            eds_aic_20230930_models.DescribeInvocationsRequest(
                instance_ids=instance_ids,
                invocation_id=message_id,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.describe_invocations_with_options(
                describe_invocations_request,
                runtime,
            )
            # print(rsp.body)
            return rsp.body
        except Exception as error:
            UtilClient.assert_as_string(error)
            logger.error(
                f"[{instance_ids}]: error when query message:"
                f" {message_id}, error:{error}",
            )
            return None

    async def run_command_with_wait(
        self,
        instances_id: str,
        command: str,
        slot_time: float = None,
        timeout: int = 60,
    ) -> tuple[bool, str | None]:
        logger.info(f"[{instances_id}]: start to run command async:{command}")
        execute_id, request_id = await self.execute_command_async(
            [instances_id],
            command,
            timeout=timeout,
        )
        logger.info(f"[{instances_id}]: start to wait command")
        start_time = time.time()
        if not slot_time:
            if (
                "execute_wait_time_" in globals()
                and execute_wait_time_ is not None
            ):
                slot_time = execute_wait_time_
            else:
                slot_time = 3  # 默认值
        slot_time = max(0.5, slot_time)
        timeout = slot_time + timeout
        if execute_id:
            while timeout > 0:
                await asyncio.sleep(slot_time)
                msgs = self.query_execute_state(
                    [instances_id],
                    execute_id,
                )
                for msg in msgs.data:
                    if msg.invocation_status in [
                        "Success",
                        "Failed",
                        "Timeout",
                    ]:
                        print(
                            f"command cost time: "
                            f"{time.time() - start_time}",
                        )
                        logger.info(
                            f"[{instances_id}]: command status:"
                            f" {msg.invocation_status}",
                        )
                        return (
                            msg.invocation_status == "Success",
                            msg.output,
                        )
                timeout -= slot_time
        logger.error(f"[{instances_id}]: command timeout")
        raise Exception("command timeout")

    async def create_screenshot(self, instances_id: str) -> str:
        logger.info(f"[{instances_id}]: start to ask api to do screenshot")
        create_screenshot_request = (
            eds_aic_20230930_models.CreateScreenshotRequest(
                android_instance_id_list=[
                    instances_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = await self.__client__.create_screenshot_with_options_async(
                create_screenshot_request,
                runtime,
            )
            logger.info(
                f"[{instances_id}]: start to ask api to do screenshot success",
            )
            return rsp.body.tasks[0].task_id
        except Exception as error:
            logger.error(
                f"[{instances_id}]: error when ask api to do screenshot:"
                f" {error}",
            )
        return ""

    async def describe_tasks(self, task_ids: List[str]) -> str:
        logger.info(f"[{task_ids}]: start to wait task")
        describe_tasks_request = eds_aic_20230930_models.DescribeTasksRequest(
            task_ids=task_ids,
        )
        runtime = util_models.RuntimeOptions()
        retry = 3
        while retry > 0:
            try:
                await asyncio.sleep(1)
                # 复制代码运行请自行打印 API 的返回值
                rsp = await self.__client__.describe_tasks_with_options_async(
                    describe_tasks_request,
                    runtime,
                )
                result = rsp.body.data[0].result
                logger.info(f"[{task_ids}]: task result: {result}")
                if not result:
                    logger.error(
                        f"[{task_ids}]: task result is empty and retry",
                    )
                    retry += 1
                    continue
                return result
            except Exception as error:
                retry -= 1
                logger.error(f"[{task_ids}]: task result error: {error}")
        return ""

    def list_instance(
        self,
        page_size: Optional[int] = 10,
        next_token: Optional[int] = None,
        status: Optional[int] = None,
        instance_ids: List[str] = None,
    ) -> Any:
        logger.info(f"start to list instances {instance_ids}")
        describe_android_instances_request = (
            eds_aic_20230930_models.DescribeAndroidInstancesRequest(
                max_results=page_size,
                next_token=next_token,
                status=status,
                android_instance_ids=instance_ids,
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.describe_android_instances_with_options(
                describe_android_instances_request,
                runtime,
            )
            devices_info = [
                EdsDeviceInfo(**inst.__dict__)
                for inst in rsp.body.instance_model
            ]
            logger.info(f"list instances success: {devices_info}")
            return rsp.body.total_count, rsp.body.next_token, devices_info
        except Exception as error:
            logger.error("list wuying mobile failed:", error)
            return 0, None, []

    def list_all_instance(
        self,
        page_size: int = 5,
        status: str = "RUNNING",
    ) -> List[EdsDeviceInfo]:
        instances = []
        count, next_token, page_instances = self.list_instance(
            page_size=page_size,
            next_token=None,
        )
        instances += page_instances
        while next_token is not None:
            _, next_token, page_instances = self.list_instance(
                page_size=page_size,
                next_token=next_token,
            )
            instances += page_instances
            # print("------", next_token)
        return instances

    async def restart_equipment(self, instance_id: str) -> None:
        logger.info(f"[{instance_id}]: start to restart equipment")
        reboot_android_instances_in_group_request = (
            eds_aic_20230930_models.RebootAndroidInstancesInGroupRequest(
                android_instance_ids=[
                    instance_id,
                ],
                force_stop=True,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            method = e_c.reboot_android_instances_in_group_with_options_async
            rsp = await method(
                reboot_android_instances_in_group_request,
                runtime,
            )
            logger.info(
                f"[{instance_id}]: restart equipment ask api success,"
                f" and wait finish",
            )
            print(rsp)
        except Exception as error:
            logger.info(
                f"restart equipment failed:{error}",
            )

    def stop_desktops(self, instance_id: str) -> int:
        logger.info(f"[{instance_id}]: start to stop instance")
        stop_android_instance_request = (
            eds_aic_20230930_models.StopAndroidInstanceRequest(
                android_instance_ids=[
                    instance_id,
                ],
            )
        )

        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.stop_android_instance_with_options(
                stop_android_instance_request,
                runtime,
            )
            logger.info(
                f"[{instance_id}]: stop instance ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"stop_desktops failed:{error}")
        return 400

    async def reset_equipment(self, instance_id: str) -> int:
        logger.info(f"[{instance_id}]: start to reset equipment")
        reset_android_instances_in_group_request = (
            eds_aic_20230930_models.ResetAndroidInstancesInGroupRequest(
                android_instance_ids=[
                    instance_id,
                ],
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            e_c = self.__client__
            method = e_c.reset_android_instances_in_group_with_options_async
            rsp = await method(
                reset_android_instances_in_group_request,
                runtime,
            )
            logger.info(
                f"[{instance_id}]: reset equipment ask api success,"
                f" and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"reset_equipment failed:{error}")
        return 400

    def rebuild_equipment_image(self, instance_id: str, image_id: str) -> int:
        logger.info(f"[{instance_id}]: start to rebuild equipment image")
        update_instance_image_request = (
            eds_aic_20230930_models.UpdateInstanceImageRequest(
                instance_id_list=[
                    instance_id,
                ],
                image_id=image_id,
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            rsp = self.__client__.update_instance_image_with_options(
                update_instance_image_request,
                runtime,
            )
            logger.info(
                f"[{instance_id}]: rebuild equipment image ask api "
                f"success, and wait finish",
            )
            return rsp.status_code
        except Exception as error:
            logger.error(f"rebuild_equipment_image failed:{error}")
        return 400


class EdsInstanceManager:
    def __init__(self, instance_id: str = ""):
        # 📝 直接使用传入的 instance_id，移除本地缓存逻辑
        if not instance_id:
            logger.error(
                "instance_id is required for "
                "EdsInstanceManager initialization",
            )
            raise Exception(
                "instance_id is required for "
                "EdsInstanceManager initialization",
            )

        self.instance_id = instance_id
        self.client_pool = ClientPool()
        self.eds_client = self.client_pool.get_eds_client()
        self.oss_client = self.client_pool.get_oss_client()
        bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
        endpoint = os.environ.get("EDS_OSS_ENDPOINT")
        # self.oss_client = OSSClient(bucket_name, endpoint)
        self.endpoint = endpoint
        self.des_oss_dir = f"oss://{bucket_name}/__mPLUG__/{self.instance_id}/"
        self.oss_ak = (os.environ.get("EDS_OSS_ACCESS_KEY_ID"),)
        self.oss_sk = os.environ.get("EDS_OSS_ACCESS_KEY_SECRET")
        self._initialized = False
        self.ticket = None
        self.person_app_id = None
        self.app_instance_id = None

    async def initialize(self):
        """异步初始化方法"""
        if not self._initialized:
            logger.info(f"实例{self.instance_id}:Initializing...")
            (
                self.ticket,
                self.person_app_id,
                self.app_instance_id,
            ) = await self.eds_client.client_ticket_create_async(
                self.instance_id,
            )
            self._initialized = True
            logger.info(f"实例{self.instance_id}:初始化成功")

    def _ensure_initialized(self):
        if not self._initialized:
            logger.warning(f"实例{self.instance_id}:请先初始化")
            raise Exception(
                "Manager not initialized. Call await initialize() first.",
            )

    # 🚫 run_list_instance 函数已被移除，因为设备分配现在由 backend.py 统一管理

    async def get_screenshot_sdk(self) -> str:
        logger.info(f"实例{self.instance_id}:获取截图")
        task_id = await self.eds_client.create_screenshot(self.instance_id)
        logger.info(
            f"实例{self.instance_id}:截图任务创建成功，task_id:{task_id}",
        )
        result = await self.eds_client.describe_tasks([task_id])
        return result

    async def in_upload_file_and_sign(
        self,
        filepath: str,
        file_name: str,
    ) -> str:
        return await self.oss_client.async_oss_upload_file_and_sign(
            filepath,
            file_name,
        )

    async def get_screenshot(self) -> str:
        local_file_name = f"{uuid.uuid4().hex}__screenshot.png"
        mobile_screen_file_path = f"/sdcard/{local_file_name}"
        des_oss_sub_path = f"__mPLUG__/{self.instance_id}/{local_file_name}"
        print(
            f"mobile path: {mobile_screen_file_path} , "
            f"des_oss_sub_path: {des_oss_sub_path}",
        )
        logger.info(
            f"mobile path: {mobile_screen_file_path}"
            f"des_oss_sub_path: {des_oss_sub_path}",
        )
        retry = 3
        while retry > 0:
            try:
                logger.info(f"实例{self.instance_id}:获取截图")
                status, output = await self.eds_client.run_command_with_wait(
                    self.instance_id,
                    f"screencap {mobile_screen_file_path} "
                    f"&& md5sum {mobile_screen_file_path}",
                )
                logger.info(
                    f"实例{self.instance_id}:获取截图{status}{output},开始上传oss",
                )
                await self.eds_client.run_command_with_wait(
                    self.instance_id,
                    f"ossutil cp {mobile_screen_file_path} {self.des_oss_dir}"
                    f" -i {self.oss_ak} -k {self.oss_sk} -e {self.endpoint}",
                )

                screen_url = await self.oss_client.async_get_url(
                    des_oss_sub_path,
                )
                logger.info(
                    f"实例{self.instance_id}:获取截图成功{screen_url}"
                    f",开始删除手机文件",
                )
                await self.eds_client.execute_command_async(
                    [self.instance_id],
                    f"rm {mobile_screen_file_path}",
                )
                if screen_url is None:
                    logger.error("screen_shot is None")
                    raise Exception("screen_shot is None")
                return screen_url
            except Exception as e:
                retry -= 1
                logger.error(
                    f"screen_shot error {e}" f", retrying: remain {retry}",
                )
                continue
        return ""

    async def tab__(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        width: int,
        height: int,
    ) -> tuple[bool, str | None]:
        x, y = int((x1 + x2) / 2), int((y1 + y2) / 2)
        input_x = int(x / 1000 * width)
        input_y = int(y / 1000 * height)
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input tap {input_x} {input_y}",
        )

    async def tab_(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> tuple[bool, str | None]:
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input tap {center_x} {center_y}",
        )

    async def tap(self, x: int, y: int) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input tap {x} {y}",
        )

    async def long_press(
        self,
        x: int,
        y: int,
        press_time: str,
    ) -> tuple[bool, str | None]:
        time_ms = int(press_time) * 1000
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input swipe {x} {y} {x} {y} {time_ms}",
        )

    async def download_and_install_apk(
        self,
        oss_url: str,
        apk_name: str,
    ) -> tuple[bool, str]:
        """
        从OSS地址下载APK文件并安装

        Args:
            oss_url (str): APK文件的OSS下载地址
            apk_name (str): APK文件名

        Returns:
            tuple: (status, response) 安装状态和响应信息
        """
        # 下载APK文件到云手机
        download_path = f"/data/local/tmp/{apk_name}"
        # download_command = f"curl -o {download_path} {oss_url}"
        # 合并下载和安装命令，使用分号分隔
        combined_command = (
            f"curl -o {download_path} {oss_url} && pm install {download_path}"
        )

        try:
            status, rsp = await self.eds_client.run_command_with_wait(
                self.instance_id,
                combined_command,
            )

            if not status:
                return False, f"下载或安装失败: {rsp or '未知错误'}"

            # 判断安装是否成功（检查输出中是否包含Success）
            if rsp and "Success" in rsp:
                return True, rsp
            else:
                return False, f"安装失败: {rsp or '未知错误'}"

        except Exception as e:
            return False, f"下载并安装APK时出错: {str(e)}"

    async def check_and_setup_app(
        self,
        internal_oss_url: str,
        app_name: str,
    ) -> tuple[bool, str | None]:
        if internal_oss_url is None or app_name is None:
            return False, "param is empty"

        status_in, rsp_in = await self.download_and_install_apk(
            internal_oss_url,
            app_name,
        )

        # 返回原来的输入法ID，以便后续恢复
        return status_in, rsp_in

    async def type(self, text: str) -> str | None:
        time_start = time.time()
        # 转义文本内容
        escaped_text = text.replace('"', '\\"').replace("'", "\\'")

        # 组合完整命令：检查输入法 -> 安装ADBKeyboard(如需要) ->
        # 启用并设置ADBKeyboard -> 发送文本 -> 禁用ADBKeyboard
        # 注意：这里简化处理，假设ADBKeyboard已经安装
        combined_command = (
            f"ime enable com.android.adbkeyboard/.AdbIME && "
            f"ime set com.android.adbkeyboard/.AdbIME && "
            f"sleep 0.3 && "
            f'am broadcast -a ADB_INPUT_TEXT --es msg "{escaped_text}" && '
            f"sleep 0.2 && "
            f"ime disable com.android.adbkeyboard/.AdbIME"
        )

        status, rsp = await self.eds_client.run_command_with_wait(
            self.instance_id,
            combined_command,
            slot_time=0.5,
        )
        print(rsp)
        print(f"输入文字耗时：{time.time() - time_start}")
        return rsp

    async def slide(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            f"input swipe {x1} {y1} {x2} {y2} 500",
        )

    async def back(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            "input keyevent KEYCODE_BACK",
        )

    async def home(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            "am start -a android.intent.action.MAIN"
            " -c android.intent.category.HOME",
        )

    async def menu(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            "input keyevent 82",
        )

    async def enter(self) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            "input keyevent 66",
        )

    async def kill_the_front_app(self) -> tuple[bool, str | None]:
        command = (
            "am force-stop $(dumpsys activity activities | "
            "grep mResumedActivity"
            " | awk '{print $4}' | cut -d "
            "'/' -f 1)"
        )
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            command,
        )

    async def run_command(self, command: str) -> tuple[bool, str | None]:
        return await self.eds_client.run_command_with_wait(
            self.instance_id,
            command,
        )
