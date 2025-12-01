# -*- coding: utf-8 -*-
import os
from typing import List, Dict, Any, Optional

import aiohttp
from pydantic import BaseModel, Field, model_validator

from agentscope_bricks.base.component import Component

# ENV-PRE
MEMORY_SERVICE_ENDPOINT = os.getenv("MEMORY_SERVICE_ENDPOINT", "https://dashscope.aliyuncs.com/api/v2/apps/memory")
ADD_MEMORY_URL = f'{MEMORY_SERVICE_ENDPOINT}/add'
SEARCH_MEMORY_URL = f'{MEMORY_SERVICE_ENDPOINT}/memory_nodes/search'
LIST_MEMORY_URL = f'{MEMORY_SERVICE_ENDPOINT}/memory_nodes'
DELETE_MEMORY_URL_PATTERN = f'{MEMORY_SERVICE_ENDPOINT}/memory_nodes/{{memory_node_id}}'
CREATE_PROFILE_SCHEMA_URL = f"{MEMORY_SERVICE_ENDPOINT}/profile_schemas"
GET_USER_PROFILE_URL_PATTERN = f"{MEMORY_SERVICE_ENDPOINT}/profile_schemas/{{schema_id}}/user_profile"


class Message(BaseModel):
    role: str
    content: Any


class AddMemoryInput(BaseModel):
    user_id: str = Field(..., description="end user id")
    messages: List[Message] = Field(..., description="conversation messages")
    timestamp: int = Field(..., description="timestamp of the memory")
    meta_data: Optional[Dict[str, Any]] = Field(
        None,
        description="metadata including location and media description",
    )

    class Config:
        extra = "allow"  # Allow extra fields


class MemoryNode(BaseModel):
    memory_node_id: Optional[str] = None
    content: str


class AddMemoryOutput(BaseModel):
    memory_nodes: List[MemoryNode] = Field(
        ...,
        description="generated memory nodes",
    )


class SearchFilters(BaseModel):
    tags: Optional[List[str]] = Field(None, description="filter by tags")


class SearchMemoryInput(BaseModel):
    user_id: str = Field(..., description="end user id")
    messages: List[Message] = Field(..., description="conversation messages")
    top_k: Optional[int] = Field(
        100,
        description="number of results to return",
    )
    min_score: Optional[float] = Field(
        0.0,
        description="minimum score threshold",
    )

    class Config:
        extra = "allow"  # Allow extra fields


class SearchMemoryOutput(BaseModel):
    memory_nodes: List[MemoryNode] = Field(
        ...,
        description="retrieved memory nodes",
    )
    request_id: str = Field(..., description="request id")


class ListMemoryInput(BaseModel):
    user_id: str = Field(..., description="end user id")
    page_num: Optional[int] = Field(1, description="page number")
    page_size: Optional[int] = Field(
        10,
        description="number of items per page",
    )

    class Config:
        extra = "allow"  # Allow extra fields


class ListMemoryOutput(BaseModel):
    memory_nodes: List[MemoryNode] = Field(
        ...,
        description="retrieved memory nodes",
    )
    page_size: int = Field(..., description="number of items per page")
    page_num: int = Field(..., description="current page number")
    total: int = Field(..., description="total number of memory nodes")
    request_id: str = Field(..., description="request id")


class DeleteMemoryInput(BaseModel):
    user_id: str = Field(..., description="end user id")
    memory_node_id: str = Field(..., description="memory node id to delete")

    class Config:
        extra = "allow"  # Allow extra fields


class DeleteMemoryOutput(BaseModel):
    request_id: str = Field(..., description="request id")


class AddMemory(Component[AddMemoryInput, AddMemoryOutput]):
    """
    Memory Component for storing conversation history as memory nodes.
    """

    name = "add_memory"
    description = "Store conversation messages as memory nodes"

    def __init__(self) -> None:
        super().__init__()
        self.service_id = os.getenv("MODELSTUDIO_SERVICE_ID", "memory_service")
        self.add_memory_url = ADD_MEMORY_URL
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY environment variable is required",
            )

    async def _arun(
        self,
        args: AddMemoryInput,
        **kwargs: Any,
    ) -> AddMemoryOutput:
        """
        Add memory nodes

        Args:
            args: AddMemoryInput
            **kwargs: Additional parameters

        Returns:
            AddMemoryOutput: Memory output
        """
        try:
            # Build request body - all fields including extra fields will be
            # included
            payload = args.model_dump(exclude_none=True)

            # Send request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.add_memory_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "agentscope-bricks",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"Add memory failed with status "
                            f"{response.status}: {error_text}",
                        )

                    result = await response.json()
                    return AddMemoryOutput(
                        memory_nodes=[
                            MemoryNode(**node)
                            for node in result.get("memory_nodes", [])
                        ],
                    )

        except Exception as e:
            raise Exception(f"Error in AddMemory: {str(e)}")


class SearchMemory(Component[SearchMemoryInput, SearchMemoryOutput]):
    """
    Memory Component for searching relevant memories based on conversation
    context.
    """

    name = "search_memory"
    description = "Search for relevant memories based on conversation context"

    def __init__(self) -> None:
        super().__init__()
        self.service_id = os.getenv("MODELSTUDIO_SERVICE_ID", "memory_service")
        self.search_memory_url = SEARCH_MEMORY_URL
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY environment variable is required",
            )

    async def _arun(
        self,
        args: SearchMemoryInput,
        **kwargs: Any,
    ) -> SearchMemoryOutput:
        """
        Search memory nodes

        Args:
            args: SearchMemoryInput
            **kwargs: Additional parameters

        Returns:
            SearchMemoryOutput: Search output
        """
        try:
            # Build request body - all fields including extra fields will be
            # included
            payload = args.model_dump(exclude_none=True)

            # Send request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.search_memory_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "agentscope-bricks",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"Search memory failed with status "
                            f"{response.status}: {error_text}",
                        )

                    result = await response.json()
                    return SearchMemoryOutput(
                        memory_nodes=[
                            MemoryNode(**node)
                            for node in result.get("memory_nodes", [])
                        ],
                        request_id=result.get("request_id", ""),
                    )

        except Exception as e:
            raise Exception(f"Error in SearchMemory: {str(e)}")


class ListMemory(Component[ListMemoryInput, ListMemoryOutput]):
    """
    Memory Component for listing memory nodes for a user.
    """

    name = "list_memory"
    description = "List memory nodes for a user"

    def __init__(self) -> None:
        super().__init__()
        self.service_id = os.getenv("MODELSTUDIO_SERVICE_ID", "memory_service")
        self.list_memory_url = LIST_MEMORY_URL
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY environment variable is required",
            )

    async def _arun(
        self,
        args: ListMemoryInput,
        **kwargs: Any,
    ) -> ListMemoryOutput:
        """
        List memory nodes for a user

        Args:
            args: ListMemoryInput
            **kwargs: Additional parameters

        Returns:
            ListMemoryOutput: List memory output
        """
        try:
            # Build request body - all fields including extra fields will be
            # included
            payload = args.model_dump(exclude_none=True)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        self.list_memory_url,
                        params=payload,
                        json={},
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "agentscope-bricks",
                            "Authorization": f"Bearer {self.api_key}",
                        },
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"List memory failed with status "
                            f"{response.status}: {error_text}",
                        )

                    result = await response.json()
                    return ListMemoryOutput(
                        memory_nodes=[
                            MemoryNode(**node)
                            for node in result.get("memory_nodes", [])
                        ],
                        page_size=result.get("page_size", 10),
                        page_num=result.get("page_num", 1),
                        total=result.get("total", 0),
                        request_id=result.get("request_id", ""),
                    )

        except Exception as e:
            raise Exception(f"Error in ListMemory: {str(e)}")


class DeleteMemory(Component[DeleteMemoryInput, DeleteMemoryOutput]):
    """
    Memory Component for deleting a specific memory node.
    """

    name = "delete_memory"
    description = "Delete a specific memory node"

    def __init__(self) -> None:
        super().__init__()
        self.service_id = os.getenv("MODELSTUDIO_SERVICE_ID", "memory_service")
        self.delete_memory_url_pattern = DELETE_MEMORY_URL_PATTERN
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY environment variable is required",
            )

    async def _arun(
        self,
        args: DeleteMemoryInput,
        **kwargs: Any,
    ) -> DeleteMemoryOutput:
        """
        Delete a memory node

        Args:
            args: DeleteMemoryInput
            **kwargs: Additional parameters

        Returns:
            DeleteMemoryOutput: Delete memory output
        """
        try:
            # Build URL with path param and include body as per example
            url = self.delete_memory_url_pattern.format(memory_node_id=args.memory_node_id)

            async with aiohttp.ClientSession() as session:
                async with session.delete(
                        url,
                        json={},
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "agentscope-bricks",
                            "Authorization": f"Bearer {self.api_key}",
                        },
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"Delete memory failed with status "
                            f"{response.status}: {error_text}",
                        )

                    result = await response.json()
                    return DeleteMemoryOutput(
                        request_id=result.get("request_id", ""),
                    )

        except Exception as e:
            raise Exception(f"Error in DeleteMemory: {str(e)}")


class ProfileAttribute(BaseModel):
    name: str = Field(..., description='Attribute name')
    description: Optional[str] = Field(None, description='Attribute description')
    immutable: Optional[bool] = Field(False, description='Whether the attribute is immutable')
    default_value: Optional[Any] = Field(None, description='Default value for the attribute')


class CreateProfileSchemaInput(BaseModel):
    name: str = Field(..., description='Profile schema name')
    description: Optional[str] = Field(None, description='Profile schema description')
    attributes: List[ProfileAttribute] = Field(..., description='List of attribute definitions (>=1)')

    @model_validator(mode='after')
    def validate_attributes(self) -> 'CreateProfileSchemaInput':
        if not self.attributes or len(self.attributes) == 0:
            raise ValueError('attributes must contain at least one item')
        return self

    class Config:
        extra = "allow"


class CreateProfileSchemaOutput(BaseModel):
    profile_schema_id: str = Field(..., description='Created profile schema id')
    request_id: str = Field(..., description='Request id')


class CreateProfileSchema(Component[CreateProfileSchemaInput, CreateProfileSchemaOutput]):
    """
    Create a user profile schema with attribute definitions.
    """

    name = 'create_profile_schema'
    description = 'Create a profile schema with attribute definitions'

    def __init__(self):
        super().__init__()
        self.service_id = os.getenv("MODELSTUDIO_SERVICE_ID", "profile_service")
        self.create_profile_schema_url = CREATE_PROFILE_SCHEMA_URL
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable is required")

    async def _arun(
            self,
            args: CreateProfileSchemaInput,
            **kwargs: Any
    ) -> CreateProfileSchemaOutput:
        """
        Create a profile schema

        Args:
            args: CreateProfileSchemaInput
            **kwargs: Additional parameters

        Returns:
            CreateProfileSchemaOutput: Result including profile_schema_id and request_id
        """
        try:
            payload = args.model_dump(exclude_none=True)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        self.create_profile_schema_url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "agentscope-bricks",
                            "Authorization": f"Bearer {self.api_key}"
                        }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Create profile schema failed with status {response.status}: {error_text}")

                    result = await response.json()
                    return CreateProfileSchemaOutput(
                        profile_schema_id=result.get('profile_schema_id', ''),
                        request_id=result.get('request_id', '')
                    )
        except Exception as e:
            raise Exception(f"Error in CreateProfileSchema: {str(e)}")


class UserProfileAttribute(BaseModel):
    name: str = Field(..., description='Attribute name')
    id: str = Field(..., description='Attribute id')
    value: Optional[Any] = Field(None, description='Attribute value')


class UserProfile(BaseModel):
    schema_description: Optional[str] = Field(None, description='Schema description')
    schema_name: Optional[str] = Field(None, description='Schema name')
    attributes: List[UserProfileAttribute] = Field(default_factory=list, description='User attributes')


class GetUserProfileInput(BaseModel):
    schema_id: str = Field(..., description='Profile schema id')
    user_id: str = Field(..., description='End user id')


class GetUserProfileOutput(BaseModel):
    request_id: str = Field(..., description='Request id')
    profile: UserProfile = Field(..., description='User profile')


class GetUserProfile(Component[GetUserProfileInput, GetUserProfileOutput]):
    """
    Get user profile by schema id and user id.
    """

    name = 'get_user_profile'
    description = 'Get user profile by schema id and user id'

    def __init__(self):
        super().__init__()
        self.service_id = os.getenv("MODELSTUDIO_SERVICE_ID", "profile_service")
        self.get_user_profile_url_pattern = GET_USER_PROFILE_URL_PATTERN
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable is required")

    async def _arun(
            self,
            args: GetUserProfileInput,
            **kwargs: Any
    ) -> GetUserProfileOutput:
        """
        Get a user profile

        Args:
            args: GetUserProfileInput
            **kwargs: Additional parameters

        Returns:
            GetUserProfileOutput: Profile and request id
        """
        try:
            # Build URL without user_id in path; user_id will be a query parameter
            url = self.get_user_profile_url_pattern.format(schema_id=args.schema_id)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        url,
                        params={"user_id": args.user_id},
                        json={},
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "agentscope-bricks",
                            "Authorization": f"Bearer {self.api_key}"
                        }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Get user profile failed with status {response.status}: {error_text}")

                    result = await response.json()
                    profile_raw = result.get('profile', {})
                    attributes = [
                        UserProfileAttribute(
                            name=item.get('name', ''),
                            id=item.get('id', ''),
                            value=item.get('value')
                        ) for item in profile_raw.get('attributes', [])
                    ]

                    profile = UserProfile(
                        schema_description=profile_raw.get('schemaDescription'),
                        schema_name=profile_raw.get('schemaName'),
                        attributes=attributes
                    )

                    return GetUserProfileOutput(
                        request_id=result.get('requestId', ''),
                        profile=profile
                    )
        except Exception as e:
            raise Exception(f"Error in GetUserProfile: {str(e)}")
