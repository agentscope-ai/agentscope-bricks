# -*- coding: utf-8 -*-
from abc import abstractmethod
from enum import Enum
from typing import Any, Generic

from .__base import BaseComponent
from .component import ComponentArgsT, ComponentReturnT
from agentscope_bricks.utils.tracing_utils.wrapper import trace


class MemoryOperation(str, Enum):
    """Enumeration of memory operations."""

    ADD = "add"
    GET = "get"
    GET_ALL = "get_all"
    SEARCH = "search"
    RESET = "reset"


class Memory(BaseComponent, Generic[ComponentArgsT, ComponentReturnT]):
    """Base class for memory zh with different operations."""

    @trace(trace_type="MEMORY")
    async def arun(
        self,
        args: ComponentArgsT,
        **kwargs: Any,
    ) -> ComponentReturnT:
        """Execute memory operation based on the operation type.

        Args:
            args (ComponentArgsT): Arguments containing operation_type and
            other parameters.
            **kwargs: Additional keyword arguments.

        Returns:
            ComponentReturnT: Result of the memory operation.

        Raises:
            ValueError: If operation_type is missing or invalid.
        """
        if hasattr(args, "operation_type"):
            operation_type = args.operation_type
        else:
            raise ValueError("operation_type is required")
        if operation_type == MemoryOperation.ADD:
            return await self.add(args, **kwargs)
        elif operation_type == MemoryOperation.GET_ALL:
            return await self.get_all(args, **kwargs)
        elif operation_type == MemoryOperation.SEARCH:
            return await self.search(args, **kwargs)
        elif operation_type == MemoryOperation.RESET:
            return await self.reset(args, **kwargs)
        else:
            raise ValueError(f"Invalid operation type: {operation_type}")

    @abstractmethod
    async def add(
        self,
        args: ComponentArgsT,
        **kwargs: Any,
    ) -> ComponentReturnT:
        """Create a new memory. store the messages to memory.

        Args:
            args (ComponentArgsT): Arguments for adding memory.
            **kwargs: Additional keyword arguments.

        Returns:
            ComponentReturnT: Result of the add operation.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("add method must be implemented")

    @abstractmethod
    async def get(
        self,
        args: ComponentArgsT,
        **kwargs: Any,
    ) -> ComponentReturnT:
        """List memories by filters.

        Args:
            args (ComponentArgsT): Arguments for getting specific memories.
            **kwargs: Additional keyword arguments.

        Returns:
            ComponentReturnT: Filtered memories.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("add method must be implemented")

    @abstractmethod
    async def get_all(
        self,
        args: ComponentArgsT,
        **kwargs: Any,
    ) -> ComponentReturnT:
        """List all memories.

        Args:
            args (ComponentArgsT): Arguments for getting all memories.
            **kwargs: Additional keyword arguments.

        Returns:
            ComponentReturnT: All stored memories.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("get_all method must be implemented")

    @abstractmethod
    async def search(
        self,
        args: ComponentArgsT,
        **kwargs: Any,
    ) -> ComponentReturnT:
        """Search for memories with query string and filters.

        Args:
            args (ComponentArgsT): Arguments containing search query and
            filters.
            **kwargs: Additional keyword arguments.

        Returns:
            ComponentReturnT: Search results matching the query and filters.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("search method must be implemented")

    @abstractmethod
    async def reset(
        self,
        args: ComponentArgsT,
        **kwargs: Any,
    ) -> ComponentReturnT:
        """Reset or  Delete all memories.

        Args:
            args (ComponentArgsT): Arguments for resetting memories.
            **kwargs: Additional keyword arguments.

        Returns:
            ComponentReturnT: Result of the reset operation.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("reset method must be implemented")
