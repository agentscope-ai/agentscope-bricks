# -*- coding: utf-8 -*-
import copy
import uuid
from typing import Any, Dict, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field, SerializeAsAny

from agentscope_bricks.base.memory import Memory, MemoryOperation
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage

MessageT = TypeVar("MessageT", bound=OpenAIMessage, contravariant=True)


class MemoryInput(BaseModel):
    operation_type: MemoryOperation
    run_id: Optional[str] = Field(
        description="Run id of the memory",
        default=str(uuid.uuid4()),
    )
    messages: Optional[Union[List[OpenAIMessage], str]] = Field(
        default=None,
        description="Messages to be used in the memory operation",
    )
    filters: Optional[Dict[str, Any]] = Field(
        description="Associated filters for the messages, such as run_id, "
        "agent_id, etc.",
        default=None,
    )


class MemoryOutput(BaseModel):
    infos: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Information about the memory operation result",
    )
    messages: Optional[List[OpenAIMessage]] = Field(
        default=[],
        description="Messages to be recalled",
    )
    summarization: Optional[str] = Field(
        default=None,
        description="Summarization of the messages",
    )


class SimpleChatStore(BaseModel):
    """Simple chat store. Async methods provide same functionality as sync
    methods in this class."""

    store: Dict[str, List[OpenAIMessage]] = Field(default_factory=dict)

    def set_messages(self, key: str, messages: List[MessageT]) -> None:
        """Set messages for a key.

        Args:
            key: The key to store messages under.
            messages: List of messages to store.
        """
        self.store[key] = copy.deepcopy(messages)

    def get_messages(
        self,
        key: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[MessageT]:
        """Get messages for a key.

        Args:
            key: The key to retrieve messages for.
            filters: Optional filters to apply (not used in this
                 implementation).

        Returns:
            List of messages associated with the key, or empty list if key
            doesn't exist.
        """
        return self.store.get(key, [])

    def add_message(
        self,
        key: str,
        message: MessageT,
        idx: Optional[int] = None,
    ) -> None:
        """Add a message for a key.

        Args:
            key: The key to add the message to.
            message: The message to add.
            idx: Optional index to insert the message at. If None, appends
                to the end.
        """
        message_buffer = copy.deepcopy(message)
        if idx is None:
            self.store.setdefault(key, []).append(message_buffer)
        else:
            self.store.setdefault(key, []).insert(idx, message_buffer)

    def add_messages(
        self,
        key: str,
        messages: List[MessageT],
        idx: Optional[int] = None,
    ) -> None:
        """Add multiple messages for a key.

        Args:
            key: The key to add the messages to.
            messages: List of messages to add.
            idx: Optional index to insert the messages at. If None, appends
                to the end.
        """
        if not messages:
            return

        message_buffers = [copy.deepcopy(message) for message in messages]
        if idx is None:
            self.store.setdefault(key, []).extend(message_buffers)
        else:
            for i, message_buffer in enumerate(message_buffers):
                self.store.setdefault(key, []).insert(idx + i, message_buffer)

    def delete_messages(self, key: str) -> Optional[List[MessageT]]:
        """Delete messages for a key.

        Args:
            key: The key to delete messages for.

        Returns:
            The deleted messages if key existed, None otherwise.
        """
        if key not in self.store:
            return None
        return self.store.pop(key)

    def delete_message(self, key: str, idx: int) -> Optional[MessageT]:
        """Delete specific message for a key.

        Args:
            key: The key to delete the message from.
            idx: The index of the message to delete.

        Returns:
            The deleted message if it existed, None otherwise.
        """
        if key not in self.store:
            return None
        if idx >= len(self.store[key]):
            return None
        return self.store[key].pop(idx)

    def delete_last_message(self, key: str) -> Optional[MessageT]:
        """Delete last message for a key.

        Args:
            key: The key to delete the last message from.

        Returns:
            The deleted message if key existed and had messages,
            None otherwise.
        """
        if key not in self.store:
            return None
        return self.store[key].pop()

    def get_keys(self) -> List[str]:
        """Get all keys.

        Returns:
            List of all keys in the store.
        """
        return list(self.store.keys())

    def search(self, query: str, filters: Any) -> List[MessageT]:
        """Simple Chat Store not implement the search method.

        Args:
            query: Search query string.
            filters: Search filters.

        Returns:
            Empty list as search is not implemented.
        """
        return []

    # TODO add persist method


class LocalMemory(Memory[MemoryInput, Any]):
    """
    Manages the chat history by memory.

    Attributes:
        max_token_limit (int): Maximum token limit for a message
        max_messages (Optional[int]): Maximum number of messages to keep in
        history.
        chat_store (Optional[SimpleChatStore]): A store of chat history.
    """

    max_token_limit: int = 2000
    max_messages: Optional[int] = None
    chat_store: SerializeAsAny[SimpleChatStore] = Field(
        default_factory=SimpleChatStore,
    )

    def __init__(
        self,
        chat_store: Optional[SerializeAsAny[SimpleChatStore]] = None,
        **kwargs: Any,
    ):
        """Initialize LocalMemory with optional chat store.

        Args:
            chat_store: Optional SimpleChatStore instance. If None, creates
                a new one.
            **kwargs: Additional keyword arguments passed to parent class.
        """
        super().__init__(**kwargs)
        if chat_store:
            self.chat_store = chat_store
        else:
            self.chat_store = SimpleChatStore()

    @staticmethod
    def generate_new_key() -> str:
        """Generate a new unique key.

        Returns:
            A new UUID string to use as a key.
        """
        return str(uuid.uuid4())

    async def add(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Add messages to memory.

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
        """Search messages in memory.

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
        filters = args.filters
        if not filters:
            raise ValueError("filters is required")

        if run_id:
            filters[run_id] = run_id

        if isinstance(args.messages, List):
            query = args.messages[-1].content
        elif isinstance(args.messages, str):
            query = args.messages
        else:
            raise ValueError("messages must be a List or str")
        if not run_id or not filters:
            raise ValueError("run_id and filters is required")
        return MemoryOutput(messages=self.chat_store.search(query, filters))

    async def get_all(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Get all messages for a run_id.

        Args:
            args: MemoryInput containing run_id.
            **kwargs: Additional keyword arguments.

        Returns:
            MemoryOutput with all messages for the run_id.

        Raises:
            ValueError: If run_id is not provided.
        """
        run_id = args.get("run_id")
        if not run_id:
            raise ValueError("run_id is required")
        return MemoryOutput(messages=self.chat_store.get_messages(run_id))

    async def get(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Get messages for a run_id with optional filters.

        Args:
            args: MemoryInput containing run_id and optional filters.
            **kwargs: Additional keyword arguments.

        Returns:
            MemoryOutput with filtered messages for the run_id.

        Raises:
            ValueError: If run_id is not provided.
        """
        run_id = args.get("run_id")
        if not run_id:
            raise ValueError("run_id is required")
        return MemoryOutput(
            messages=self.chat_store.get_messages(
                run_id,
                filters=args.filters,
            ),
        )

    async def reset(self, args: MemoryInput, **kwargs: Any) -> MemoryOutput:
        """Reset (delete all) messages for a run_id.

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
