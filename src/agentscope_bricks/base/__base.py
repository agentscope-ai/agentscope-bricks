# -*- coding: utf-8 -*-
import json
from abc import ABC
from typing import (
    Any,
    Dict,
    TypeVar,
)

from pydantic import BaseModel


class BaseComponent(ABC):
    """Base component object to capture class names. use namespace to track
    during serialize"""

    def __str__(self) -> str:
        """Return string representation of the component.

        Returns:
            str: JSON representation if model_dump_json is available,
                 or name/description dict, or default string representation.
        """
        if hasattr(self, "model_dump_json"):
            return self.model_dump_json()
        elif hasattr(self, "name") and hasattr(self, "description"):
            info = {
                "name": self.name,
                "description": self.description,
            }
            return json.dumps(info)
        else:
            return str(self)

    def to_dict(self, **kwargs: Any) -> Dict[str, Any]:
        """Convert component to dictionary representation.

        Args:
            **kwargs: Additional arguments passed to model_dump if available.

        Returns:
            Dict[str, Any]: Dictionary containing component data and namespace.
        """
        if kwargs:
            data = self.model_dump(**kwargs)
        else:
            data = {}
        data["namespace"] = self.get_namespace()
        return data

    def to_json(self, **kwargs: Any) -> str:
        """Convert component to JSON string representation.

        Args:
            **kwargs: Additional arguments passed to to_dict.

        Returns:
            str: JSON string representation of the component.
        """
        data = self.to_dict(**kwargs)
        return json.dumps(data)

    @classmethod
    def get_namespace(cls) -> list[str]:
        """Get the namespace of the object.

        For example, if the class is
        `agentscope_bricks.component.internal.dashscopesearch`, then the
        namespace is ["agentscope_bricks", "component", "dashscopesearch"]

        Returns:
            list[str]: List of namespace zh derived from module path.
        """
        return cls.__module__.split(".")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> Any:
        """Get Pydantic core schema for the component.

        Args:
            source_type: The source type for schema generation.
            handler: The schema handler.

        Returns:
            Any: Pydantic core schema allowing any type.
        """
        from pydantic_core import core_schema

        return core_schema.any_schema()
