# -*- coding: utf-8 -*-
import asyncio
from typing import AsyncGenerator, Any


async def batch_run_tasks(
    coro_list: list,
    batch_size: int,
) -> AsyncGenerator[tuple[int, Any], None]:
    """
    Execute coroutines in batches and yield results as they complete.

    Args:
        coro_list: List of coroutines to execute. Each coroutine should
                  return a tuple of (index: int, result: Any)
        batch_size: Number of tasks to execute in each batch

    Yields:
        tuple[int, Any]: Tuple containing (index, result) from each coroutine
    """
    if not coro_list:
        return

    # Process coroutines in batches
    for i in range(0, len(coro_list), batch_size):
        # Get the current batch of coroutines
        batch_coros = coro_list[i : i + batch_size]

        # Create tasks for the current batch only
        batch_tasks = [asyncio.create_task(coro) for coro in batch_coros]
        pending = set(batch_tasks)

        # Wait for all tasks in current batch to complete and yield results
        # as they finish
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                index, result = await task
                yield index, result


async def main():
    """Main function with representative unit test for batch_run_tasks."""
    print("=" * 50)
    print("Running batch_run_tasks unit test")
    print("=" * 50)

    # Representative test: Batch execution with timing verification
    print("\nTesting batch execution functionality...")

    execution_times = {}

    async def mock_task(index: int) -> tuple[int, str]:
        """Mock task that simulates image generation work."""
        start_time = asyncio.get_event_loop().time()
        execution_times[f"start_{index}"] = start_time
        await asyncio.sleep(0.1)  # Simulate work time
        end_time = asyncio.get_event_loop().time()
        execution_times[f"end_{index}"] = end_time
        return index, f"generated_image_{index}"

    # Test: 5 tasks with batch_size=2 should execute as [0,1], [2,3], [4]
    coro_list = [mock_task(i) for i in range(5)]
    batch_size = 2

    start_time = asyncio.get_event_loop().time()
    results = []

    async for index, result in batch_run_tasks(coro_list, batch_size):
        completion_time = asyncio.get_event_loop().time() - start_time
        results.append((index, result))
        print(f"  Task {index} completed at {completion_time:.3f}s: {result}")

    # Verify all tasks completed
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"
    received_indices = {r[0] for r in results}
    expected_indices = {0, 1, 2, 3, 4}
    assert received_indices == expected_indices, "Missing task indices"

    # Verify batch execution timing: each batch should take ~0.1s
    total_time = asyncio.get_event_loop().time() - start_time
    expected_min_time = 0.3  # 3 batches * 0.1s each
    assert (
        total_time >= expected_min_time
    ), f"Execution too fast: {total_time:.3f}s"

    print(f"\n✓ Test passed! Total execution time: {total_time:.3f}s")
    print("✓ All 5 tasks completed with correct batch execution")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
