# -*- coding: utf-8 -*-
from typing import AsyncIterable, AsyncIterator, Tuple, TypeVar

T = TypeVar("T")


async def aenumerate(
    asequence: AsyncIterable[T],
    start: int = 0,
) -> AsyncIterator[Tuple[int, T]]:
    """Asynchronously enumerate an async iterator from a given start value.

    Args:
        asequence (AsyncIterable[T]): The async iterable to enumerate.
        start (int): The starting value for enumeration. Defaults to 0.

    Yields:
        Tuple[int, T]: A tuple containing the index and the item from the
        async iterable.
    """
    n = start
    async for elem in asequence:
        yield n, elem
        n += 1
