# -*- coding: utf-8 -*-
# pylint:disable=no-untyped-def

import asyncio
from typing import Any
from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component


class SearchInput(BaseModel):
    """
    Search Input.
    """

    query: str = Field(
        ...,
        title="Query",
        description="Search Query used for query",
    )


class SearchOutput(BaseModel):
    """
    Search Output.
    """

    results: list[str]


class SearchComponent(Component[SearchInput, SearchOutput]):
    """
    Search Component.
    """

    name = "Search Component"
    description = "Search Component For Example"

    async def arun(self, args: SearchInput, **kwargs: Any) -> SearchOutput:
        """
        Run asynchronously.
        """
        if not isinstance(args, SearchInput):
            raise TypeError(
                "Argument must be an instance of SearchInput or its subclass",
            )

        await asyncio.sleep(1)  # 模拟异步操作
        return SearchOutput(results=["result1", "result2"])


if __name__ == "__main__":
    search_component = SearchComponent()
    search_input = SearchInput(query="query")

    # 异步运行
    async def main() -> None:
        search_output = await search_component.arun(search_input)
        print(search_output)
        print(search_component.function_schema.model_dump())

    asyncio.run(main())
