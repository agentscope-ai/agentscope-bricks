# -*- coding: utf-8 -*-
import asyncio
import time
import os
import json
import requests
import uuid
import weakref
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
from advanced_version.computer_use_server.computer_use_agent import (  # noqa E501
    ComputerUseAgent,
)
from agents.agent import AgentRequest
from redis_resource_allocator import (
    AllocationStatus,
)
from cua_utils import init_sandbox
from enum import Enum

# 导入Redis状态管理器
from advanced_version.computer_use_server.redis_state_manager import (  # noqa E501
    RedisStateManager,
)

# 云设备导入
from sandbox_center.sandboxes.cloud_phone_wy import (
    CloudPhone,
)
from sandbox_center.sandboxes.cloud_computer_wy import (
    CloudComputer,
)

from agentscope_bricks.utils.logger_util import logger
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional
from pydantic import ConfigDict

load_dotenv()

app = FastAPI(title="Computer Use Agent Backend", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 资源池配置

# 从环境变量获取PHONE_INSTANCE_IDS，如果未设置则使用默认值
PHONE_INSTANCE_IDS = os.getenv("PHONE_INSTANCE_IDS", "").split(",")
PHONE_INSTANCE_IDS = [id.strip() for id in PHONE_INSTANCE_IDS if id.strip()]


# 从环境变量获取DESKTOP_IDS，如果未设置则使用默认值
DESKTOP_IDS = os.getenv("DESKTOP_IDS", "").split(",")
DESKTOP_IDS = [id.strip() for id in DESKTOP_IDS if id.strip()]


def _serialize(obj):
    """把任意 Python 对象序列化成可打印 / 可 JSON 化的 dict / list / 基础类型"""
    # 1. 基础类型
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj

    # 2. 字典
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}

    # 3. 列表 / 元组 / 集合
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(v) for v in obj]

    # 4. 具有 __dict__ 的普通对象
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items()}

    # 5. 具有 __slots__ 的对象
    if hasattr(obj, "__slots__"):
        return {
            name: _serialize(getattr(obj, name))
            for name in obj.__slots__
            if hasattr(obj, name)
        }

    # 6. 其它：返回可读字符串
    return repr(obj)


# utils
def _purge_queue(q: asyncio.Queue):
    while not q.empty():
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            break


async def _wait_for_pc_ready(
    equipment,
    desktop_id: str,
    max_wait_time: int = 300,
    stability_check_duration: int = 10,
):
    """
    异步等待PC设备就绪，增加稳定性检查

    Args:
        equipment: CloudComputer实例
        desktop_id: 桌面ID
        max_wait_time: 最大等待时间（秒），默认5分钟
        stability_check_duration: 稳定性检查时长（秒），确保设备持续运行状态
    """
    start_time = time.time()
    stable_start_time = None

    while True:
        try:
            # 将同步的状态检查操作放到线程池中执行
            pc_info = await asyncio.to_thread(
                equipment.instance_manager.ecd_client.search_desktop_info,
                [desktop_id],
            )

            if pc_info and pc_info[0].desktop_status.lower() == "running":
                # 第一次检测到运行状态，开始稳定性检查
                if stable_start_time is None:
                    stable_start_time = time.time()
                    logger.info(
                        f"PC {desktop_id} status: running, starting "
                        f"stability check...",
                    )

                # 检查设备是否已稳定运行足够长时间
                stable_duration = time.time() - stable_start_time
                if stable_duration >= stability_check_duration:
                    logger.info(
                        f"✓ PC {desktop_id} is stable and ready "
                        f"(stable for {stable_duration:.1f}s)",
                    )
                    break
                else:
                    logger.info(
                        f"PC {desktop_id} stability check: "
                        f"{stable_duration:.1f}s"
                        f"/{stability_check_duration}s",
                    )
            else:
                # 状态不是运行中，重置稳定性检查
                if stable_start_time is not None:
                    logger.info(
                        f"PC {desktop_id} status changed, "
                        f"resetting stability check",
                    )
                    stable_start_time = None
                current_status = (
                    pc_info[0].desktop_status.lower() if pc_info else "unknown"
                )
                logger.info(
                    f"PC {desktop_id} status: {current_status}, waiting...",
                )
            # 检查是否超时
            if time.time() - start_time > max_wait_time:
                logger.error(
                    f"PC {desktop_id} failed to become ready within"
                    f" {max_wait_time} seconds",
                )

        except Exception as e:
            logger.error(f"Error checking PC status for {desktop_id}: {e}")
            # 出现异常时重置稳定性检查
            stable_start_time = None

        await asyncio.sleep(3)  # 减少检查间隔，更精确的监控


async def _wait_for_phone_ready(
    equipment,
    instance_id: str,
    max_wait_time: int = 300,
):
    """
    异步等待手机设备就绪

    Args:
        equipment: CloudPhone实例
        instance_id: 实例ID
        max_wait_time: 最大等待时间（秒），默认5分钟
    """
    start_time = time.time()
    while True:
        try:
            # 将同步的状态检查操作放到线程池中执行
            total_count, next_token, devices_info = await asyncio.to_thread(
                equipment.instance_manager.eds_client.list_instance,
                instance_ids=[instance_id],
            )

            if (
                devices_info
                and devices_info[0].android_instance_status.lower()
                == "running"
            ):
                logger.info(f"✓ Phone {instance_id} is ready")
                break

            # 检查是否超时
            if time.time() - start_time > max_wait_time:
                logger.error(
                    f"Phone {instance_id} failed to become ready within"
                    f" {max_wait_time} seconds",
                )
                raise TimeoutError(
                    f"Phone {instance_id} failed to become ready within"
                    f" {max_wait_time} seconds",
                )

        except Exception as e:
            logger.error(f"Error checking phone status for {instance_id}: {e}")

        await asyncio.sleep(5)


# 环境操作状态枚举
class EnvironmentOperationStatus(Enum):
    """环境操作状态"""

    IDLE = "idle"  # 空闲
    INITIALIZING = "initializing"  # 初始化中
    SWITCHING = "switching"  # 切换中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败
    QUEUED = "queued"  # 排队中
    WAITING_RETRY = "waiting_retry"  # 等待重试


class EnvironmentOperation:
    """环境操作任务"""

    def __init__(
        self,
        operation_id: str,
        operation_type: str,
        config: dict,
        user_id: str,
        chat_id: str,
    ):
        self.operation_id = operation_id
        self.operation_type = operation_type  # "init" or "switch"
        self.config = config
        self.user_id = user_id
        self.chat_id = chat_id
        self.status = EnvironmentOperationStatus.IDLE
        self.message = ""
        self.progress = 0  # 0-100
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
        self.background_task = None

    def to_dict(self):
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "status": self.status.value,
            "message": self.message,
            "progress": self.progress,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "result": _serialize(self.result) if self.result else None,
            "error": self.error,
        }


# 全局状态管理器
state_manager = None


if not hasattr(app.state, "running_agents"):
    app.state.running_agents = weakref.WeakValueDictionary()


async def validate_user_session(
    user_id: str,
    chat_id: str,
    strict_mode: bool = True,
) -> bool:
    """
    验证用户会话的有效性

    Args:
        user_id: 用户ID
        chat_id: 会话ID
        strict_mode: 严格模式下，非活跃会话会拒绝请求；非严格模式下，仅记录警告

    Returns:
        bool: 会话是否有效
    """
    try:
        is_valid = await state_manager.validate_user_active_chat(
            user_id,
            chat_id,
        )

        if not is_valid:
            if strict_mode:
                logger.info(
                    f"Rejected request: Invalid chat session for user "
                    f"{user_id}, chat {chat_id}",
                )
                raise HTTPException(
                    status_code=403,
                    detail={
                        "message": "Invalid chat session. Another session "
                        "may be active for this user.",
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "type": "session_conflict",
                    },
                )
            else:
                logger.warning(
                    f"⚠️ Warning: Invalid chat session for user "
                    f"{user_id}, chat {chat_id}",
                )

        return is_valid

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session validation error for {user_id}:{chat_id}: {e}")
        if strict_mode:
            raise HTTPException(
                status_code=500,
                detail="Session validation failed",
            )
        return False


@app.on_event("startup")
async def startup_event():
    global state_manager
    # 使用Redis状态管理器
    state_manager = RedisStateManager(
        phone_instance_ids=PHONE_INSTANCE_IDS,
        desktop_ids=DESKTOP_IDS,
    )
    await state_manager.initialize()

    # 启动心跳监控任务
    asyncio.create_task(state_manager._monitor_heartbeats())
    logger.info("Backend startup completed with Redis state manager")


# 请求/响应模型
class MessageContent(BaseModel):
    type: str
    text: Optional[str] = None
    image: Optional[str] = None


class Message(BaseModel):
    role: str
    content: List[MessageContent]


class AgentConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    mode: str = "qwen_vl"
    sandbox_type: str = "e2b-desktop"
    save_logs: bool = True
    timeout: int = 120
    pc_use_addon_info: str = ""
    max_steps: int = 15
    user_id: str = ""
    chat_id: str = ""
    e2e_info: list = []
    extra_params: str = ""

    @model_validator(mode="after")
    def set_defaults_based_on_mode(self):
        # 只有当 sandbox_type 是默认值时才根据 mode 设置新值
        if self.sandbox_type == "e2b-desktop":  # 默认值
            if self.mode == "pc_use":
                self.sandbox_type = "pc_wuyin"
            elif self.mode == "phone_use":
                self.sandbox_type = "phone_wuyin"
        return self

    @field_validator("e2e_info", mode="before")
    @classmethod
    def set_e2e_info_defaults(cls, v, info):
        mode = info.data.get("mode") if "mode" in info.data else "qwen_vl"
        if mode == "pc_use":
            default_e2e_info = [
                {"pipeline_name": "pre-pc-agent-e"},
                {"pipeline_type": "agent"},
                {"use_add_info_generate": "false"},
                {"model_name": "pre-gui_owl_7b"},
                {"device_type": "pc"},
            ]

            # 如果没有提供e2e_info或者为空，则使用默认值
            if not v:
                return default_e2e_info
            else:
                # 如果提供了e2e_info，合并默认值和提供的值
                if isinstance(v, list):
                    # 创建默认值字典以便查找
                    default_dict = {}
                    for item in default_e2e_info:
                        default_dict.update(item)

                    # 合并逻辑：将用户提供的字典与默认字典合并
                    merged = []
                    user_dict = {}
                    for item in v:
                        if isinstance(item, dict):
                            user_dict.update(item)

                    # 对于每个默认键，如果用户提供了该键且值不为空，则使用用户值，否则使用默认值
                    for key, default_value in default_dict.items():
                        user_value = user_dict.get(key)
                        # 当用户传入的值为空（None, "", 空列表等）时，使用默认值
                        if user_value is not None and user_value != "":
                            merged.append({key: user_value})
                        else:
                            merged.append({key: default_value})
                    return merged
                else:
                    return default_e2e_info
        elif mode == "phone_use":
            default_e2e_info = [
                {"device_type": "mobile"},
                {"model_name": "pre-gui_owl_7b"},
                {"pipeline_type": "agent"},
                {"pipeline_name": "mobile-agent-pipeline"},
                {"use_add_info_generate": "false"},
            ]

            # 如果没有提供e2e_info或者为空，则使用默认值
            if not v:
                return default_e2e_info
            else:
                # 如果提供了e2e_info，合并默认值和提供的值
                if isinstance(v, list):
                    # 创建默认值字典以便查找
                    default_dict = {}
                    for item in default_e2e_info:
                        default_dict.update(item)

                    # 合并逻辑：将用户提供的字典与默认字典合并
                    merged = []
                    user_dict = {}
                    for item in v:
                        if isinstance(item, dict):
                            user_dict.update(item)

                    # 对于每个默认键，如果用户提供了该键且值不为空，则使用用户值，否则使用默认值
                    for key, default_value in default_dict.items():
                        user_value = user_dict.get(key)
                        # 当用户传入的值为空（None, "", 空列表等）时，使用默认值
                        if user_value is not None and user_value != "":
                            merged.append({key: user_value})
                        else:
                            merged.append({key: default_value})
                    return merged
                else:
                    return default_e2e_info
        # 如果v不为空但mode不是pc_use或phone_use，则直接返回原始值
        return v if v else []


class ComputerUseRequest(AgentRequest):
    """扩展的Agent请求，包含ComputerUse特定配置"""

    config: Optional[AgentConfig] = AgentConfig()
    sequence_number: Optional[int] = None  # 新增：序列号参数，用于断线续传
    user_id: str = ""


class RunRequest(BaseModel):
    messages: List[Message]
    config: Optional[AgentConfig] = AgentConfig()


class InitRequest(BaseModel):
    config: Optional[AgentConfig] = AgentConfig()
    user_id: str = ""


class UserChatRequest(BaseModel):
    user_id: str
    chat_id: str


async def get_equipment(
    user_id: str,
    chat_id: str,
    config: AgentConfig,
) -> dict:
    """
    设备查询
    注意：这里重新使用锁，因为 run_task 已经在锁外调用
    """
    chat_state = await state_manager.get_chat_state(user_id, chat_id)

    # 📝 恢复使用锁，确保设备初始化的原子性
    async with chat_state.lock:
        sandbox_type = config.sandbox_type
        task_id = str(uuid.uuid4())
        static_url = config.static_url
        logger.info(
            f"启动中: {chat_id}-{sandbox_type}\n",
        )

        if chat_state.equipment is not None:
            logger.info(f"设备已存在: {chat_id}-{sandbox_type}")
            if sandbox_type == "pc_wuyin":
                instance_m = chat_state.equipment.instance_manager

                # 验证PC设备状态和auth_code有效性
                try:
                    # 检查设备状态
                    pc_info = await asyncio.to_thread(
                        instance_m.ecd_client.search_desktop_info,
                        [instance_m.desktop_id],
                    )

                    if (
                        not pc_info
                        or pc_info[0].desktop_status.lower() != "running"
                    ):
                        logger.warning(
                            f"PC设备状态异常，重新初始化: {instance_m.desktop_id}",
                        )
                        # 清理旧设备
                        chat_state.equipment = None
                        # 递归调用，重新初始化设备
                        return await get_equipment(user_id, chat_id, config)

                    # 重新获取auth_code确保有效性
                    logger.info(
                        f"重新获取auth_code确保有效性，desktop_id: "
                        f"{instance_m.desktop_id}",
                    )
                    new_auth_code = (
                        await instance_m.app_stream_client.search_auth_code()
                    )
                    if new_auth_code:
                        instance_m.auth_code = new_auth_code
                        logger.info(
                            f"auth_code已更新: {instance_m.desktop_id}",
                        )
                    else:
                        logger.warning(
                            f"获取新auth_code失败，使用原有auth_code: "
                            f"{instance_m.desktop_id}",
                        )

                except Exception as e:
                    logger.error(f"验证PC设备时出错: {e}，重新初始化设备")
                    # 清理旧设备
                    chat_state.equipment = None
                    # 递归调用，重新初始化设备
                    return await get_equipment(user_id, chat_id, config)

                logger.info(
                    f"设备已存在，返回设备信息-desktop_id: {instance_m.desktop_id}",
                )
                return {
                    "task_id": task_id,
                    "equipment_web_url": chat_state.equipment_web_url,
                    "equipment_web_sdk_info": {
                        "auth_code": instance_m.auth_code,
                        "desktop_id": instance_m.desktop_id,
                        "static_url": static_url,
                    },
                }
            elif sandbox_type == "phone_wuyin":
                instance_m = chat_state.equipment.instance_manager

                # 验证手机设备状态和ticket有效性
                try:
                    # 检查设备状态
                    total_count, next_token, devices_info = (
                        await asyncio.to_thread(
                            instance_m.eds_client.list_instance,
                            instance_ids=[instance_m.instance_id],
                        )
                    )

                    if (
                        not devices_info
                        or devices_info[0].android_instance_status.lower()
                        != "running"
                    ):
                        logger.warning(
                            f"手机设备状态异常，重新初始化: {instance_m.instance_id}",
                        )
                        # 清理旧设备
                        chat_state.equipment = None
                        # 递归调用，重新初始化设备
                        return await get_equipment(user_id, chat_id, config)

                    # 对于手机设备，可能需要重新获取ticket（如果有相应的接口）
                    # 这里暂时保持原有逻辑，如果需要可以添加类似PC的ticket刷新

                except Exception as e:
                    logger.error(f"验证手机设备时出错: {e}，重新初始化设备")
                    # 清理旧设备
                    chat_state.equipment = None
                    # 递归调用，重新初始化设备
                    return await get_equipment(user_id, chat_id, config)

                logger.info(
                    f"设备已存在，返回设备信息-instance_id: {instance_m.instance_id}",
                )
                return {
                    "task_id": task_id,
                    "equipment_web_url": chat_state.equipment_web_url,
                    "equipment_web_sdk_info": {
                        "ticket": instance_m.ticket,
                        "person_app_id": instance_m.person_app_id,
                        "app_instance_id": instance_m.instance_id,
                        "static_url": static_url,
                    },
                }
        else:
            # 初始化PC设备
            if sandbox_type == "pc_wuyin":
                # 从资源分配器获取PC实例
                logger.info(
                    f"启动user_id: {user_id}, chat_id: {chat_id}",
                )
                desktop_id, status = (
                    await state_manager.pc_allocator.allocate_async(
                        f"{user_id}:{chat_id}",
                        timeout=0,
                    )
                )
                logger.info(
                    f"启动desktop_id: {desktop_id}, status: {status}",
                )
                # 处理资源排队情况
                if status == AllocationStatus.WAIT_TIMEOUT:
                    position = (
                        state_manager.pc_allocator.get_chat_wait_position(
                            f"{user_id}:{chat_id}",
                        )[0]
                    )
                    total_waiting = (
                        state_manager.pc_allocator.get_queue_info()[
                            "total_waiting"
                        ]
                    )
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "message": "All PC resources are currently in use",
                            "queue_position": position + 1,
                            "total_waiting": total_waiting,
                            "type": "queued",
                        },
                    )

                if not (
                    status == AllocationStatus.SUCCESS
                    or status == AllocationStatus.CHAT_ALREADY_ALLOCATED
                ):
                    logger.error(f"Failed to allocate PC resource: {status}")
                    raise HTTPException(
                        503,
                        "Failed " "to allocate PC resource",
                    )

                # 创建云电脑实例
                try:
                    equipment = await asyncio.to_thread(
                        CloudComputer,
                        desktop_id=desktop_id,
                    )
                    await equipment.initialize()
                except Exception as e:
                    # 初始化失败时释放已分配的资源
                    logger.error(
                        f"CloudComputer初始化失败: {e}，释放资源 {desktop_id}",
                    )
                    await state_manager.pc_allocator.release_async(desktop_id)
                    raise HTTPException(
                        503,
                        f"Failed to initialize PC resource: {str(e)}",
                    )

                logger.info(
                    f"启动equipment: {equipment}-{equipment.instance_manager}"
                    f"-{equipment.instance_manager.ecd_client}",
                )
                # 更新对话状态
                chat_state.equipment = equipment
                chat_state.task_id = task_id
                chat_state.sandbox_type = sandbox_type
                chat_state.equipment_web_url = (
                    f"{static_url}equipment_computer.html"
                )
                logger.info(
                    f"启动instance_id: {desktop_id}\n",
                )
                return {
                    "task_id": task_id,
                    "equipment_web_url": chat_state.equipment_web_url,
                    "equipment_web_sdk_info": {
                        "auth_code": equipment.instance_manager.auth_code,
                        "desktop_id": desktop_id,
                        "static_url": static_url,
                    },
                }

            # 初始化手机设备
            elif sandbox_type == "phone_wuyin":
                # 从资源分配器获取手机实例
                instance_id, status = (
                    await state_manager.phone_allocator.allocate_async(
                        f"{user_id}:{chat_id}",
                        timeout=0,
                    )
                )
                logger.info(
                    f"启动 instance_id: {instance_id}, status: {status}",
                )
                # 处理资源排队情况
                if status == AllocationStatus.WAIT_TIMEOUT:
                    position = (
                        state_manager.phone_allocator.get_chat_wait_position(
                            f"{user_id}:{chat_id}",
                        )[0]
                    )
                    total_waiting = (
                        state_manager.phone_allocator.get_queue_info()[
                            "total_waiting"
                        ]
                    )
                    logger.warning(
                        f"Failed to allocate phone resource: {status}",
                    )
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "message": "All phone resources are "
                            "currently in use",
                            "queue_position": position + 1,
                            "total_waiting": total_waiting,
                            "type": "queued",
                        },
                    )

                if not (
                    status == AllocationStatus.SUCCESS
                    or status == AllocationStatus.CHAT_ALREADY_ALLOCATED
                ):
                    logger.warning(
                        f"Failed to allocate phone resource: {status}",
                    )
                    raise HTTPException(
                        503,
                        "Failed to allocate phone resource",
                    )

                # 创建云手机设备对象 - 异步初始化
                try:
                    equipment = await asyncio.to_thread(
                        CloudPhone,
                        instance_id=instance_id,
                    )
                    await equipment.initialize()
                except Exception as e:
                    # 🚨 初始化失败时释放已分配的资源
                    logger.error(
                        f"CloudPhone初始化失败: {e}，释放资源 {instance_id}",
                    )
                    await state_manager.phone_allocator.release_async(
                        instance_id,
                    )
                    raise HTTPException(
                        503,
                        f"Failed to initialize "
                        f"phone "
                        f"resource: {str(e)}",
                    )
                # 更新对话状态
                chat_state.equipment = equipment
                chat_state.task_id = task_id
                chat_state.sandbox_type = sandbox_type
                chat_state.equipment_web_url = (
                    f"{static_url}equipment_phone.html"
                )
                logger.info(f"启动instance_id: {instance_id}")
                e_in_m = equipment.instance_manager
                return {
                    "task_id": task_id,
                    "equipment_web_url": chat_state.equipment_web_url,
                    "equipment_web_sdk_info": {
                        "ticket": e_in_m.ticket,
                        "person_app_id": e_in_m.person_app_id,
                        "app_instance_id": e_in_m.instance_id,
                        "static_url": static_url,
                    },
                }

            # 默认e2b桌面初始化
            else:
                equipment = await asyncio.to_thread(init_sandbox)
                chat_state.equipment = equipment
                chat_state.sandbox = equipment.device
                chat_state.task_id = task_id
                chat_state.sandbox_type = sandbox_type

                return {
                    "task_id": task_id,
                    "sandbox_url": (
                        equipment.device.stream.get_url()
                        if equipment.device
                        else None
                    ),
                }


# API端点
@app.post("/cua/init")
async def init_task(request: InitRequest, user_id: str = ""):
    """触发异步环境初始化"""
    if not user_id:
        if request.user_id:
            user_id = request.user_id
        else:
            user_id = request.config.user_id
    logger.info(f"start init by user_id:{user_id}")
    chat_id = request.config.chat_id
    if not user_id or not chat_id:
        raise HTTPException(
            status_code=400,
            detail="user_id and chat_id are required",
        )
    logger.info(
        f"接收到任务请求，用户: {user_id}, 对话: {chat_id} "
        f"request: {json.dumps(request.model_dump(), ensure_ascii=False)}",
    )
    try:
        # 启动异步环境初始化操作
        operation_id = await state_manager.start_environment_operation(
            user_id,
            chat_id,
            "init",
            request.config.dict(),
        )

        return {
            "success": True,
            "operation_id": operation_id,
            "message": "Environment initialization started",
            "status": "initializing",
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error starting init operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cua/run")
async def run_task_stream(request: ComputerUseRequest, user_id: str = ""):
    """
    流式任务执行接口，支持序列号机制和断线续传
    如果提供sequence_number，则返回历史数据；否则执行新任务
    """
    # 从请求中提取对话ID和配置
    if not user_id:
        if request.user_id:
            user_id = request.user_id
        else:
            user_id = request.config.user_id
    chat_id = request.config.chat_id if request.config else ""
    logger.info(f"start run by user_id:{user_id}")
    if not user_id or not chat_id:
        raise HTTPException(400, "user_id and chat_id are required in config")

    # 验证用户会话有效性（非严格模式，因为心跳可能还没建立）
    await validate_user_session(user_id, chat_id, strict_mode=False)

    sequence_number = request.sequence_number

    logger.info(
        f"接收到任务请求，用户: {user_id}, 对话: {chat_id}, "
        f"序列号: {sequence_number} , request: "
        f"{json.dumps(request.model_dump(), ensure_ascii=False)}",
    )
    # 如果提供了序列号，返回历史数据（断线续传）
    if sequence_number is not None:
        return await _handle_resume_stream(user_id, chat_id, sequence_number)

    # 否则执行新任务
    if not request.input:
        raise HTTPException(400, "No input messages provided")

    return await _handle_new_stream(user_id, chat_id, request)


async def _handle_resume_stream(
    user_id: str,
    chat_id: str,
    from_sequence: int,
):
    """处理断线续传，返回历史数据"""
    logger.info(
        f"处理断线续传，用户: {user_id}, 对话: {chat_id}, 从序列号: {from_sequence}",
    )

    async def resume_stream():
        try:
            # 获取对话状态，确定task_id
            chat_state = await state_manager.get_chat_state(user_id, chat_id)
            current_task_id = chat_state.get("task_id")

            # 从Redis获取历史数据
            historical_data = (
                await state_manager.get_stream_data_from_sequence(
                    user_id,
                    chat_id,
                    from_sequence,
                    current_task_id,
                )
            )

            logger.info(f"找到 {len(historical_data)} 条历史数据")
            # 发送历史数据
            for data_item in historical_data:
                json_str = json.dumps(data_item, ensure_ascii=False)
                yield f"data: {json_str}\n\n"

            # 如果对话当前有正在运行的任务，继续流式输出新数据
            if chat_state.get("is_running") and chat_state.get("agent"):
                logger.info("检测到正在运行任务，继续流式输出新数据")
                # 监听新数据（这里需要实现一个机制来获取实时数据）
                # 暂时先获取最新的序列号，等待新数据
                latest_sequence = (
                    await state_manager.get_latest_sequence_number(
                        user_id,
                        chat_id,
                        current_task_id,
                    )
                )

                # 如果最新序列号大于请求的序列号，说明有新数据
                if latest_sequence > from_sequence:
                    new_data = (
                        await state_manager.get_stream_data_from_sequence(
                            user_id,
                            chat_id,
                            max(
                                from_sequence,
                                latest_sequence - 10,
                            ),  # 获取最近的数据
                            current_task_id,
                        )
                    )

                    for data_item in new_data:
                        if data_item.get("sequence_number", 0) > from_sequence:
                            json_str = json.dumps(
                                data_item,
                                ensure_ascii=False,
                            )
                            yield f"data: {json_str}\n\n"

        except Exception as e:
            logger.error(f"处理断线续传时出错: {e}")
            # 对于断线续传错误，我们仍然手动创建（不存储到Redis，因为这不是agent数据）
            error_data = {
                "sequence_number": from_sequence,
                "object": "error",
                "status": "error",
                "error": f"Resume failed: {str(e)}",
                "type": "error",
                "data": {"error": str(e)},
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        resume_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
        },
    )


async def _handle_new_stream(
    user_id: str,
    chat_id: str,
    request: ComputerUseRequest,
):
    """处理新的流式任务"""
    logger.info(f"开始新任务，用户: {user_id}, 对话: {chat_id}")

    async def agent_stream():
        """Agent流式响应生成器 - 支持序列号存储"""
        task_id = None
        try:

            # 创建AgentScope Context模拟对象
            class MockContext:
                def __init__(self, request):
                    self.request = request

            context = MockContext(request)

            # 清空旧的流式数据
            await state_manager.clear_stream_data(user_id, chat_id)

            # 设置任务状态
            await state_manager.update_chat_state(
                user_id,
                chat_id,
                {
                    "is_running": True,
                    "current_task": f"Agent API Task from input:"
                    f" {len(request.input)} messages",
                },
            )

            # 重新获取更新后的state
            chat_state = await state_manager.get_chat_state(user_id, chat_id)
            task_id = chat_state.get("task_id")

            # 创建Agent配置
            agent_config = {
                "equipment": chat_state.get("equipment"),
                "output_dir": ".",
                "sandbox_type": chat_state.get("sandbox_type"),
                "status_callback": None,
                "mode": (
                    "phone_use"
                    if chat_state.get("sandbox_type") == "phone_wuyin"
                    else "pc_use"
                ),
                "pc_use_add_info": request.config.pc_use_addon_info,
                "max_steps": request.config.max_steps,
                "chat_id": chat_id,
                "user_id": user_id,
                "e2e_info": request.config.e2e_info,
                "extra_params": request.config.extra_params,
                "state_manager": state_manager,
            }

            # 创建Agent实例
            agent = ComputerUseAgent(
                name="ComputerUseAgent",
                agent_config=agent_config,
            )

            # 将agent引用存储在应用状态中，支持多实例部署
            app.state.running_agents[f"{user_id}:{chat_id}"] = agent

            # 将agent标识存储到Redis（仅用于状态检查，不是真实对象）
            await state_manager.update_chat_state(
                user_id,
                chat_id,
                {
                    "agent_running": True,
                    "agent_id": id(agent),  # 存储agent的标识符
                },
            )

            logger.info(f"开始Agent执行，用户: {user_id}, 对话: {chat_id}")
            # 执行Agent任务并处理流式输出
            async_iterator = None
            try:
                async_iterator = agent.run_async(context)
                async for result in async_iterator:
                    try:
                        # 将Agent的输出转换为JSON格式
                        if hasattr(result, "model_dump"):
                            result_dict = result.model_dump()
                        else:
                            result_dict = _serialize(result)

                        # 直接使用Agent返回的原始数据，只添加序列号
                        sequence_number = (
                            await state_manager.store_stream_data(
                                user_id,
                                chat_id,
                                result_dict,
                                task_id,
                            )
                        )
                        result_dict["sequence_number"] = sequence_number

                        json_str = json.dumps(result_dict, ensure_ascii=False)
                        yield f"data: {json_str}\n\n"

                    except Exception as serialize_error:
                        logger.error(f"处理输出时出错: {serialize_error}")
                        # 存储错误信息
                        error_data = {
                            "error": f"序列化输出时出错: {str(serialize_error)}",
                            "type": "serialization_error",
                        }

                        sequence_number = (
                            await state_manager.store_stream_data(
                                user_id,
                                chat_id,
                                error_data,
                                task_id,
                            )
                        )

                        # 获取Redis中已标准化的错误数据
                        stored_error_list = (
                            await state_manager.get_stream_data_from_sequence(
                                user_id,
                                chat_id,
                                sequence_number,
                                task_id,
                            )
                        )

                        if stored_error_list:
                            _d = json.dumps(
                                stored_error_list[0],
                                ensure_ascii=False,
                            )
                            yield f"data: {_d}\n\n"
                        else:
                            # 降级方案
                            error_output = {
                                "sequence_number": sequence_number,
                                "object": "error",
                                "status": "error",
                                "error": str(serialize_error),
                                "type": "error",
                                "data": error_data,
                            }
                            _data = json.dumps(
                                error_output,
                                ensure_ascii=False,
                            )
                            yield f"data: {_data}\n\n"
                        continue

            except Exception as iteration_error:
                logger.error(f"Agent执行时出错: {iteration_error}")
                # 存储执行错误
                error_data = {
                    "error": f"Agent执行时出错: {str(iteration_error)}",
                    "type": "iteration_error",
                }

                sequence_number = await state_manager.store_stream_data(
                    user_id,
                    chat_id,
                    error_data,
                    task_id,
                )

                # 获取Redis中已标准化的错误数据
                stored_error_list = (
                    await state_manager.get_stream_data_from_sequence(
                        user_id,
                        chat_id,
                        sequence_number,
                        task_id,
                    )
                )

                if stored_error_list:
                    _d = json.dumps(stored_error_list[0], ensure_ascii=False)
                    yield f"data: {_d}\n\n"
                else:
                    # 降级方案
                    error_output = {
                        "sequence_number": sequence_number,
                        "object": "error",
                        "status": "error",
                        "error": str(iteration_error),
                        "type": "error",
                        "data": error_data,
                    }
                    _d = json.dumps(error_output, ensure_ascii=False)
                    yield f"data: {_d}\n\n"

            finally:
                # 清理资源
                if async_iterator and hasattr(async_iterator, "aclose"):
                    try:
                        await async_iterator.aclose()
                    except Exception as close_error:
                        print(f"关闭异步迭代器时出错: {close_error}")

            print(f"Agent执行完成，用户: {user_id}, 对话: {chat_id}")

        except Exception as e:
            logger.error(
                f"Agent stream execution failed for user {user_id}, "
                f"chat {chat_id}: {e}",
            )
            # 存储全局错误
            error_data = {
                "error": f"任务执行失败: {str(e)}",
                "type": "agent_error",
            }

            try:
                sequence_number = await state_manager.store_stream_data(
                    user_id,
                    chat_id,
                    error_data,
                    task_id,
                )

                # 获取Redis中已标准化的错误数据
                stored_error_list = (
                    await state_manager.get_stream_data_from_sequence(
                        user_id,
                        chat_id,
                        sequence_number,
                        task_id,
                    )
                )

                if stored_error_list:
                    _d = json.dumps(stored_error_list[0], ensure_ascii=False)
                    yield f"data: {_d}\n\n"
                else:
                    # 降级方案
                    error_output = {
                        "sequence_number": sequence_number,
                        "object": "error",
                        "status": "error",
                        "error": str(e),
                        "type": "error",
                        "data": error_data,
                    }
                    _d = json.dumps(error_output, ensure_ascii=False)
                    yield f"data: {_d}\n\n"
            except Exception as storage_error:
                print(f"存储错误信息失败: {storage_error}")
                # 最后的错误输出，不存储到Redis
                final_error = {
                    "sequence_number": None,
                    "object": "error",
                    "status": "error",
                    "error": str(e),
                    "type": "error",
                    "data": {"error": str(e)},
                }
                _d = json.dumps(final_error, ensure_ascii=False)
                yield f"data: {_d}\n\n"

        finally:
            # 清理状态
            try:
                # 清理agent引用
                composite_key = f"{user_id}:{chat_id}"
                if composite_key in app.state.running_agents:
                    del app.state.running_agents[composite_key]

                await state_manager.update_chat_state(
                    user_id,
                    chat_id,
                    {
                        "is_running": False,
                        "current_task": None,
                        "agent_running": False,
                        "agent_id": None,
                    },
                )
            except Exception as cleanup_error:
                print(f"清理状态时出错: {cleanup_error}")

    return StreamingResponse(
        agent_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
        },
    )


@app.post("/cua/switch_environment")
async def switch_environment(request: InitRequest):
    """触发异步环境切换"""
    if not request.user_id:
        user_id = request.config.user_id
    else:
        user_id = request.user_id
    chat_id = request.config.chat_id
    if not user_id or not chat_id:
        raise HTTPException(
            status_code=400,
            detail="user_id and chat_id " "are required",
        )
    logger.info(
        f"start switch_environment by user_id:{user_id} , "
        f"chat_id: {chat_id}, request:{request}",
    )
    # 验证会话有效性 - 只有活跃会话才能切换环境
    await validate_user_session(user_id, chat_id, strict_mode=True)

    try:
        # 启动异步环境切换操作
        operation_id = await state_manager.start_environment_operation(
            user_id,
            chat_id,
            "switch",
            request.config.dict(),
        )

        return {
            "success": True,
            "operation_id": operation_id,
            "message": "Environment switch started",
            "status": "switching",
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error starting switch operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cua/operation_status")
async def get_operation_status(
    user_id: str,
    chat_id: str,
    operation_id: str = None,
):
    """查询环境操作状态（用于轮询）"""
    if not user_id or not chat_id:
        logger.error("user_id and chat_id are required")
        raise HTTPException(
            status_code=400,
            detail="user_id and chat_id are required",
        )

    try:
        status_info = await state_manager.get_environment_operation(
            user_id,
            chat_id,
            operation_id,
        )
        if status_info is None:
            logger.info(
                f"Operation not found for user_id: {user_id}, "
                f"chat_id: {chat_id}"
                f", operation_id: {operation_id}",
            )
            return {
                "success": False,
                "error": "Operation not found",
                "user_id": user_id,
                "chat_id": chat_id,
                "operation_id": operation_id,
            }
        return {
            "success": True,
            **status_info,
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting operation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cua/stop")
async def stop_task(user_id: str, chat_id: str):
    logger.info(f"stop task by user_id:{user_id} , chat_id: {chat_id}")
    # 验证用户会话有效性（非严格模式，允许停止非活跃会话）
    await validate_user_session(user_id, chat_id, strict_mode=False)

    await state_manager.stop_task(user_id, chat_id)
    logger.info("task stopped")
    return {"success": True}


@app.post("/cua/release")
async def release_resource(request: UserChatRequest):
    user_id = request.user_id
    chat_id = request.chat_id
    logger.info(f"release resource by user_id:{user_id} , chat_id: {chat_id}")
    # 验证用户会话有效性（非严格模式，允许释放非活跃会话资源）
    await validate_user_session(user_id, chat_id, strict_mode=False)

    await state_manager.release_resources(user_id, chat_id)
    logger.info("release success")
    return {"success": True}


@app.get("/cua/heartbeat")
async def heartbeat(user_id: str, chat_id: str):
    try:
        # 验证chat_id是否为该user_id的活跃会话
        is_valid = await state_manager.validate_user_active_chat(
            user_id,
            chat_id,
        )
        current_active_chat = await state_manager.get_user_active_chat(user_id)

        if not is_valid:
            logger.warning(
                f"Invalid chat session for user {user_id}, chat {chat_id}"
                f", active: {current_active_chat}",
            )
            # 为失效的会话返回明确的状态信息
            return {
                "success": False,
                "is_active_chat": False,
                "status": "chat_inactive",
                "message": "Current chat is no longer active. "
                "Another session may be active for this user.",
                "active_chat_id": current_active_chat,
                "error_code": "CHAT_INACTIVE",
            }

        # 只为有效会话更新心跳记录
        await state_manager.set_heartbeat(user_id, chat_id)

        # 同时更新heartbeats记录
        composite_key = f"{user_id}:{chat_id}"
        state_manager.heartbeats[composite_key] = time.time()

        return {"success": True, "is_active_chat": True, "status": "active"}

    except Exception as e:
        logger.error(f"Heartbeat error for {user_id}:{chat_id}: {e}")
        # 充底逻辑：即使Redis失败也要确保心跳更新
        composite_key = f"{user_id}:{chat_id}"
        state_manager.heartbeats[composite_key] = time.time()
        return {
            "success": False,
            "is_active_session": False,
            "status": "error",
            "error": str(e),
        }


@app.get("/cua/queue_status")
async def get_queue_status(user_id: str, chat_id: str, sandbox_type: str):
    try:
        if sandbox_type == "pc_wuyin":
            # 使用PC分配器并调用异步方法
            position, status = (
                await state_manager.pc_allocator.get_chat_wait_position_async(
                    user_id,
                )
            )
            if (
                status == AllocationStatus.SUCCESS
                or status == AllocationStatus.CHAT_ALREADY_ALLOCATED
            ):
                queue_info = (
                    await state_manager.pc_allocator.get_queue_info_async()
                )
                return {
                    "position": position,
                    "total_waiting": queue_info["total_waiting"],
                    "queue_status": "queued",
                }
        elif sandbox_type == "phone_wuyin":
            # 使用手机分配器并调用异步方法
            position, status = (
                await state_manager.phone_allocator.get_chat_wait_position_async(  # noqa E501
                    user_id=user_id,
                )
            )
            if (
                status == AllocationStatus.SUCCESS
                or status == AllocationStatus.CHAT_ALREADY_ALLOCATED
            ):
                queue_info = (
                    await state_manager.phone_allocator.get_queue_info_async()
                )
                return {
                    "position": position,
                    "total_waiting": queue_info["total_waiting"],
                    "queue_status": "queued",
                }

        # 检查对话是否已分配资源
        equipment_info = await state_manager.get_equipment_info(
            user_id,
            chat_id,
        )
        if equipment_info is not None:
            return {
                "position": -1,
                "queue_status": "allocated",
            }

        # 对话不在队列且无已分配资源 - 可能是因为没有可用资源被移除或其他原因
        return {
            "position": -1,
            "queue_status": "not_queued",
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return {
            "position": -1,
            "queue_status": "error",
            "error": str(e),
        }


# 添加代理端点来验证 studio token
@app.get("/cua/proxy/validate-studio-token")
async def proxy_validate_studio_token(studio_token: str = Query(...)):
    """
    代理验证 studio token 的端点，避免前端 CORS 问题
    """
    try:
        # 使用异步方式发送请求到 ModelScope API
        def make_request():
            return requests.get(
                f"https://modelscope.cn/api/v1/"
                f"studios/check-token?studio_token={studio_token}",
                timeout=300,
            )

        response = await asyncio.to_thread(make_request)

        # 返回相同的响应结构
        return JSONResponse(
            content=response.json(),
            status_code=response.status_code,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cua/interrupt_wait")
async def interrupt_wait(user_id: str, chat_id: str):
    # 验证用户会话有效性（非严格模式）
    await validate_user_session(user_id, chat_id, strict_mode=False)

    chat_state = await state_manager.get_chat_state(user_id, chat_id)

    # 检查对话是否有正在运行的任务
    if isinstance(chat_state, dict):
        is_running = chat_state.get("is_running", False)
        agent_running = chat_state.get("agent_running", False)
    else:
        is_running = getattr(chat_state, "is_running", False)
        agent_running = getattr(chat_state, "agent_running", False)

    # 没有正在运行的任务
    if not is_running or not agent_running:
        raise HTTPException(status_code=400, detail="No running task")

    # 从应用状态中获取agent实例
    composite_key = f"{user_id}:{chat_id}"
    agent = app.state.running_agents.get(composite_key)
    if agent is None:
        raise HTTPException(status_code=400, detail="Agent instance not found")

    # 调用agent的中断方法
    agent.interrupt_wait()

    # 向前端发送状态更新
    await state_manager.update_status(
        user_id,
        chat_id,
        {
            "status": "running",
            "type": "SYSTEM",
            "message": "Stop-wait request received",
        },
    )
    return {"success": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend:app", host="0.0.0.0", port=8002, reload=True)
