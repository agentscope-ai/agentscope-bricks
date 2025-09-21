# -*- coding: utf-8 -*-
"""
Redis-based State Manager for Computer Use Agent
支持多实例部署和数据共享
"""
import json
import time
import asyncio
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
import pickle
import uuid
from datetime import datetime
from enum import Enum
from redis_resource_allocator import (
    AsyncRedisResourceAllocator,
    AllocationStatus,
)
from cua_utils import init_sandbox
import os
from demos.computer_use.sandbox_center.sandboxes.cloud_phone_wy import (
    CloudPhone,
)
from demos.computer_use.sandbox_center.sandboxes.cloud_computer_wy import (
    CloudComputer,
)
from fastapi import HTTPException
from agentscope_bricks.utils.logger_util import logger
from demos.computer_use.sandbox_center.sandboxes.cloud_computer_wy import (
    AppStreamClient,
)


class EnvironmentOperationStatus(Enum):
    """环境操作状态"""

    IDLE = "idle"
    INITIALIZING = "initializing"
    SWITCHING = "switching"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED = "queued"
    WAITING_RETRY = "waiting_retry"


class RedisStateManager:
    """基于Redis的状态管理器，支持多实例部署"""

    def __init__(
        self,
        redis_url: str = None,
        phone_instance_ids: List[str] = None,
        desktop_ids: List[str] = None,
    ):
        if redis_url is None:
            # 构建Redis URL
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_db = os.environ.get("REDIS_DB", "0")
            redis_password = os.environ.get("REDIS_PASSWORD", "")
            redis_username = os.environ.get("REDIS_USERNAME", "")

            # 构建连接URL
            if redis_password:
                if redis_username:
                    self.redis_url = (
                        f"redis://{redis_username}:"
                        f"{redis_password}@{redis_host}"
                        f":{redis_port}/{redis_db}"
                    )
                else:
                    self.redis_url = (
                        f"redis://:{redis_password}@"
                        f"{redis_host}:{redis_port}"
                        f"/{redis_db}"
                    )
            else:
                self.redis_url = (
                    f"redis://{redis_host}:{redis_port}/{redis_db}"
                )
        else:
            self.redis_url = redis_url

        self.redis_client = None

        # 存储资源ID用于后续初始化
        self.phone_instance_ids = phone_instance_ids or []
        self.desktop_ids = desktop_ids or []

        # 资源分配器将在初始化时创建
        self.phone_allocator = None
        self.pc_allocator = None

        # Redis key前缀
        self.CHAT_STATE_PREFIX = "computer_use:chat_state:"
        self.STATUS_QUEUE_PREFIX = "computer_use:status_queue:"
        self.HEARTBEAT_PREFIX = "computer_use:heartbeat:"
        self.EQUIPMENT_PREFIX = "computer_use:equipment:"
        self.ENV_OPERATION_PREFIX = "computer_use:env_op:"
        self.STREAM_DATA_PREFIX = "computer_use:stream:"  # 流式数据前缀
        self.STREAM_COUNTER_PREFIX = (
            "computer_use:stream_counter:"  # 序列号计数器
        )
        self.USER_ACTIVE_CHAT_PREFIX = (
            "computer_use:user_active_chat:"  # 用户活跃chat_id映射
        )

        # 过期时间配置
        self.CHAT_STATE_TTL = 3600  # 对话状态1小时过期
        self.HEARTBEAT_TTL = 30  # 心跳30秒过期
        self.STATUS_QUEUE_TTL = 300  # 状态队列5分钟过期
        self.EQUIPMENT_TTL = 3600  # 设备信息1小时过期
        self.STREAM_DATA_TTL = 1800  # 流式数据30分钟过期
        self.USER_ACTIVE_CHAT_TTL = 7200  # 用户活跃chat_id映射2小时过期

        # 内存存储（兼容原有接口）
        self.status_queues: Dict[str, asyncio.Queue] = {}
        self.heartbeats: Dict[str, float] = {}

    async def initialize(self):
        """初始化Redis连接和资源分配器"""

        self.redis_client = redis.from_url(self.redis_url)
        await self.redis_client.ping()
        logger.info(
            f"Redis连接成功: "
            f"{self.redis_url.rpartition('@')[-1] or self.redis_url}",
        )

        # 显示资源配置信息
        logger.info(f"Phone instance IDs: {self.phone_instance_ids}")
        logger.info(f"Desktop IDs: {self.desktop_ids}")

        # 初始化Redis资源分配器
        if self.phone_instance_ids:
            self.phone_allocator = AsyncRedisResourceAllocator(
                "phone",
                self.phone_instance_ids,
                self.redis_client,
            )
            await self.phone_allocator.initialize()
            logger.info(
                f"Phone resource allocator initialized with "
                f"{len(self.phone_instance_ids)} instances",
            )

        if self.desktop_ids:
            self.pc_allocator = AsyncRedisResourceAllocator(
                "pc",
                self.desktop_ids,
                self.redis_client,
            )
            await self.pc_allocator.initialize()
            logger.info(
                f"PC resource allocator initialized with "
                f"{len(self.desktop_ids)} instances",
            )

    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()

    def _composite_key(self, user_id: str, chat_id: str) -> str:
        """生成复合键"""
        return f"{user_id}:{chat_id}"

    def _chat_state_key(self, user_id: str, chat_id: str) -> str:
        composite = self._composite_key(user_id, chat_id)
        return f"{self.CHAT_STATE_PREFIX}{composite}"

    def _status_queue_key(self, user_id: str, chat_id: str) -> str:
        composite = self._composite_key(user_id, chat_id)
        return f"{self.STATUS_QUEUE_PREFIX}{composite}"

    def _heartbeat_key(self, user_id: str, chat_id: str) -> str:
        composite = self._composite_key(user_id, chat_id)
        return f"{self.HEARTBEAT_PREFIX}{composite}"

    def _equipment_key(self, user_id: str, chat_id: str) -> str:
        composite = self._composite_key(user_id, chat_id)
        return f"{self.EQUIPMENT_PREFIX}{composite}"

    def _env_operation_key(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str = None,
    ) -> str:
        composite = self._composite_key(user_id, chat_id)
        if operation_id:
            return f"{self.ENV_OPERATION_PREFIX}{composite}:{operation_id}"
        return f"{self.ENV_OPERATION_PREFIX}{composite}:current"

    def _stream_data_key(
        self,
        user_id: str,
        chat_id: str,
        task_id: str = None,
    ) -> str:
        """生成流式数据存储key"""
        composite = self._composite_key(user_id, chat_id)
        if task_id:
            return f"{self.STREAM_DATA_PREFIX}{composite}:{task_id}"
        return f"{self.STREAM_DATA_PREFIX}{composite}:current"

    def _stream_counter_key(
        self,
        user_id: str,
        chat_id: str,
        task_id: str = None,
    ) -> str:
        """生成序列号计数器key"""
        composite = self._composite_key(user_id, chat_id)
        if task_id:
            return f"{self.STREAM_COUNTER_PREFIX}{composite}:{task_id}"
        return f"{self.STREAM_COUNTER_PREFIX}{composite}:current"

    def _user_active_chat_key(self, user_id: str) -> str:
        """生成用户活跃chat_id存储key"""
        return f"{self.USER_ACTIVE_CHAT_PREFIX}{user_id}"

    async def set_user_active_chat(self, user_id: str, chat_id: str):
        """设置用户的活跃chat_id"""
        key = self._user_active_chat_key(user_id)
        await self.redis_client.setex(key, self.USER_ACTIVE_CHAT_TTL, chat_id)

    async def get_user_active_chat(self, user_id: str) -> Optional[str]:
        """获取用户的活跃chat_id"""
        key = self._user_active_chat_key(user_id)
        chat_id = await self.redis_client.get(key)
        if chat_id:
            if isinstance(chat_id, bytes):
                chat_id = chat_id.decode("utf-8")
            return chat_id
        return None

    async def cleanup_user_old_sessions(self, user_id: str, new_chat_id: str):
        """清理用户的旧会话资源，只保留新的chat_id"""
        try:
            # 获取用户当前的活跃chat_id
            old_chat_id = await self.get_user_active_chat(user_id)

            if old_chat_id and old_chat_id != new_chat_id:
                logger.info(
                    f"清理用户 {user_id} 的旧会话 {old_chat_id}，激活新会话 {new_chat_id}",
                )

                # 停止旧会话的任务
                old_chat_state = await self.get_chat_state(
                    user_id,
                    old_chat_id,
                )
                if old_chat_state.get("is_running"):
                    await self.stop_task(user_id, old_chat_id)
                    await asyncio.sleep(0.5)  # 给任务一点时间停止

                # 用户级别资源释放：释放用户的所有资源
                await self.release_user_resources(user_id)

                # 清理旧会话的数据
                await self.cleanup_chat_data(user_id, old_chat_id)

                logger.info(f"用户 {user_id} 旧会话 {old_chat_id} 清理完成")
                logger.info(f"用户 {user_id} 旧会话 {old_chat_id} 清理完成")
            # 设置新的活跃chat_id
            await self.set_user_active_chat(user_id, new_chat_id)

        except Exception as e:
            logger.error(f"清理用户 {user_id} 旧会话时出错: {e}")

    async def validate_user_active_chat(
        self,
        user_id: str,
        chat_id: str,
    ) -> bool:
        """验证chat_id是否为该user_id的活跃会话"""
        active_chat_id = await self.get_user_active_chat(user_id)
        return active_chat_id == chat_id

    async def get_chat_state(
        self,
        user_id: str,
        chat_id: str,
    ) -> Dict[str, Any]:
        """获取对话状态"""
        key = self._chat_state_key(user_id, chat_id)
        state_data = await self.redis_client.get(key)

        if not state_data:
            # 创建默认对话状态
            default_state = {
                "user_id": user_id,
                "chat_id": chat_id,
                "current_task": None,
                "is_running": False,
                "equipment": None,
                "sandbox": None,
                "agent": None,
                "task_id": None,
                "sandbox_type": None,
                "equipment_web_url": None,
                "background_task": None,
                "current_env_operation": None,
                "env_operation_history": [],
                "last_status": {
                    "status": "idle",
                    "message": "Ready to start",
                    "type": "SYSTEM",
                    "timestamp": time.time(),
                    "uuid": str(uuid.uuid4()),
                    "task_id": None,
                },
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            await self.set_chat_state(user_id, chat_id, default_state)
            return default_state

        # 反序列化（处理bytes）
        if isinstance(state_data, bytes):
            state_data = state_data.decode("utf-8")
        return json.loads(state_data)

    async def set_chat_state(
        self,
        user_id: str,
        chat_id: str,
        state: Dict[str, Any],
    ):
        """设置对话状态"""
        state["updated_at"] = time.time()
        key = self._chat_state_key(user_id, chat_id)
        state_json = json.dumps(state, default=str)
        await self.redis_client.setex(key, self.CHAT_STATE_TTL, state_json)

    async def update_chat_state(
        self,
        user_id: str,
        chat_id: str,
        updates: Dict[str, Any],
    ):
        """更新对话状态"""
        current_state = await self.get_chat_state(user_id, chat_id)
        current_state.update(updates)
        await self.set_chat_state(user_id, chat_id, current_state)

    async def store_equipment(
        self,
        user_id: str,
        chat_id: str,
        equipment: object,
    ):
        """存储设备关键信息（不序列化对象本身，避免线程锁问题）"""
        try:
            # 提取设备基本信息用于查询和显示
            equipment_info = {
                "user_id": user_id,
                "chat_id": chat_id,
                "equipment_type": "unknown",
                "instance_manager_info": {},
                "stored_at": time.time(),
            }

            # 提取设备信息
            if (
                hasattr(equipment, "instance_manager")
                and equipment.instance_manager
            ):
                manager = equipment.instance_manager

                # 判断设备类型
                if hasattr(manager, "instance_id"):
                    # 手机设备
                    equipment_info.update(
                        {
                            "equipment_type": "phone_wuyin",
                            "instance_manager_info": {
                                "instance_id": getattr(
                                    manager,
                                    "instance_id",
                                    None,
                                ),
                                "ticket": getattr(manager, "ticket", None),
                                "person_app_id": getattr(
                                    manager,
                                    "person_app_id",
                                    None,
                                ),
                                "app_instance_id": getattr(
                                    manager,
                                    "app_instance_id",
                                    None,
                                ),
                            },
                        },
                    )
                elif hasattr(manager, "desktop_id"):
                    # PC设备
                    equipment_info.update(
                        {
                            "equipment_type": "pc_wuyin",
                            "instance_manager_info": {
                                "desktop_id": getattr(
                                    manager,
                                    "desktop_id",
                                    None,
                                ),
                                "auth_code": getattr(
                                    manager,
                                    "auth_code",
                                    None,
                                ),
                            },
                        },
                    )

            # 只存储设备信息，不序列化对象本身（避免线程锁序列化问题）
            info_key = f"{self._equipment_key(user_id, chat_id)}_info"
            await self.redis_client.setex(
                info_key,
                self.EQUIPMENT_TTL,
                json.dumps(equipment_info, default=str),
            )

            # 同时更新对话状态中的设备引用
            await self.update_chat_state(
                user_id,
                chat_id,
                {
                    "equipment_storage_status": "stored_in_redis",
                    "equipment_info": equipment_info,
                },
            )

            logger.info(
                f"设备信息已存储到Redis，用户: {user_id}, 对话: {chat_id}, "
                f"类型: {equipment_info['equipment_type']}",
            )

        except Exception as e:
            logger.error(f"存储设备到Redis失败: {e}")

    async def get_equipment(
        self,
        user_id: str,
        chat_id: str,
    ) -> Optional[object]:
        """获取完整的设备对象（反序列化）"""
        key = self._equipment_key(user_id, chat_id)
        equipment_data = await self.redis_client.get(key)

        if not equipment_data:
            return None

        try:
            # 使用pickle反序列化设备对象
            equipment = pickle.loads(equipment_data)
            return equipment
        except Exception as e:
            logger.error(f"反序列化设备失败: {e}")
            return None

    async def get_equipment_info(
        self,
        user_id: str,
        chat_id: str,
    ) -> Optional[Dict[str, Any]]:
        """获取设备信息（基本信息和统计）"""
        info_key = f"{self._equipment_key(user_id, chat_id)}_info"
        equipment_data = await self.redis_client.get(info_key)

        if not equipment_data:
            return None

        if isinstance(equipment_data, bytes):
            equipment_data = equipment_data.decode("utf-8")
        return json.loads(equipment_data)

    async def delete_equipment(self, user_id: str, chat_id: str):
        """删除设备信息和对象"""
        equipment_key = self._equipment_key(user_id, chat_id)
        info_key = f"{self._equipment_key(user_id, chat_id)}_info"

        # 使用管道操作删除两个key
        pipe = self.redis_client.pipeline()
        pipe.delete(equipment_key)
        pipe.delete(info_key)
        await pipe.execute()

        # 同时清理对话状态中的设备引用
        await self.update_chat_state(
            user_id,
            chat_id,
            {
                "equipment": None,
                "equipment_storage_status": None,  # 清理设备存储状态
                "equipment_info": None,
            },
        )

    async def push_status_message(
        self,
        user_id: str,
        chat_id: str,
        message: Dict[str, Any],
    ):
        """推送状态消息到队列"""
        key = self._status_queue_key(user_id, chat_id)
        message_data = json.dumps(
            {
                **message,
                "timestamp": time.time(),
                "uuid": str(uuid.uuid4()),
                "chat_id": chat_id,  # 确保消息包含对话ID
                "user_id": user_id,  # 确保消息包含用户ID
            },
            default=str,
        )

        # 使用Redis LIST作为队列
        await self.redis_client.lpush(key, message_data)
        await self.redis_client.expire(key, self.STATUS_QUEUE_TTL)

        # 限制队列长度，避免内存占用过多
        await self.redis_client.ltrim(key, 0, 99)

    async def pop_status_message(
        self,
        user_id: str,
        chat_id: str,
        timeout: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """从状态队列弹出消息（阻塞等待）"""
        key = self._status_queue_key(user_id, chat_id)
        try:
            result = await self.redis_client.brpop([key], timeout=timeout)
            if result:
                _, message_data = result
                if isinstance(message_data, bytes):
                    message_data = message_data.decode("utf-8")
                return json.loads(message_data)
        except Exception as e:
            logger.error(f"弹出状态消息失败: {e}")
        return None

    async def clear_status_queue(self, user_id: str, chat_id: str):
        """清空对话状态队列"""
        key = self._status_queue_key(user_id, chat_id)
        await self.redis_client.delete(key)

    # === 流式数据存储方法 ===

    async def store_stream_data(
        self,
        user_id: str,
        chat_id: str,
        data: Dict[str, Any],
        task_id: str = None,
    ) -> int:
        """
        存储流式数据并返回序列号

        Args:
            user_id: 用户ID
            chat_id: 对话ID
            data: 要存储的数据（Agent原始数据）
            task_id: 任务ID（可选）

        Returns:
            int: 数据的序列号
        """
        # 获取并递增序列号
        counter_key = self._stream_counter_key(user_id, chat_id, task_id)
        sequence_number = await self.redis_client.incr(counter_key)
        await self.redis_client.expire(counter_key, self.STREAM_DATA_TTL)

        # 简化存储：直接存储Agent原始数据+基本元信息，用于断线续传
        storage_data = {
            "sequence_number": sequence_number,
            "raw_data": data,  # Agent原始数据
            "timestamp": time.time(),
            "user_id": user_id,
            "chat_id": chat_id,
            "task_id": task_id,
        }

        # 存储到Redis有序集合，使用序列号作为分数
        stream_key = self._stream_data_key(user_id, chat_id, task_id)
        data_json = json.dumps(storage_data, ensure_ascii=False, default=str)

        await self.redis_client.zadd(
            stream_key,
            {data_json: sequence_number},
        )
        await self.redis_client.expire(stream_key, self.STREAM_DATA_TTL)

        # 限制有序集合大小，保留最新的1000条记录
        await self.redis_client.zremrangebyrank(stream_key, 0, -1001)

        return sequence_number

    def _is_already_standardized(self, data: Dict[str, Any]) -> bool:
        """
        检查数据是否已经包含标准化字段

        Args:
            data: 要检查的数据

        Returns:
            bool: 如果数据已标准化返回True，否则返回False
        """
        # 检查是否包含标准化字段的关键指示器
        standardized_fields = ["object", "index", "delta", "msg_id"]
        has_standardized_fields = (
            sum(1 for field in standardized_fields if field in data) >= 2
        )

        # 如果包含多个标准化字段，认为已经被标准化过了
        return has_standardized_fields

    async def get_stream_data_from_sequence(
        self,
        user_id: str,
        chat_id: str,
        from_sequence: int = 1,
        task_id: str = None,
    ) -> List[Dict[str, Any]]:
        """
        从指定序列号开始获取流式数据，重新构建标准化格式

        Args:
            chat_id: 对话ID
            from_sequence: 起始序列号
            task_id: 任务ID（可选）

        Returns:
            List[Dict[str, Any]]: 标准化格式的数据列表，按序列号排序
        """
        stream_key = self._stream_data_key(user_id, chat_id, task_id)

        # 从Redis有序集合中获取指定范围的数据
        data_list = await self.redis_client.zrangebyscore(
            stream_key,
            from_sequence,
            "+inf",
            withscores=False,
        )

        result = []
        for data_json in data_list:
            try:
                if isinstance(data_json, bytes):
                    data_json = data_json.decode("utf-8")
                stored_data = json.loads(data_json)

                # 从存储数据重新构建标准化格式
                raw_data = stored_data.get("raw_data", {})
                sequence_number = stored_data.get("sequence_number", 0)
                timestamp = stored_data.get("timestamp", time.time())

                # 重新构建标准化格式，确保与实时输出一致
                standardized_output = {
                    "sequence_number": sequence_number,
                    "object": "content",
                    "status": raw_data.get("status"),
                    "error": raw_data.get("error"),
                    "type": "data",
                    "index": None,
                    "delta": False,
                    "msg_id": None,
                    "data": raw_data,  # Agent的原始数据
                    "timestamp": timestamp,
                    "chat_id": stored_data.get("chat_id"),
                    "task_id": stored_data.get("task_id"),
                }

                result.append(standardized_output)

            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Failed to parse stream data: {e}")
                continue

        # 按序列号排序
        result.sort(key=lambda x: x.get("sequence_number", 0))
        return result

    async def get_latest_sequence_number(
        self,
        user_id: str,
        chat_id: str,
        task_id: str = None,
    ) -> int:
        """
        获取当前最新的序列号

        Args:
            chat_id: 对话ID
            task_id: 任务ID（可选）

        Returns:
            int: 最新序列号，如果没有数据则返回0
        """
        counter_key = self._stream_counter_key(user_id, chat_id, task_id)
        sequence = await self.redis_client.get(counter_key)

        if sequence:
            if isinstance(sequence, bytes):
                sequence = sequence.decode("utf-8")
            return int(sequence)
        return 0

    async def clear_stream_data(
        self,
        user_id: str,
        chat_id: str,
        task_id: str = None,
    ):
        """
        清空对话的流式数据

        Args:
            chat_id: 对话ID
            task_id: 任务ID（可选）
        """
        stream_key = self._stream_data_key(user_id, chat_id, task_id)
        counter_key = self._stream_counter_key(user_id, chat_id, task_id)

        # 删除数据和计数器
        await self.redis_client.delete(stream_key)
        await self.redis_client.delete(counter_key)

    async def set_heartbeat(self, user_id: str, chat_id: str):
        """设置心跳 - 不进行自动会话切换"""
        key = self._heartbeat_key(user_id, chat_id)
        await self.redis_client.setex(
            key,
            self.HEARTBEAT_TTL,
            str(time.time()),
        )

    async def get_heartbeat(
        self,
        user_id: str,
        chat_id: str,
    ) -> Optional[float]:
        """获取心跳时间"""
        key = self._heartbeat_key(user_id, chat_id)
        heartbeat = await self.redis_client.get(key)
        if heartbeat:
            if isinstance(heartbeat, bytes):
                heartbeat = heartbeat.decode("utf-8")
            return float(heartbeat)
        return None

    async def get_expired_users(self, timeout: int = 20) -> List[str]:
        """获取心跳过期的用户（返回复合键格式）"""
        current_time = time.time()
        expired_users = []

        # 扫描所有心跳key
        pattern = f"{self.HEARTBEAT_PREFIX}*"
        async for key in self.redis_client.scan_iter(match=pattern):
            if isinstance(key, bytes):
                key = key.decode("utf-8")

            # 提取复合键（user_id:chat_id）
            composite_key = key.replace(self.HEARTBEAT_PREFIX, "")

            # 解析复合键获取user_id和chat_id
            if ":" in composite_key:
                user_id, chat_id = composite_key.split(":", 1)
            else:
                # 兼容旧格式，如果没有user_id则跳过
                continue

            heartbeat_time = await self.get_heartbeat(user_id, chat_id)

            if heartbeat_time and current_time - heartbeat_time > timeout:
                expired_users.append(composite_key)

        return expired_users

    async def cleanup_chat_data(self, user_id: str, chat_id: str):
        """清理对话相关数据"""
        keys_to_delete = [
            self._chat_state_key(user_id, chat_id),
            self._status_queue_key(user_id, chat_id),
            self._heartbeat_key(user_id, chat_id),
            self._equipment_key(user_id, chat_id),
            f"{self._equipment_key(user_id, chat_id)}_info",
        ]

        # 清理环境操作相关key
        composite_key = self._composite_key(user_id, chat_id)
        pattern = f"{self.ENV_OPERATION_PREFIX}{composite_key}:*"
        async for key in self.redis_client.scan_iter(match=pattern):
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            keys_to_delete.append(key)

        # 清理流式数据相关key
        stream_pattern = f"{self.STREAM_DATA_PREFIX}{composite_key}:*"
        async for key in self.redis_client.scan_iter(match=stream_pattern):
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            keys_to_delete.append(key)

        counter_pattern = f"{self.STREAM_COUNTER_PREFIX}{composite_key}:*"
        async for key in self.redis_client.scan_iter(match=counter_pattern):
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            keys_to_delete.append(key)

        # 清理停止信号相关key
        stop_signal_key = f"computer_use:stop_signal:{composite_key}"
        keys_to_delete.append(stop_signal_key)

        # 检查并清理用户活跃chat_id（仅当当前chat_id是活跃会话时）
        try:
            current_active_chat = await self.get_user_active_chat(user_id)
            if current_active_chat == chat_id:
                # 只有当被清理的chat_id确实是该用户的活跃会话时才清理
                user_active_chat_key = self._user_active_chat_key(user_id)
                keys_to_delete.append(user_active_chat_key)
                logger.info(f"清理用户 {user_id} 的活跃会话映射: {chat_id}")
        except Exception as e:
            logger.warning(f"检查用户活跃会话时出错: {e}")

        if keys_to_delete:
            await self.redis_client.delete(*keys_to_delete)

        logger.info(f"已清理对话 {user_id}:{chat_id} 的所有数据")

    async def start_environment_operation(
        self,
        user_id: str,
        chat_id: str,
        operation_type: str,
        config: dict,
    ) -> str:
        """启动环境操作（激活或切换）"""
        operation_id = str(uuid.uuid4())
        operation_data = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "config": config,
            "user_id": user_id,
            "chat_id": chat_id,
            "status": (
                "initializing" if operation_type == "init" else "switching"
            ),
            "message": "",
            "progress": 0,
            "start_time": time.time(),
            "end_time": None,
            "result": None,
            "error": None,
        }

        # 存储操作记录
        key = self._env_operation_key(user_id, chat_id, operation_id)
        operation_json = json.dumps(operation_data, default=str)
        await self.redis_client.setex(key, 3600, operation_json)

        # 设置为当前操作
        current_key = self._env_operation_key(user_id, chat_id)
        await self.redis_client.setex(current_key, 3600, operation_json)

        # 更新对话状态
        await self.update_chat_state(
            user_id,
            chat_id,
            {
                "current_env_operation": operation_data,
            },
        )

        # 启动后台任务
        if operation_type == "init":
            asyncio.create_task(
                self._execute_environment_init(
                    user_id,
                    chat_id,
                    operation_id,
                    config,
                ),
            )
        elif operation_type == "switch":
            asyncio.create_task(
                self._execute_environment_switch(
                    user_id,
                    chat_id,
                    operation_id,
                    config,
                ),
            )

        logger.info(
            f"Started environment operation {operation_id} for user "
            f"{user_id}, chat {chat_id}",
        )
        return operation_id

    async def update_environment_operation(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """更新环境操作状态"""
        key = self._env_operation_key(user_id, chat_id, operation_id)
        operation_data = await self.redis_client.get(key)

        if operation_data:
            if isinstance(operation_data, bytes):
                operation_data = operation_data.decode("utf-8")
            operation_data = json.loads(operation_data)
            operation_data.update(updates)
            operation_data["updated_at"] = time.time()

            # 更新操作记录
            operation_json = json.dumps(operation_data, default=str)
            await self.redis_client.setex(key, 3600, operation_json)

            # 更新当前操作
            current_key = self._env_operation_key(user_id, chat_id)
            await self.redis_client.setex(current_key, 3600, operation_json)

            # 更新对话状态
            await self.update_chat_state(
                user_id,
                chat_id,
                {
                    "current_env_operation": operation_data,
                },
            )

            return operation_data
        return None

    async def get_current_environment_operation(
        self,
        user_id: str,
        chat_id: str,
    ) -> Optional[Dict[str, Any]]:
        """获取当前环境操作"""
        key = self._env_operation_key(user_id, chat_id)
        operation_data = await self.redis_client.get(key)

        if operation_data:
            if isinstance(operation_data, bytes):
                operation_data = operation_data.decode("utf-8")
            return json.loads(operation_data)
        return None

    async def get_environment_operation(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """获取指定的环境操作"""
        key = self._env_operation_key(user_id, chat_id, operation_id)
        operation_data = await self.redis_client.get(key)

        if operation_data:
            if isinstance(operation_data, bytes):
                operation_data = operation_data.decode("utf-8")
            return json.loads(operation_data)
        return None

    # === 兼容原有StateManager接口的方法 ===

    async def update_status(
        self,
        user_id: str,
        chat_id: str,
        status_data: dict,
    ):
        """更新状态（兼容原有接口）"""
        # 构建完整的状态消息
        new_status = {
            "user_id": user_id,
            "chat_id": chat_id,
            **status_data,
            "uuid": str(uuid.uuid4()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 推送到Redis状态队列
        await self.push_status_message(user_id, chat_id, new_status)

        # 同时更新内存队列（为了兼容性）
        composite_key = self._composite_key(user_id, chat_id)
        if composite_key in self.status_queues:
            try:
                await self.status_queues[composite_key].put(new_status)
            except Exception as e:
                logger.error(f"更新内存状态队列失败: {e}")

    async def stop_task(self, user_id: str, chat_id: str):
        """停止任务"""
        # 设置停止信号，让运行中的agent能够检查到
        composite_key = self._composite_key(user_id, chat_id)
        stop_signal_key = f"computer_use:stop_signal:{composite_key}"
        await self.redis_client.setex(
            stop_signal_key,
            60,
            "stop_requested",
        )  # 60秒过期

        # 更新对话状态
        await self.update_chat_state(
            user_id,
            chat_id,
            {
                "is_running": False,
                "current_task": None,
                "agent": None,
                "background_task": None,
                "task_id": None,
                "stop_requested": True,  # 添加停止请求标志
            },
        )

        # 清空状态队列
        await self.clear_status_queue(user_id, chat_id)

        # 发送停止状态
        await self.update_status(
            user_id,
            chat_id,
            {
                "status": "stopping",
                "message": "Stop request sent, waiting for agent to "
                "terminate...",
                "type": "SYSTEM",
            },
        )

    async def check_stop_signal(self, user_id: str, chat_id: str) -> bool:
        """检查对话是否有停止信号"""
        composite_key = self._composite_key(user_id, chat_id)
        stop_signal_key = f"computer_use:stop_signal:{composite_key}"
        signal = await self.redis_client.get(stop_signal_key)
        return signal is not None

    async def clear_stop_signal(self, user_id: str, chat_id: str):
        """清除停止信号"""
        composite_key = self._composite_key(user_id, chat_id)
        stop_signal_key = f"computer_use:stop_signal:{composite_key}"
        await self.redis_client.delete(stop_signal_key)

    async def release_user_resources(self, user_id: str):
        """释放用户级别的所有资源"""
        try:
            logger.info(
                f"[release_user_resources] 开始释放用户 {user_id} 的所有资源",
            )
            released_resource_type = None

            # 用户级别的资源释放逻辑
            # 检查PC资源分配
            logger.info(
                f"[release_user_resources] 检查用户 {user_id} 的PC资源分配状态",
            )
            pc_instance_id, pc_status = (
                await self.pc_allocator.get_chat_allocation_async(user_id)
            )
            logger.info(
                f"[release_user_resources] PC资源查询结果: "
                f"instance_id={pc_instance_id}, status={pc_status}",
            )

            if (
                pc_status == AllocationStatus.SUCCESS
                or pc_status == AllocationStatus.CHAT_ALREADY_ALLOCATED
            ) and pc_instance_id:
                logger.info(
                    f"[release_user_resources] 释放用户 {user_id} 的PC资源: "
                    f"{pc_instance_id}",
                )
                release_result = await self.pc_allocator.release_async(
                    pc_instance_id,
                )
                logger.info(
                    f"[release_user_resources] PC资源释放结果: {release_result}",
                )
                released_resource_type = "pc_wuyin"
            else:
                logger.info(
                    f"[release_user_resources] 用户 {user_id} 没有PC资源需要释放",
                )

            # 检查手机资源分配
            logger.info(
                f"[release_user_resources] 检查用户 {user_id} 的手机资源分配状态",
            )
            phone_instance_id, phone_status = (
                await self.phone_allocator.get_chat_allocation_async(user_id)
            )
            logger.info(
                f"[release_user_resources] 手机资源查询结果: "
                f"instance_id={phone_instance_id}, status={phone_status}",
            )

            if (
                phone_status == AllocationStatus.SUCCESS
                or phone_status == AllocationStatus.CHAT_ALREADY_ALLOCATED
            ) and phone_instance_id:
                logger.info(
                    f"[release_user_resources] 释放用户 {user_id} 的手机资源: "
                    f"{phone_instance_id}",
                )
                release_result = await self.phone_allocator.release_async(
                    phone_instance_id,
                )
                logger.info(
                    f"[release_user_resources] 手机资源释放结果: {release_result}",
                )
                released_resource_type = "phone_wuyin"
            else:
                logger.info(
                    f"[release_user_resources] 用户 {user_id} 没有手机资源需要释放",
                )

            # 清理用户排队状态
            try:
                logger.info(
                    f"[release_user_resources] 清理用户 {user_id} 的排队状态",
                )
                pc_position, pc_wait_status = (
                    await self.pc_allocator.get_chat_wait_position_async(
                        user_id,
                    )
                )
                phone_position, phone_wait_status = (
                    await self.phone_allocator.get_chat_wait_position_async(
                        user_id,
                    )
                )

                if pc_wait_status == AllocationStatus.SUCCESS:
                    await self.pc_allocator.cancel_wait_async(user_id)
                    logger.info(
                        f"[release_user_resources] 已取消用户 {user_id} 的PC排队",
                    )
                if phone_wait_status == AllocationStatus.SUCCESS:
                    await self.phone_allocator.cancel_wait_async(user_id)
                    logger.info(
                        f"[release_user_resources] 已取消用户 {user_id} 的手机排队",
                    )
            except Exception as e:
                logger.error(
                    f"[release_user_resources] 清理用户 {user_id} 排队状态出错: {e}",
                )

            # 通知排队用户资源可用
            if released_resource_type:
                logger.info(
                    f"[release_user_resources] 释放了 {released_resource_type} "
                    f"资源，通知排队用户",
                )
                asyncio.create_task(
                    self._notify_queued_users(released_resource_type),
                )
            else:
                logger.info(
                    f"[release_user_resources] 用户 {user_id} 没有释放任何资源",
                )

            logger.info(
                f"[release_user_resources] 用户 {user_id} 资源释放完成",
            )

        except Exception as e:
            logger.error(f"释放用户 {user_id} 资源时出错: {e}")
            import traceback

            logger.error(f"错误详情: {traceback.format_exc()}")

    async def release_resources(self, user_id: str, chat_id: str):
        """释放资源（兼容旧接口，内部调用用户级别释放）"""
        # 清理设备
        equipment_info = await self.get_equipment_info(user_id, chat_id)
        if equipment_info:
            await self.delete_equipment(user_id, chat_id)

        # 调用用户级别的资源释放
        await self.release_user_resources(user_id)

        # 彻底清理对话数据，包括重置对话状态
        try:
            await self.cleanup_chat_data(user_id, chat_id)
            logger.info(f"已彻底清理对话 {user_id}:{chat_id} 的所有数据")
        except Exception as e:
            logger.warning(f"清理对话数据时出错: {e}")
            # 如果cleanup_chat_data失败，至少重置对话状态
            try:
                await self.update_chat_state(
                    user_id,
                    chat_id,
                    {
                        "equipment": None,
                        "sandbox": None,
                        "task_id": None,
                        "sandbox_type": None,
                        "equipment_web_url": None,
                    },
                )
            except Exception as update_error:
                logger.error(f"重置对话状态也失败: {update_error}")

    async def _notify_queued_users(self, resource_type: str):
        """通知排队对话资源可用"""
        logger.info(
            f"[_notify_queued_users] 通知排队对话，资源类型: {resource_type}",
        )

        try:
            if resource_type == "pc_wuyin":
                allocator = self.pc_allocator
            elif resource_type == "phone_wuyin":
                allocator = self.phone_allocator
            else:
                return

            queue_info = allocator.get_queue_info()
            queued_users = queue_info.get("waiting_users", [])

            # 为第一个排队对话尝试分配资源
            for queued_chat_id in queued_users[:1]:
                try:
                    instance_id, status = await allocator.allocate_async(
                        queued_chat_id,
                        timeout=0,
                    )

                    if status == AllocationStatus.SUCCESS:
                        logger.info(
                            f"[_notify_queued_users] 为对话 {queued_chat_id} "
                            f"分配资源: {instance_id}",
                        )

                        # 通知对话资源可用
                        # 解析复合键获取user_id和chat_id
                        if ":" in queued_chat_id:
                            user_id, chat_id = queued_chat_id.split(":", 1)
                        else:
                            # 兼容旧格式
                            user_id, chat_id = "unknown", queued_chat_id

                        await self.update_status(
                            user_id,
                            chat_id,
                            {
                                "status": "resource_available",
                                "type": "SYSTEM",
                                "message": "Resource available! Please "
                                "reactivate your environment.",
                                "resource_type": resource_type,
                                "resource_id": instance_id,
                            },
                        )
                        break

                except Exception as e:
                    logger.error(
                        f"[_notify_queued_users] 分配资源出错: {e}",
                    )

        except Exception as e:
            logger.error(f"[_notify_queued_users] 通知排队对话出错: {e}")

    async def _monitor_heartbeats(self):
        """心跳监控任务 - 增强版，支持更可靠的超时检测和彻底清理"""
        logger.info("Redis heartbeat monitor started")
        heartbeat_timeout = 30  # 心跳超时时间（秒）

        while True:
            try:
                # 同时检查Redis和内存中的心跳记录
                expired_users = []
                current_time = time.time()

                # 方法1：从Redis获取过期的用户
                redis_expired = await self.get_expired_users(
                    timeout=heartbeat_timeout,
                )
                expired_users.extend(redis_expired)

                # 方法2：检查内存中的心跳记录（兜底检查）
                memory_expired = []
                for chat_id, last_heartbeat in self.heartbeats.items():
                    if current_time - last_heartbeat > heartbeat_timeout:
                        memory_expired.append(chat_id)

                # 合并去重
                all_expired = list(set(expired_users + memory_expired))

                # 对过期用户进行二次确认，避免误释放
                confirmed_expired = []
                for composite_key in all_expired:
                    # 解析复合键获取user_id和chat_id
                    if ":" in composite_key:
                        user_id, chat_id = composite_key.split(":", 1)
                    else:
                        # 兼容旧格式（如果有的话）
                        user_id, chat_id = "unknown", composite_key

                    # 再次检查Redis中的心跳时间
                    redis_heartbeat = await self.get_heartbeat(
                        user_id,
                        chat_id,
                    )
                    memory_heartbeat = self.heartbeats.get(composite_key, 0)

                    # 取最新的心跳时间
                    latest_heartbeat = max(
                        redis_heartbeat or 0,
                        memory_heartbeat,
                    )

                    if current_time - latest_heartbeat > heartbeat_timeout:
                        confirmed_expired.append(composite_key)
                        logger.warning(
                            f"[HeartbeatMonitor] 确认用户心跳超时: {composite_key} "
                            f"(超时 {current_time - latest_heartbeat:.1f}秒)",
                        )

                # 释放确认超时的用户资源
                for composite_key in confirmed_expired:
                    try:
                        # 解析复合键获取user_id和chat_id
                        if ":" in composite_key:
                            user_id, chat_id = composite_key.split(":", 1)
                        else:
                            # 兼容旧格式
                            user_id, chat_id = "unknown", composite_key

                        logger.info(
                            f"[HeartbeatMonitor] 开始彻底清理超时用户: {composite_key}",
                        )

                        # 1. 检查用户是否有活跃的任务，如果有则停止
                        chat_state = await self.get_chat_state(
                            user_id,
                            chat_id,
                        )
                        if chat_state.get("is_running"):
                            logger.info(
                                f"[HeartbeatMonitor] 停止用户任务: {composite_key}",
                            )
                            await self.stop_task(user_id, chat_id)
                            await asyncio.sleep(1)  # 给任务一点时间停止

                        # 2. 彻底清理用户的所有Redis资源
                        await self._thorough_cleanup_user_resources(
                            user_id,
                            chat_id,
                        )

                        # 3. 清理内存心跳记录
                        if composite_key in self.heartbeats:
                            del self.heartbeats[composite_key]

                        logger.info(
                            f"[HeartbeatMonitor] 成功彻底清理用户资源: {composite_key}",
                        )

                    except Exception as e:
                        logger.error(
                            f"[HeartbeatMonitor] 清理用户 {composite_key} "
                            f"资源时出错: {e}",
                        )
                        import traceback

                        logger.error(
                            f"[HeartbeatMonitor] 错误详情: "
                            f"{traceback.format_exc()}",
                        )

                await asyncio.sleep(10)  # 调整监控间隔为10秒，更及时响应

            except Exception as e:
                logger.error(f"Redis heartbeat monitor error: {e}")
                await asyncio.sleep(10)

    async def _thorough_cleanup_user_resources(
        self,
        user_id: str,
        chat_id: str,
    ):
        """彻底清理用户的所有Redis资源 - 增强版"""
        try:
            logger.info(
                f"[_thorough_cleanup_user_resources] 开始彻底清理用户 "
                f"{user_id}:{chat_id} 的所有资源",
            )

            # 1. 释放物理资源（PC和手机）
            await self._cleanup_physical_resources(user_id)

            # 2. 清理资源分配器中的相关记录
            await self._cleanup_allocator_records(user_id)

            # 3. 清理对话相关的所有Redis数据
            await self._cleanup_all_chat_data(user_id, chat_id)

            # 4. 清理用户级别的Redis数据
            await self._cleanup_user_level_data(user_id, chat_id)

            logger.info(
                f"[_thorough_cleanup_user_resources] 彻底清理完成: "
                f"{user_id}:{chat_id}",
            )

        except Exception as e:
            logger.error(
                f"[_thorough_cleanup_user_resources] 彻底清理用户 "
                f"{user_id}:{chat_id} 时出错: {e}",
            )
            import traceback

            logger.error(
                f"[_thorough_cleanup_user_resources] 错误详情: "
                f"{traceback.format_exc()}",
            )

    async def _cleanup_physical_resources(self, user_id: str):
        """清理物理资源（PC和手机）"""
        try:
            released_resource_type = None

            # 检查并释放PC资源
            logger.info(
                f"[_cleanup_physical_resources] 检查用户 {user_id} 的PC资源",
            )
            try:
                pc_instance_id, pc_status = (
                    await self.pc_allocator.get_chat_allocation_async(user_id)
                )
                if (
                    pc_status == AllocationStatus.SUCCESS
                    or pc_status == AllocationStatus.CHAT_ALREADY_ALLOCATED
                ) and pc_instance_id:
                    logger.info(
                        f"[_cleanup_physical_resources] 释放用户 {user_id} "
                        f"的PC资源: {pc_instance_id}",
                    )
                    release_result = await self.pc_allocator.release_async(
                        pc_instance_id,
                    )
                    logger.info(
                        f"[_cleanup_physical_resources] PC资源释放结果: "
                        f"{release_result}",
                    )
                    released_resource_type = "pc_wuyin"
                else:
                    logger.info(
                        f"[_cleanup_physical_resources] 用户 {user_id} "
                        f"没有PC资源需要释放",
                    )
            except Exception as e:
                logger.error(
                    f"[_cleanup_physical_resources] 释放PC资源时出错: {e}",
                )

            # 检查并释放手机资源
            logger.info(
                f"[_cleanup_physical_resources] 检查用户 {user_id} 的手机资源",
            )
            try:
                phone_instance_id, phone_status = (
                    await self.phone_allocator.get_chat_allocation_async(
                        user_id,
                    )
                )
                if (
                    phone_status == AllocationStatus.SUCCESS
                    or phone_status == AllocationStatus.CHAT_ALREADY_ALLOCATED
                ) and phone_instance_id:
                    logger.info(
                        f"[_cleanup_physical_resources] 释放用户 {user_id} "
                        f"的手机资源: {phone_instance_id}",
                    )
                    release_result = await self.phone_allocator.release_async(
                        phone_instance_id,
                    )
                    logger.info(
                        f"[_cleanup_physical_resources] 手机资源释放结果: "
                        f"{release_result}",
                    )
                    released_resource_type = "phone_wuyin"
                else:
                    logger.info(
                        f"[_cleanup_physical_resources] 用户 {user_id} "
                        f"没有手机资源需要释放",
                    )
            except Exception as e:
                logger.error(
                    f"[_cleanup_physical_resources] 释放手机资源时出错: {e}",
                )

            # 通知排队用户资源可用
            if released_resource_type:
                logger.info(
                    f"[_cleanup_physical_resources] 释放了 "
                    f"{released_resource_type} 资源，通知排队用户",
                )
                asyncio.create_task(
                    self._notify_queued_users(released_resource_type),
                )

        except Exception as e:
            logger.error(
                f"[_cleanup_physical_resources] 清理物理资源时出错: {e}",
            )

    async def _cleanup_allocator_records(self, user_id: str):
        """清理资源分配器中的用户记录"""
        try:
            logger.info(
                f"[_cleanup_allocator_records] 清理用户 {user_id} 的分配器记录",
            )

            # 清理PC分配器中的排队记录
            try:
                pc_position, pc_wait_status = (
                    await self.pc_allocator.get_chat_wait_position_async(
                        user_id,
                    )
                )
                if pc_wait_status == AllocationStatus.SUCCESS:
                    await self.pc_allocator.cancel_wait_async(user_id)
                    logger.info(
                        f"[_cleanup_allocator_records] 已取消用户 {user_id} 的PC排队",
                    )
            except Exception as e:
                logger.error(
                    f"[_cleanup_allocator_records] 清理PC排队记录时出错: {e}",
                )

            # 清理手机分配器中的排队记录
            try:
                phone_position, phone_wait_status = (
                    await self.phone_allocator.get_chat_wait_position_async(
                        user_id,
                    )
                )
                if phone_wait_status == AllocationStatus.SUCCESS:
                    await self.phone_allocator.cancel_wait_async(user_id)
                    logger.info(
                        f"[_cleanup_allocator_records] 已取消用户 {user_id} 的手机排队",
                    )
            except Exception as e:
                logger.error(
                    f"[_cleanup_allocator_records] 清理手机排队记录时出错: {e}",
                )

            # 直接清理Redis中的用户分配记录（确保彻底清理）
            try:
                if (
                    hasattr(self.pc_allocator, "allocator")
                    and self.pc_allocator.allocator
                ):
                    # 直接从Redis删除用户的分配记录
                    await self.redis_client.hdel(
                        self.pc_allocator.allocator.USER_ALLOCATIONS_KEY,
                        user_id,
                    )
                    await self.redis_client.lrem(
                        self.pc_allocator.allocator.QUEUE_KEY,
                        0,
                        user_id,
                    )
                    await self.redis_client.hdel(
                        self.pc_allocator.allocator.QUEUE_TIMESTAMPS_KEY,
                        user_id,
                    )
                    logger.info(
                        f"[_cleanup_allocator_records] 已直接清理用户 "
                        f"{user_id} 的PC分配器Redis记录",
                    )
            except Exception as e:
                logger.error(
                    f"[_cleanup_allocator_records] 直接清理PC分配器Redis记录时出错: {e}",
                )

            try:
                if (
                    hasattr(self.phone_allocator, "allocator")
                    and self.phone_allocator.allocator
                ):
                    # 直接从Redis删除用户的分配记录
                    await self.redis_client.hdel(
                        self.phone_allocator.allocator.USER_ALLOCATIONS_KEY,
                        user_id,
                    )
                    await self.redis_client.lrem(
                        self.phone_allocator.allocator.QUEUE_KEY,
                        0,
                        user_id,
                    )
                    await self.redis_client.hdel(
                        self.phone_allocator.allocator.QUEUE_TIMESTAMPS_KEY,
                        user_id,
                    )
                    logger.info(
                        f"[_cleanup_allocator_records] 已直接清理用户 "
                        f"{user_id} 的手机分配器Redis记录",
                    )
            except Exception as e:
                logger.error(
                    f"[_cleanup_allocator_records] 直接清理手机分配器Redis记录时出错: {e}",
                )

        except Exception as e:
            logger.error(
                f"[_cleanup_allocator_records] 清理分配器记录时出错: {e}",
            )

    async def _cleanup_all_chat_data(self, user_id: str, chat_id: str):
        """清理对话相关的所有Redis数据 - 增强版"""
        try:
            logger.info(
                f"[_cleanup_all_chat_data] 清理对话数据: {user_id}:{chat_id}",
            )

            # 清理设备信息
            equipment_info = await self.get_equipment_info(user_id, chat_id)
            if equipment_info:
                await self.delete_equipment(user_id, chat_id)
                logger.info("[_cleanup_all_chat_data] 已清理设备信息")

            # 调用原有的清理方法
            await self.cleanup_chat_data(user_id, chat_id)

        except Exception as e:
            logger.error(f"[_cleanup_all_chat_data] 清理对话数据时出错: {e}")

    async def _cleanup_user_level_data(self, user_id: str, chat_id: str):
        """清理用户级别的Redis数据"""
        try:
            logger.info(
                f"[_cleanup_user_level_data] 清理用户级别数据: {user_id}",
            )

            # 扫描并清理所有可能的用户相关键
            patterns_to_clean = [
                f"computer_use:*:{user_id}:*",  # 通用用户相关键
                "resource_allocator:*:user_allocations",  # 用户分配记录
                "resource_allocator:*:queue*",  # 排队相关
                f"computer_use:user_active_chat:{user_id}",  # 用户活跃chat
            ]

            for pattern in patterns_to_clean:
                try:
                    keys_to_delete = []
                    async for key in self.redis_client.scan_iter(
                        match=pattern,
                    ):
                        if isinstance(key, bytes):
                            key = key.decode("utf-8")

                        # 对于用户分配记录，检查是否包含该用户
                        if "user_allocations" in key:
                            # 检查hash中是否有该用户的记录
                            if await self.redis_client.hexists(key, user_id):
                                await self.redis_client.hdel(key, user_id)
                                logger.info(
                                    f"[_cleanup_user_level_data] 清理用户分配记录: "
                                    f"{key}",
                                )
                        elif "queue" in key and "timestamps" not in key:
                            # 清理队列中的用户记录
                            removed = await self.redis_client.lrem(
                                key,
                                0,
                                user_id,
                            )
                            if removed > 0:
                                logger.info(
                                    f"[_cleanup_user_level_data] 清理队列记录: "
                                    f"{key}, "
                                    f"移除 {removed} 条",
                                )
                        elif "queue_timestamps" in key:
                            # 清理队列时间戳记录
                            if await self.redis_client.hexists(key, user_id):
                                await self.redis_client.hdel(key, user_id)
                                logger.info(
                                    f"[_cleanup_user_level_data] 清理队列时间戳记录: "
                                    f"{key}",
                                )
                        elif key.endswith(user_id):
                            # 直接删除以用户ID结尾的键
                            keys_to_delete.append(key)

                    # 批量删除键
                    if keys_to_delete:
                        await self.redis_client.delete(*keys_to_delete)
                        logger.info(
                            f"[_cleanup_user_level_data] 批量删除 "
                            f"{len(keys_to_delete)} 个用户相关键",
                        )

                except Exception as e:
                    logger.error(
                        f"[_cleanup_user_level_data] 清理模式 {pattern} 时出错: {e}",
                    )

        except Exception as e:
            logger.error(
                f"[_cleanup_user_level_data] 清理用户级别数据时出错: {e}",
            )

    async def _execute_environment_init(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
        config: dict,
    ):
        """执行环境初始化"""
        try:
            # 检查用户是否已在同一chat_id中有活跃会话
            current_active_chat = await self.get_user_active_chat(user_id)
            is_same_session_reactivation = current_active_chat == chat_id

            if is_same_session_reactivation:
                # 检查是否已有设备且不需要重启
                chat_state = await self.get_chat_state(user_id, chat_id)
                equipment_info = await self.get_equipment_info(
                    user_id,
                    chat_id,
                )

                if chat_state.get("equipment") or equipment_info:
                    logger.info(
                        f"用户 {user_id} 在 chat {chat_id} 已有设备，刷新认证信息后重用",
                    )
                    # 需要刷新认证信息，特别是auth_code等一次性凭证
                    if equipment_info:
                        static_url = config.get("static_url", "")
                        sandbox_type = config.get("sandbox_type")
                        task_id = str(uuid.uuid4())

                        result = {"task_id": task_id}

                        if sandbox_type == "pc_wuyin":
                            # 刷新PC设备的auth_code
                            try:
                                app_stream_client = AppStreamClient()
                                new_auth_code = (
                                    await app_stream_client.search_auth_code()
                                )

                                # 更新设备信息中的auth_code
                                equipment_info["instance_manager_info"][
                                    "auth_code"
                                ] = new_auth_code

                                # 重新存储更新后的设备信息
                                info_key = (
                                    f"{self._equipment_key(user_id, chat_id)}"
                                    f"_info"
                                )
                                await self.redis_client.setex(
                                    info_key,
                                    self.EQUIPMENT_TTL,
                                    json.dumps(equipment_info, default=str),
                                )

                                logger.info(
                                    f"已刷新PC设备的auth_code: "
                                    f"{new_auth_code[:20]}...",
                                )

                                result.update(
                                    {
                                        "equipment_web_url": f"{static_url}"
                                        f"equipment_computer.html",
                                        "equipment_web_sdk_info": {
                                            "auth_code": new_auth_code,
                                            "desktop_id": equipment_info[
                                                "instance_manager_info"
                                            ]["desktop_id"],
                                            "static_url": static_url,
                                        },
                                    },
                                )
                            except Exception as e:
                                logger.error(f"刷新PC设备auth_code失败: {e}")
                                # 如果刷新失败，使用旧的auth_code（可能会失败，但至少保持向后兼容）
                                result.update(
                                    {
                                        "equipment_web_url": f"{static_url}"
                                        f"equipment_computer.html",
                                        "equipment_web_sdk_info": {
                                            "auth_code": equipment_info[
                                                "instance_manager_info"
                                            ]["auth_code"],
                                            "desktop_id": equipment_info[
                                                "instance_manager_info"
                                            ]["desktop_id"],
                                            "static_url": static_url,
                                        },
                                    },
                                )

                        elif sandbox_type == "phone_wuyin":
                            # 手机设备的ticket通常有更长的有效期，但也可以考虑刷新
                            result.update(
                                {
                                    "equipment_web_url": f"{static_url}"
                                    f"equipment_phone.html",
                                    "equipment_web_sdk_info": {
                                        "ticket": equipment_info[
                                            "instance_manager_info"
                                        ]["ticket"],
                                        "person_app_id": equipment_info[
                                            "instance_manager_info"
                                        ]["person_app_id"],
                                        "app_instance_id": equipment_info[
                                            "instance_manager_info"
                                        ]["instance_id"],
                                        "static_url": static_url,
                                    },
                                },
                            )

                        # 标记操作完成
                        await self.update_environment_operation(
                            user_id,
                            chat_id,
                            operation_id,
                            {
                                "status": "completed",
                                "message": "环境已存在，已刷新认证信息",
                                "progress": 100,
                                "end_time": time.time(),
                                "result": result,
                            },
                        )

                        await self._notify_operation_progress(
                            user_id,
                            chat_id,
                            operation_id,
                        )
                        return

            # 如果是不同的chat_id或没有现有设备，清理旧会话
            # 注意：这里直接清理，因为是环境初始化操作
            await self.cleanup_user_old_sessions(user_id, chat_id)

            operation = await self.get_environment_operation(
                user_id,
                chat_id,
                operation_id,
            )
            if not operation or operation["operation_id"] != operation_id:
                return

            # 更新进度：开始初始化
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "message": "开始环境初始化...",
                    "progress": 10,
                },
            )

            # 执行原有的设备初始化逻辑
            result = await self._init_equipment_async(
                user_id,
                chat_id,
                config,
                restart_device=True,
                is_session_switch=is_same_session_reactivation,
                # 传递是否为同一会话重新激活的标志
            )

            # 初始化成功
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "status": "completed",
                    "message": "环境初始化完成",
                    "progress": 100,
                    "end_time": time.time(),
                    "result": result,
                },
            )

            await self._notify_operation_progress(
                user_id,
                chat_id,
                operation_id,
            )

        except Exception as http_exc:
            # 检查是否为HTTPException（排队情况）
            from fastapi import HTTPException

            if isinstance(http_exc, HTTPException) and hasattr(
                http_exc,
                "status_code",
            ):
                if (
                    http_exc.status_code == 429
                    and hasattr(http_exc, "detail")
                    and isinstance(http_exc.detail, dict)
                ):
                    # 排队情况
                    if http_exc.detail.get("type") == "queued":
                        q_p = http_exc.detail.get("queue_position", 0)
                        t_w = http_exc.detail.get("total_waiting", 0)
                        await self.update_environment_operation(
                            user_id,
                            chat_id,
                            operation_id,
                            {
                                "status": "queued",
                                "message": (
                                    f"资源不足，已加入排队队列 (位置:"
                                    f" {q_p}"
                                    f"/{t_w})"
                                ),
                                "progress": 0,
                                "end_time": time.time(),
                                "error": str(http_exc.detail),
                            },
                        )

                        await self._notify_operation_progress(
                            user_id,
                            chat_id,
                            operation_id,
                        )

                        # 启动排队监控和自动重试逻辑
                        asyncio.create_task(
                            self._handle_queue_retry(
                                user_id,
                                chat_id,
                                operation_id,
                                config,
                                "init",
                            ),
                        )
                        return

                # 其他HTTPException当作失败处理
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "status": "failed",
                        "message": f"环境初始化失败: HTTP {http_exc.status_code}",
                        "progress": 0,
                        "end_time": time.time(),
                        "error": (
                            str(http_exc.detail)
                            if hasattr(http_exc, "detail")
                            else str(http_exc)
                        ),
                    },
                )

                await self._notify_operation_progress(
                    user_id,
                    chat_id,
                    operation_id,
                )

            else:
                # 其他异常
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "status": "failed",
                        "message": f"环境初始化失败: {str(http_exc)}",
                        "progress": 0,
                        "end_time": time.time(),
                        "error": str(http_exc),
                    },
                )

                await self._notify_operation_progress(
                    user_id,
                    chat_id,
                    operation_id,
                )

            logger.error(
                f"Environment init exception for user {chat_id}: {http_exc}",
            )

    async def _execute_environment_switch(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
        config: dict,
    ):
        """执行环境切换"""
        try:
            operation = await self.get_environment_operation(
                user_id,
                chat_id,
                operation_id,
            )
            if not operation or operation["operation_id"] != operation_id:
                return

            # 更新进度：开始切换
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "message": "开始环境切换...",
                    "progress": 10,
                },
            )

            # 1. 停止当前任务
            chat_state = await self.get_chat_state(user_id, chat_id)
            if chat_state.get("is_running"):
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "message": "停止当前任务...",
                        "progress": 20,
                    },
                )
                await self.stop_task(user_id, chat_id)
                await asyncio.sleep(0.5)

            # 2. 释放当前资源
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "message": "释放当前资源...",
                    "progress": 40,
                },
            )
            # 设备切换时先清理设备信息，再释放物理资源
            equipment_info = await self.get_equipment_info(user_id, chat_id)
            if equipment_info:
                logger.info(
                    f"删除旧设备信息: 用户 {user_id}, 对话 {chat_id}, "
                    f"类型: {equipment_info.get('equipment_type', 'unknown')}",
                )
                await self.delete_equipment(user_id, chat_id)
                # 额外清理：确保设备信息完全从chat_state中移除
                await self.update_chat_state(
                    user_id,
                    chat_id,
                    {
                        "equipment": None,
                        "equipment_storage_status": None,
                        "equipment_info": None,
                        "sandbox_type": None,  # 清理sandbox_type避免类型混淆
                        "equipment_web_url": None,  # 清理URL信息
                    },
                )
                logger.info(
                    f"已完全清理用户 {user_id} 对话 {chat_id} 的设备信息",
                )
            # 调用用户级别的资源释放（释放物理资源）
            await self.release_user_resources(user_id)

            # 3. 初始化新环境
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "message": "初始化新环境...",
                    "progress": 60,
                },
            )

            result = await self._init_equipment_async(
                user_id,
                chat_id,
                config,
                restart_device=True,
                is_session_switch=True,  # 标识为会话内设备切换
            )

            # 切换成功
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "status": "completed",
                    "message": "环境切换完成",
                    "progress": 100,
                    "end_time": time.time(),
                    "result": result,
                },
            )

            # 确保用户活跃会话状态正确
            await self.set_user_active_chat(user_id, chat_id)

            await self._notify_operation_progress(
                user_id,
                chat_id,
                operation_id,
            )

        except Exception as http_exc:
            # 处理异常
            from fastapi import HTTPException

            if isinstance(http_exc, HTTPException) and hasattr(
                http_exc,
                "status_code",
            ):
                if (
                    http_exc.status_code == 429
                    and hasattr(http_exc, "detail")
                    and isinstance(http_exc.detail, dict)
                ):
                    # 排队情况
                    if http_exc.detail.get("type") == "queued":
                        qu_p = http_exc.detail.get("queue_position", 0)
                        to_w = http_exc.detail.get("total_waiting", 0)
                        await self.update_environment_operation(
                            user_id,
                            chat_id,
                            operation_id,
                            {
                                "status": "queued",
                                "message": (
                                    f"资源不足，已加入排队队列 (位置:"
                                    f" {qu_p}"
                                    f"/{to_w})"
                                ),
                                "progress": 0,
                                "end_time": time.time(),
                                "error": str(http_exc.detail),
                            },
                        )

                        await self._notify_operation_progress(
                            user_id,
                            chat_id,
                            operation_id,
                        )

                        # 启动排队监控和自动重试逻辑
                        asyncio.create_task(
                            self._handle_queue_retry(
                                user_id,
                                chat_id,
                                operation_id,
                                config,
                                "switch",
                            ),
                        )
                        return

                # 其他HTTPException当作失败处理
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "status": "failed",
                        "message": f"环境切换失败: HTTP {http_exc.status_code}",
                        "progress": 0,
                        "end_time": time.time(),
                        "error": (
                            str(http_exc.detail)
                            if hasattr(http_exc, "detail")
                            else str(http_exc)
                        ),
                    },
                )

                await self._notify_operation_progress(
                    user_id,
                    chat_id,
                    operation_id,
                )
            else:
                # 其他异常
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "status": "failed",
                        "message": f"环境切换失败: {str(http_exc)}",
                        "progress": 0,
                        "end_time": time.time(),
                        "error": str(http_exc),
                    },
                )

                await self._notify_operation_progress(
                    user_id,
                    chat_id,
                    operation_id,
                )

            logger.error(
                f"Environment switch exception for user {chat_id}: {http_exc}",
            )

    async def _handle_queue_retry(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
        config: dict,
        operation_type: str,
    ):
        """处理排队监控和自动重试"""
        max_retries = 10  # 最大重试次数
        retry_interval = 30  # 重试间隔（秒）

        for attempt in range(max_retries):
            try:
                print(
                    f"[排队监控] 第 {attempt + 1} 次监控排队状态，对话: {chat_id}",
                )

                # 检查操作是否仍然有效
                operation = await self.get_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                )
                if not operation or operation["operation_id"] != operation_id:
                    print("[排队监控] 操作已取消或变更，停止监控")
                    return

                # 等待一段时间再重试
                await asyncio.sleep(retry_interval)

                # 再次检查操作状态
                operation = await self.get_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                )
                if not operation or operation["operation_id"] != operation_id:
                    print("[排队监控] 操作已取消，停止监控")
                    return

                # 如果操作状态不再是排队中，则停止监控
                if operation.get("status") != "queued":
                    print(
                        f"[排队监控] 操作状态已变更 ({operation.get('status')})，停止监控",
                    )
                    return

                # 更新操作状态为重试中
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "status": "waiting_retry",
                        "message": f"第 {attempt + 1} 次尝试重新激活环境...",
                        "progress": 5,
                    },
                )

                await self._notify_operation_progress(
                    user_id,
                    chat_id,
                    operation_id,
                )

                # 尝试重新执行
                if operation_type == "init":
                    await self._retry_environment_init(
                        user_id,
                        chat_id,
                        operation_id,
                        config,
                    )
                elif operation_type == "switch":
                    await self._retry_environment_switch(
                        user_id,
                        chat_id,
                        operation_id,
                        config,
                    )

                # 检查重试结果
                operation = await self.get_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                )
                if operation and operation.get("status") == "completed":
                    print("[排队监控] 重试成功，停止监控")
                    return
                elif operation and operation.get("status") == "failed":
                    print("[排队监控] 重试失败，停止监控")
                    return
                # 如果仍然是排队状态，继续下一次循环

            except Exception as e:
                print(f"[排队监控] 第 {attempt + 1} 次重试出错: {e}")

        # 所有重试都失败，标记为失败
        await self.update_environment_operation(
            user_id,
            chat_id,
            operation_id,
            {
                "status": "failed",
                "message": f"排队重试超过最大次数 ({max_retries})，请手动重试",
                "progress": 0,
                "end_time": time.time(),
                "error": "Queue retry timeout",
            },
        )

        await self._notify_operation_progress(user_id, chat_id, operation_id)
        print("[排队监控] 超过最大重试次数，停止监控")

    async def _retry_environment_init(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
        config: dict,
    ):
        """重试环境初始化"""
        try:
            result = await self._init_equipment_async(
                user_id,
                chat_id,
                config,
                restart_device=True,
                is_session_switch=False,  # 重试环境初始化不是会话内切换
            )

            # 初始化成功
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "status": "completed",
                    "message": "环境初始化完成 (排队重试成功)",
                    "progress": 100,
                    "end_time": time.time(),
                    "result": result,
                },
            )

            await self._notify_operation_progress(
                user_id,
                chat_id,
                operation_id,
            )

        except Exception as http_exc:
            from fastapi import HTTPException

            # 仍然遇到排队，返回继续重试
            if (
                isinstance(http_exc, HTTPException)
                and http_exc.status_code == 429
            ):
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "status": "queued",
                        "message": "仍然需要排队，继续等待...",
                        "error": (
                            str(http_exc.detail)
                            if hasattr(http_exc, "detail")
                            else str(http_exc)
                        ),
                    },
                )
                return

            # 其他错误，直接失败
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "status": "failed",
                    "message": f"重试初始化失败: {str(http_exc)}",
                    "error": str(http_exc),
                },
            )

    async def _retry_environment_switch(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
        config: dict,
    ):
        """重试环境切换"""
        try:
            # 停止当前任务（如果有）
            chat_state = await self.get_chat_state(user_id, chat_id)
            if chat_state.get("is_running"):
                await self.stop_task(user_id, chat_id)
                await asyncio.sleep(0.5)

            # 释放当前资源
            # 设备切换时先清理设备信息，再释放物理资源
            equipment_info = await self.get_equipment_info(user_id, chat_id)
            if equipment_info:
                logger.info(
                    f"重试切换-删除旧设备信息: 用户 {user_id}, 对话 {chat_id}, "
                    f"类型: {equipment_info.get('equipment_type', 'unknown')}",
                )
                await self.delete_equipment(user_id, chat_id)
                # 额外清理：确保设备信息完全从chat_state中移除
                await self.update_chat_state(
                    user_id,
                    chat_id,
                    {
                        "equipment": None,
                        "equipment_storage_status": None,
                        "equipment_info": None,
                        "sandbox_type": None,  # 清理sandbox_type避免类型混淆
                        "equipment_web_url": None,  # 清理URL信息
                    },
                )
                logger.info(
                    f"重试切换-已完全清理用户 {user_id} 对话 {chat_id} 的设备信息",
                )
            # 调用用户级别的资源释放（释放物理资源）
            await self.release_user_resources(user_id)

            # 初始化新环境
            result = await self._init_equipment_async(
                user_id,
                chat_id,
                config,
                restart_device=True,
                is_session_switch=True,  # 标识为会话内设备切换
            )

            # 切换成功
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "status": "completed",
                    "message": "环境切换完成 (排队重试成功)",
                    "progress": 100,
                    "end_time": time.time(),
                    "result": result,
                },
            )

            # 确保用户活跃会话状态正确
            await self.set_user_active_chat(user_id, chat_id)

            await self._notify_operation_progress(
                user_id,
                chat_id,
                operation_id,
            )

        except Exception as http_exc:
            from fastapi import HTTPException

            # 仍然遇到排队，返回继续重试
            if (
                isinstance(http_exc, HTTPException)
                and http_exc.status_code == 429
            ):
                await self.update_environment_operation(
                    user_id,
                    chat_id,
                    operation_id,
                    {
                        "status": "queued",
                        "message": "仍然需要排队，继续等待...",
                        "error": (
                            str(http_exc.detail)
                            if hasattr(http_exc, "detail")
                            else str(http_exc)
                        ),
                    },
                )
                return

            # 其他错误，直接失败
            await self.update_environment_operation(
                user_id,
                chat_id,
                operation_id,
                {
                    "status": "failed",
                    "message": f"重试切换失败: {str(http_exc)}",
                    "error": str(http_exc),
                },
            )

    async def _notify_operation_progress(
        self,
        user_id: str,
        chat_id: str,
        operation_id: str,
    ):
        """通知操作进度"""
        operation = await self.get_environment_operation(
            user_id,
            chat_id,
            operation_id,
        )
        if operation:
            await self.update_status(
                user_id,
                chat_id,
                {
                    "type": "ENV_OPERATION",
                    "status": operation.get("status"),
                    "message": operation.get("message"),
                    "operation_id": operation_id,
                    "operation_type": operation.get("operation_type"),
                    "progress": operation.get("progress"),
                    "data": operation,
                },
            )

    async def _init_equipment_async(
        self,
        user_id: str,
        chat_id: str,
        config: dict,
        restart_device: bool = False,
        is_session_switch: bool = False,  # 标识是否为会话内设备切换
    ):
        """异步设备初始化函数"""
        sandbox_type = config.get("sandbox_type")
        task_id = str(uuid.uuid4())
        static_url = config.get("static_url", "")

        print(
            f"异步启动中: {chat_id}-{sandbox_type}-{restart_device}\\n",
            flush=True,
        )
        logger.info(
            f"异步启动中: {chat_id}-{sandbox_type}-{restart_device}\\n",
        )

        chat_state = await self.get_chat_state(user_id, chat_id)

        # 检查是否已有设备且不需要重启
        if chat_state.get("equipment") and not restart_device:
            print(
                f"设备已存在: {chat_id}-{sandbox_type}，刷新认证信息",
                flush=True,
            )
            logger.info(f"设备已存在: {chat_id}-{sandbox_type}，刷新认证信息")
            # 由于设备已存储在Redis中，需要从存储信息构造返回值，同时刷新认证信息
            equipment_info = await self.get_equipment_info(user_id, chat_id)
            if equipment_info:
                if sandbox_type == "pc_wuyin":
                    # 刷新PC设备的auth_code
                    try:
                        app_stream_client = AppStreamClient()
                        new_auth_code = (
                            await app_stream_client.search_auth_code()
                        )

                        # 更新设备信息中的auth_code
                        equipment_info["instance_manager_info"][
                            "auth_code"
                        ] = new_auth_code

                        # 重新存储更新后的设备信息
                        info_key = (
                            f"{self._equipment_key(user_id, chat_id)}_info"
                        )
                        await self.redis_client.setex(
                            info_key,
                            self.EQUIPMENT_TTL,
                            json.dumps(equipment_info, default=str),
                        )

                        logger.info(
                            f"_init_equipment_async已刷新PC设备的auth_code: "
                            f"{new_auth_code[:20]}...",
                        )

                        return {
                            "task_id": task_id,
                            "equipment_web_url": f"{static_url}"
                            f"equipment_computer.html",
                            "equipment_web_sdk_info": {
                                "auth_code": new_auth_code,
                                "desktop_id": equipment_info[
                                    "instance_manager_info"
                                ]["desktop_id"],
                                "static_url": static_url,
                            },
                        }
                    except Exception as e:
                        logger.error(
                            f"_init_equipment_async刷新PC设备auth_code失败: {e}",
                        )
                        # 如果刷新失败，使用旧的auth_code（可能会失败，但至少保持向后兼容）
                        return {
                            "task_id": task_id,
                            "equipment_web_url": f"{static_url}"
                            f"equipment_computer.html",
                            "equipment_web_sdk_info": {
                                "auth_code": equipment_info[
                                    "instance_manager_info"
                                ]["auth_code"],
                                "desktop_id": equipment_info[
                                    "instance_manager_info"
                                ]["desktop_id"],
                                "static_url": static_url,
                            },
                        }

                elif sandbox_type == "phone_wuyin":
                    return {
                        "task_id": task_id,
                        "equipment_web_url": f"{static_url}"
                        "equipment_phone.html",
                        "equipment_web_sdk_info": {
                            "ticket": equipment_info["instance_manager_info"][
                                "ticket"
                            ],
                            "person_app_id": equipment_info[
                                "instance_manager_info"
                            ]["person_app_id"],
                            "app_instance_id": equipment_info[
                                "instance_manager_info"
                            ]["instance_id"],
                            "static_url": static_url,
                        },
                    }

        print(f"设备不存在或需要重启，初始化设备: {chat_id}-{sandbox_type}")
        logger.info(
            f"设备不存在或需要重启，初始化设备: {chat_id}-{sandbox_type}",
        )
        # 初始化PC设备
        if sandbox_type == "pc_wuyin":
            # 修改为用户级别的资源分配
            logger.info(
                f"[_init_equipment_async] 开始为用户 {user_id} 分配PC资源",
            )
            desktop_id, status = await self.pc_allocator.allocate_async(
                user_id,  # 使用user_id而不是chat_id
                timeout=0,
            )

            logger.info(f"启动desktop_id: {desktop_id}, status: {status}")
            logger.info(
                f"[_init_equipment_async] PC资源分配结果: "
                f"desktop_id={desktop_id}, status={status}",
            )

            # 处理资源耗尽情况（通常是因为没有配置资源）
            if status == AllocationStatus.RESOURCE_EXHAUSTED:
                logger.error(
                    f"PC资源耗尽: desktop_ids配置为空或无可用资源 "
                    f"(配置的desktop_ids: {self.desktop_ids})",
                )
                raise HTTPException(
                    503,
                    detail={
                        "message": "No PC resources configured or all "
                        "resources exhausted",
                        "type": "resource_exhausted",
                        "configured_desktop_ids": (
                            len(self.desktop_ids) if self.desktop_ids else 0
                        ),
                        "suggestion": "请检查环境变量 DESKTOP_IDS 是否正确配置",
                    },
                )

            # 处理资源排队情况
            if status == AllocationStatus.WAIT_TIMEOUT:
                logger.info("资源排队超时")
                position = (
                    await self.pc_allocator.get_chat_wait_position_async(
                        user_id,
                    )
                )[
                    0
                ]  # 使用user_id
                total_waiting = (
                    await self.pc_allocator.get_queue_info_async()
                )["total_waiting"]
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
                logger.error(
                    f"设备分配失败: status={status}, 可能原因: 资源耗尽或其他错误",
                )
                if status == AllocationStatus.RESOURCE_EXHAUSTED:
                    error_message = (
                        f"Resource exhausted - configured desktop_ids: "
                        f"{len(self.desktop_ids) if self.desktop_ids else 0}"
                    )
                else:
                    error_message = f"Unexpected allocation status: {status}"
                raise HTTPException(
                    503,
                    detail={
                        "message": "Failed to allocate PC resource",
                        "allocation_status": str(status),
                        "error_detail": error_message,
                    },
                )

            # 创建云电脑实例
            try:
                logger.info("创建云电脑实例")
                equipment = await asyncio.to_thread(
                    CloudComputer,
                    desktop_id=desktop_id,
                )
                await equipment.initialize()
            except Exception as e:
                print(f"CloudComputer初始化失败: {e}，释放资源 {desktop_id}")
                logger.error(
                    f"CloudComputer初始化失败: {e}，释放资源 {desktop_id}",
                )
                await self.pc_allocator.release_async(desktop_id)
                raise HTTPException(
                    503,
                    f"Failed to initialize PC resource: {str(e)}",
                )

            # 只有在需要重启时才重启设备
            time_reset = time.time()
            if restart_device:
                # 检查是否需要重置镜像：只有在环境初始化或设备切换时才重置，同一会话重新激活时跳过
                should_reset_image = (
                    not is_session_switch
                    and os.environ.get("EQUIP_RESET", 1) == "1"
                )

                if should_reset_image:
                    logger.info("查询设备状态")
                    await self._wait_for_pc_ready(
                        equipment,
                        desktop_id,
                        stability_check_duration=2,
                    )
                    # 重置实例镜像
                    print(f"Equipment reset for user {chat_id}")
                    logger.info(f"Equipment reset for user {chat_id}")
                    e_client = equipment.instance_manager.ecd_client
                    method = e_client.rebuild_equipment_image
                    status = await method(
                        desktop_id,
                        os.environ.get("ECD_IMAGE_ID"),
                    )
                    if status != 200:
                        raise HTTPException(
                            503,
                            "Failed to reset computer resource",
                        )
                else:
                    logger.info(
                        f"跳过镜像重置: 同一会话重新激活或EQUIP_RESET未启用 "
                        f"(is_session_switch={is_session_switch})",
                    )

                # 等待PC就绪
                await self._wait_for_pc_ready(
                    equipment,
                    desktop_id,
                    stability_check_duration=2,
                )

            print(
                "Total reset and setup time: "
                f"{time.time() - time_reset:.1f}s",
            )
            logger.info(
                "Total reset and setup time: "
                f"{time.time() - time_reset:.1f}s",
            )

            # 存储设备到Redis
            await self.store_equipment(user_id, chat_id, equipment)

            # 更新对话状态
            await self.update_chat_state(
                user_id,
                chat_id,
                {
                    "task_id": task_id,
                    "sandbox_type": sandbox_type,
                    "equipment_web_url": f"{static_url}"
                    "equipment_computer.html",
                },
            )

            return {
                "task_id": task_id,
                "equipment_web_url": f"{static_url}equipment_computer.html",
                "equipment_web_sdk_info": {
                    "auth_code": equipment.instance_manager.auth_code,
                    "desktop_id": desktop_id,
                    "static_url": static_url,
                },
            }

        # 初始化手机设备
        elif sandbox_type == "phone_wuyin":
            # 修改为用户级别的资源分配
            instance_id, status = await self.phone_allocator.allocate_async(
                user_id,  # 使用user_id而不是chat_id
                timeout=0,
            )

            print(f"启动 instance_id: {instance_id}, status: {status}")
            logger.info(f"启动 instance_id: {instance_id}, status: {status}")

            # 处理资源耗尽情况（通常是因为没有配置资源）
            if status == AllocationStatus.RESOURCE_EXHAUSTED:
                logger.error(
                    f"手机资源耗尽: phone_instance_ids配置为空或无可用资源 "
                    f"(配置的phone_instance_ids: {self.phone_instance_ids})",
                )
                raise HTTPException(
                    503,
                    detail={
                        "message": "No phone resources configured or all "
                        "resources exhausted",
                        "type": "resource_exhausted",
                        "configured_phone_instance_ids": (
                            len(self.phone_instance_ids)
                            if self.phone_instance_ids
                            else 0
                        ),
                        "suggestion": "请检查环境变量 PHONE_INSTANCE_IDS 是否正确配置",
                    },
                )

            # 处理资源排队情况
            if status == AllocationStatus.WAIT_TIMEOUT:
                position = (
                    await self.phone_allocator.get_chat_wait_position_async(
                        user_id,  # 使用user_id
                    )
                )[0]
                total_waiting = (
                    await self.phone_allocator.get_queue_info_async()
                )["total_waiting"]
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": "All phone resources are currently in use",
                        "queue_position": position + 1,
                        "total_waiting": total_waiting,
                        "type": "queued",
                    },
                )

            if not (
                status == AllocationStatus.SUCCESS
                or status == AllocationStatus.CHAT_ALREADY_ALLOCATED
            ):
                logger.error(
                    f"手机设备分配失败: status={status}, 可能原因: "
                    f"资源耗尽或其他错误",
                )
                if status == AllocationStatus.RESOURCE_EXHAUSTED:
                    phone_count = (
                        len(self.phone_instance_ids)
                        if self.phone_instance_ids
                        else 0
                    )
                    error_message = (
                        f"Resource exhausted - configured "
                        f"phone_instance_ids: "
                        f"{phone_count}"
                    )
                else:
                    error_message = f"Unexpected allocation status: {status}"
                raise HTTPException(
                    503,
                    detail={
                        "message": "Failed to allocate phone resource",
                        "allocation_status": str(status),
                        "error_detail": error_message,
                    },
                )

            # 创建云手机设备对象 - 异步初始化
            try:
                equipment = await asyncio.to_thread(
                    CloudPhone,
                    instance_id=instance_id,
                )
                await equipment.initialize()
            except Exception as e:
                print(f"CloudPhone初始化失败: {e}，释放资源 {instance_id}")
                await self.phone_allocator.release_async(instance_id)
                raise HTTPException(
                    503,
                    f"Failed to initialize phone resource: {str(e)}",
                )

            time_reset = time.time()
            if restart_device:
                # 检查是否需要重置镜像：只有在环境初始化或设备切换时才重置，同一会话重新激活时跳过
                should_reset_image = (
                    not is_session_switch
                    and os.environ.get("EQUIP_RESET", 1) == "1"
                )

                if should_reset_image:
                    await self._wait_for_phone_ready(equipment, instance_id)
                    # 重置实例镜像
                    print(f"Equipment reset for user {chat_id}")
                    logger.info(f"Equipment reset for user {chat_id}")
                    e_client = equipment.instance_manager.eds_client
                    method = e_client.reset_equipment
                    status = await method(instance_id)
                    if status != 200:
                        raise HTTPException(
                            503,
                            "Failed to reset phone resource",
                        )
                else:
                    logger.info(
                        "跳过手机镜像重置: 同一会话重新激活或EQUIP_RESET未启用"
                        f" (is_session_switch={is_session_switch})",
                    )

                # 等待设备就绪 - 异步轮询
                await self._wait_for_phone_ready(equipment, instance_id)
            print(f"启动time_reset: {time.time() - time_reset}")

            # 存储设备到Redis
            await self.store_equipment(user_id, chat_id, equipment)

            # 更新对话状态
            await self.update_chat_state(
                user_id,
                chat_id,
                {
                    "task_id": task_id,
                    "sandbox_type": sandbox_type,
                    "equipment_web_url": f"{static_url}equipment_phone.html",
                },
            )

            e_in_m = equipment.instance_manager
            return {
                "task_id": task_id,
                "equipment_web_url": f"{static_url}equipment_phone.html",
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
            # 这里不存储设备到Redis，因为e2b设备结构不同
            await self.update_chat_state(
                user_id,
                chat_id,
                {
                    "equipment": "e2b_desktop",  # 标记为e2b设备
                    "sandbox": "e2b_device",
                    "task_id": task_id,
                    "sandbox_type": sandbox_type,
                },
            )

            return {
                "task_id": task_id,
                "sandbox_url": (
                    equipment.device.stream.get_url()
                    if equipment.device
                    else None
                ),
            }

    async def _wait_for_pc_ready(
        self,
        equipment,
        desktop_id: str,
        max_wait_time: int = 300,
        stability_check_duration: int = 10,
    ):
        """异步等待PC设备就绪，增加稳定性检查"""
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
                        print(
                            f"PC {desktop_id} status: running, "
                            "starting stability check...",
                        )

                    # 检查设备是否已稳定运行足够长时间
                    stable_duration = time.time() - stable_start_time
                    if stable_duration >= stability_check_duration:
                        print(
                            f"✓ PC {desktop_id} is stable and ready"
                            f" (stable for {stable_duration:.1f}s)",
                        )
                        break
                    else:
                        print(
                            f"PC {desktop_id} stability check: "
                            f"{stable_duration:.1f}"
                            f"s/{stability_check_duration}s",
                        )
                else:
                    # 状态不是运行中，重置稳定性检查
                    if stable_start_time is not None:
                        print(
                            f"PC {desktop_id} status changed, "
                            "resetting stability check",
                        )
                        stable_start_time = None
                    current_status = (
                        pc_info[0].desktop_status.lower()
                        if pc_info
                        else "unknown"
                    )
                    print(
                        f"PC {desktop_id} status: "
                        f"{current_status}, waiting...",
                    )

                # 检查是否超时
                if time.time() - start_time > max_wait_time:
                    raise TimeoutError(
                        f"PC {desktop_id} failed to become ready"
                        f" within {max_wait_time} seconds",
                    )

            except Exception as e:
                print(f"Error checking PC status for {desktop_id}: {e}")
                # 出现异常时重置稳定性检查
                stable_start_time = None

            await asyncio.sleep(3)  # 减少检查间隔，更精确的监控

    async def _wait_for_phone_ready(
        self,
        equipment,
        instance_id: str,
        max_wait_time: int = 300,
    ):
        """异步等待手机设备就绪"""
        start_time = time.time()
        while True:
            try:
                # 将同步的状态检查操作放到线程池中执行
                total_count, next_token, devices_info = (
                    await asyncio.to_thread(
                        equipment.instance_manager.eds_client.list_instance,
                        instance_ids=[instance_id],
                    )
                )

                if (
                    devices_info
                    and devices_info[0].android_instance_status.lower()
                    == "running"
                ):
                    print(f"Phone {instance_id} is now ready")
                    break

                # 检查是否超时
                if time.time() - start_time > max_wait_time:
                    raise TimeoutError(
                        f"Phone {instance_id} failed to become ready "
                        f"within {max_wait_time} seconds",
                    )

            except Exception as e:
                print(f"Error checking phone status for {instance_id}: {e}")

            await asyncio.sleep(5)

    # === 兼容属性和方法 ===
    @property
    def global_lock(self):
        """全局锁（兼容原有接口）"""
        # Redis本身提供了原子操作，这里返回一个空的异步上下文管理器
        return asyncio.Lock()


# 全局Redis状态管理器实例
redis_state_manager = None


async def get_redis_state_manager() -> RedisStateManager:
    """获取Redis状态管理器实例"""
    global redis_state_manager
    if redis_state_manager is None:
        redis_state_manager = RedisStateManager()
        await redis_state_manager.initialize()
    return redis_state_manager


async def cleanup_redis_state_manager():
    """清理Redis状态管理器"""
    global redis_state_manager
    if redis_state_manager:
        await redis_state_manager.close()
        redis_state_manager = None
