# -*- coding: utf-8 -*-
import json
import uuid
from typing import Any, Dict, List, Optional

import redis
from pydantic import Field, SerializeAsAny

from agentscope_bricks.base.memory import Memory
from agentscope_bricks.components.memory.local_memory import (
    MemoryInput,
    MemoryOutput,
)
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage


class RedisChatStore:
    """Chat storage implemented with Redis, each message as a separate key,
    index as a list."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        user: Optional[str] = None,
        password: Optional[str] = None,
        key_prefix: str = "memory:",
        expire_seconds: Optional[int] = 60 * 60 * 24 * 5,
    ):
        """Initialize Redis chat store.

        Args:
            host: Redis server hostname. Defaults to "localhost".
            port: Redis server port. Defaults to 6379.
            db: Redis database number. Defaults to 0.
            user: Redis username for authentication. Defaults to None.
            password: Redis password for authentication. Defaults to None.
            key_prefix: Prefix for all Redis keys. Defaults to "memory:".
            expire_seconds: TTL for keys in seconds. Defaults to 5 days.
        """
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            username=user,
            password=password,
            decode_responses=True,
        )
        self.key_prefix = key_prefix
        self.expire_seconds = expire_seconds

    def _get_index_key(self, run_id: str) -> str:
        """Get the Redis key for the message index.

        Args:
            run_id: The run ID for the conversation.

        Returns:
            The Redis key for storing the message index.
        """
        return f"{self.key_prefix}{run_id}:index"

    def _get_msg_key(self, run_id: str, msg_id: str) -> str:
        """Get the Redis key for a specific message.

        Args:
            run_id: The run ID for the conversation.
            msg_id: The unique message ID.

        Returns:
            The Redis key for storing the message.
        """
        return f"{self.key_prefix}{run_id}:{msg_id}"

    def add_message(self, run_id: str, message: OpenAIMessage) -> None:
        """Add a message to Redis, as a new key, and update index.

        Args:
            run_id: The run ID for the conversation.
            message: The PromptMessage to add.
        """
        msg_id = str(uuid.uuid4())
        msg_key = self._get_msg_key(run_id, msg_id)
        msg_json = json.dumps(
            {
                "content": message.content,
                "role": message.role,
                "name": getattr(message, "name", None),
            },
            ensure_ascii=False,
        )
        self.redis.set(msg_key, msg_json, ex=self.expire_seconds)
        index_key = self._get_index_key(run_id)
        self.redis.rpush(index_key, msg_id)
        if self.expire_seconds:
            self.redis.expire(index_key, self.expire_seconds)

    def add_messages(self, run_id: str, messages: List[OpenAIMessage]) -> None:
        """Batch add multiple messages to Redis (append, do not delete old
        messages).

        Args:
            run_id: The run ID for the conversation.
            messages: List of PromptMessage objects to add.
        """
        if not messages:
            return
        index_key = self._get_index_key(run_id)
        pipe = self.redis.pipeline()
        msg_ids = []
        for message in messages:
            msg_id = str(uuid.uuid4())
            msg_ids.append(msg_id)
            msg_key = self._get_msg_key(run_id, msg_id)
            msg_json = json.dumps(
                {
                    "content": message.content,
                    "role": message.role,
                    "name": getattr(message, "name", None),
                },
                ensure_ascii=False,
            )
            pipe.set(msg_key, msg_json, ex=self.expire_seconds)
        pipe.rpush(index_key, *msg_ids)
        if self.expire_seconds:
            pipe.expire(index_key, self.expire_seconds)
        pipe.execute()

    def get_messages(
        self,
        run_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[OpenAIMessage]:
        """Get message list from Redis, optionally limiting to the most recent
        dialogue_round messages.

        Args:
            run_id: The run ID for the conversation.
            filters: Optional filters including dialogue_round to limit
                the number of recent messages.

        Returns:
            List of PromptMessage objects from the conversation.
        """
        index_key = self._get_index_key(run_id)
        total = self.redis.llen(index_key)
        dialogue_round = None
        if filters and "dialogue_round" in filters:
            try:
                dialogue_round = int(filters["dialogue_round"]) * 2
            except Exception:
                dialogue_round = None
        if dialogue_round is not None and dialogue_round > 0:
            start = max(total - dialogue_round, 0)
            end = total - 1
            msg_ids = self.redis.lrange(index_key, start, end)
        else:
            msg_ids = self.redis.lrange(index_key, 0, -1)
        # Batch get message content
        msg_keys = [self._get_msg_key(run_id, msg_id) for msg_id in msg_ids]
        msg_jsons = self.redis.mget(msg_keys) if msg_keys else []
        result = []
        for msg_json in msg_jsons:
            if not msg_json:
                continue  # Skip expired messages
            msg_dict = json.loads(msg_json)
            result.append(
                OpenAIMessage(
                    content=msg_dict["content"],
                    role=msg_dict["role"],
                    name=msg_dict.get("name"),
                ),
            )
        return result

    def search(self, query: str, filters: Dict) -> List[OpenAIMessage]:
        """Search messages (simplified version).

        Args:
            query: Search query string.
            filters: Search filters including run_id.

        Returns:
            List of PromptMessage objects matching the query.
        """
        run_id = filters.get("run_id")
        if not run_id:
            return []
        messages = self.get_messages(run_id, filters=filters)
        return [
            msg for msg in messages if query.lower() in msg.content.lower()
        ]

    def delete_messages(self, run_id: str) -> None:
        """Delete all messages of the specified session.

        Args:
            run_id: The run ID for the conversation to delete.
        """
        index_key = self._get_index_key(run_id)
        msg_ids = self.redis.lrange(index_key, 0, -1)
        pipe = self.redis.pipeline()
        for msg_id in msg_ids:
            pipe.delete(self._get_msg_key(run_id, msg_id))
        pipe.delete(index_key)
        pipe.execute()

    def delete_message(self, run_id: str, index: int) -> None:
        """Delete the message at the specified index (remove from index and
        delete key).

        Args:
            run_id: The run ID for the conversation.
            index: The index of the message to delete.
        """
        index_key = self._get_index_key(run_id)
        msg_id = self.redis.lindex(index_key, index)
        if msg_id is None:
            return
        pipe = self.redis.pipeline()
        pipe.delete(self._get_msg_key(run_id, msg_id))
        pipe.lset(index_key, index, "__deleted__")
        pipe.lrem(index_key, 1, "__deleted__")
        pipe.execute()


class RedisMemory(Memory[MemoryInput, Any]):
    """
    Manages the chat history by redis for an agents.

    Attributes:
        max_token_limit (int): Maximum token limit for a message
        max_messages (Optional[int]): Maximum number of messages to keep in
        history.
        chat_store (Optional[SimpleChatStore]): A store of chat history.
    """

    max_token_limit: int = 2000
    max_messages: Optional[int] = None
    chat_store: SerializeAsAny[RedisChatStore] = Field(
        default_factory=RedisChatStore,
    )

    def __init__(
        self,
        chat_store: Optional[SerializeAsAny[RedisChatStore]] = None,
        **kwargs: Any,
    ):
        """Initialize RedisMemory with optional Redis chat store.

        Args:
            chat_store: Optional RedisChatStore instance. If None, creates
                a new one with the provided kwargs.
            **kwargs: Additional keyword arguments passed to RedisChatStore
                constructor if chat_store is None.
        """
        if chat_store:
            self.chat_store = chat_store
        else:
            self.chat_store = RedisChatStore(**kwargs)

    @staticmethod
    def generate_new_key() -> str:
        """Generate a new unique key.

        Returns:
            A new UUID string to use as a key.
        """
        return str(uuid.uuid4())

    async def add(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Add messages to Redis memory.

        Args:
            args: MemoryInput containing run_id and messages to add.
            **kwargs: Additional keyword arguments.

        Returns:
            MemoryOutput with success information.

        Raises:
            ValueError: If run_id or messages are not provided, or if messages
                are not PromptMessage instances.
        """
        run_id = args.run_id
        messages = args.messages
        if not run_id or not messages:
            raise ValueError("run_id and message are required")
        if isinstance(messages, str):
            messages = [OpenAIMessage(content=messages, role="user")]
        for message in messages:
            if not isinstance(message, OpenAIMessage):
                raise ValueError("message must be a PromptMessage")
            self.chat_store.add_message(run_id, message)
            self._manage_overflow(run_id)
        return MemoryOutput(infos={"success": True})

    async def search(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Search messages in Redis memory.

        Args:
            args: MemoryInput containing run_id, messages (for query), and
                filters.
            **kwargs: Additional keyword arguments.

        Returns:
            MemoryOutput with search results.

        Raises:
            ValueError: If required parameters are missing or invalid.
        """
        run_id = args.run_id
        filters = args.filters or {}
        if run_id:
            filters["run_id"] = run_id
        if not filters:
            raise ValueError("filters is required")
        if isinstance(args.messages, list) and args.messages:
            query = args.messages[-1].content
        elif isinstance(args.messages, str):
            query = args.messages
        else:
            raise ValueError("messages must be a List or str")
        if not run_id or not filters:
            raise ValueError("run_id and filters is required")
        return MemoryOutput(messages=self.chat_store.search(query, filters))

    async def get_all(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Get all messages for a run_id from Redis.

        Args:
            args: MemoryInput containing run_id.
            **kwargs: Additional keyword arguments.

        Returns:
            MemoryOutput with all messages for the run_id.

        Raises:
            ValueError: If run_id is not provided.
        """
        run_id = getattr(args, "run_id", None) or (
            args.get("run_id") if isinstance(args, dict) else None
        )
        if not run_id:
            raise ValueError("run_id is required")
        return MemoryOutput(messages=self.chat_store.get_messages(run_id))

    async def get(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Get messages for a run_id with optional filters from Redis.

        Args:
            args: MemoryInput containing run_id and optional filters.
            **kwargs: Additional keyword arguments.

        Returns:
            MemoryOutput with filtered messages for the run_id.

        Raises:
            ValueError: If run_id is not provided.
        """
        run_id = getattr(args, "run_id", None) or (
            args.get("run_id") if isinstance(args, dict) else None
        )
        filters = getattr(args, "filters", None) or (
            args.get("filters") if isinstance(args, dict) else None
        )
        if not run_id:
            raise ValueError("run_id is required")
        return MemoryOutput(
            messages=self.chat_store.get_messages(run_id, filters=filters),
        )

    async def reset(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Reset (delete all) messages for a run_id in Redis.

        Args:
            args: MemoryInput containing run_id.
            **kwargs: Additional keyword arguments.

        Returns:
            MemoryOutput with success information.

        Raises:
            ValueError: If run_id is not provided.
        """
        run_id = args.run_id
        if not run_id:
            raise ValueError("run_id is required")
        self.chat_store.delete_messages(run_id)
        return MemoryOutput(infos={"success": True})

    def _manage_overflow(self, key: str) -> None:
        """Manage the chat history overflow based on max_messages constraint.

        Args:
            key: The key to manage overflow for.
        """
        if self.max_messages is not None:
            current_messages = self.chat_store.get_messages(key)
            while len(current_messages) > self.max_messages:
                self.chat_store.delete_message(key, 0)

    # TODO： add token and length limit
