import asyncio
import logging
from typing import Callable, Any
from tokenfinops.gateway.schemas import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)

class BatchScheduler:
    """Aggregates multiple individual chat completion queries into scheduled micro-batches.
    Particularly useful to optimize throughput for self-hosted LLM endpoints.
    """

    def __init__(self, batch_window_seconds: float = 0.1, max_batch_size: int = 16):
        self.batch_window = batch_window_seconds
        self.max_batch_size = max_batch_size
        self._queue: list[tuple[ChatCompletionRequest, asyncio.Future]] = []
        self._lock = asyncio.Lock()
        self._running_task = None

    async def add_to_batch(self, request: ChatCompletionRequest, execute_fn: Callable[[ChatCompletionRequest], Any]) -> ChatCompletionResponse:
        """Enqueue request and wait for batch window execution to resolve."""
        future = asyncio.get_running_loop().create_future()
        
        async with self._lock:
            self._queue.append((request, future))
            if len(self._queue) >= self.max_batch_size:
                # Trigger batch flush immediately if size threshold is hit
                await self._flush_batch(execute_fn)
            elif not self._running_task or self._running_task.done():
                self._running_task = asyncio.create_task(self._wait_and_flush(execute_fn))
                
        return await future

    async def _wait_and_flush(self, execute_fn):
        await asyncio.sleep(self.batch_window)
        async with self._lock:
            await self._flush_batch(execute_fn)

    async def _flush_batch(self, execute_fn):
        if not self._queue:
            return
            
        current_batch = self._queue[:]
        self._queue.clear()
        
        logger.info(f"Flushing micro-batch of size {len(current_batch)} queries.")
        
        # Execute concurrently in a gather block
        tasks = []
        for req, _ in current_batch:
            tasks.append(execute_fn(req))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for (req, future), res in zip(current_batch, results):
            if isinstance(res, Exception):
                future.set_exception(res)
            else:
                future.set_result(res)

# Global batch scheduler instance
batch_scheduler = BatchScheduler()
