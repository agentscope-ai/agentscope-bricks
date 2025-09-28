# -*- coding: utf-8 -*-
import asyncio
from concurrent.futures import Executor, ThreadPoolExecutor


class AsyncTaskExecutor:

    def __init__(self, thread_pool_executor: Executor = None):
        self.loop = asyncio.new_event_loop()

        if not thread_pool_executor:
            thread_pool_executor = ThreadPoolExecutor(max_workers=1)

        thread_pool_executor.submit(self.loop.run_forever)

    def __del__(self):
        self.stop()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def submit(self, coro, *args, **kwargs):
        future = asyncio.run_coroutine_threadsafe(
            coro(*args, **kwargs),
            self.loop,
        )
        return future

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
