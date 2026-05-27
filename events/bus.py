import asyncio
from typing import Dict, List, Callable, Any
import structlog

logger = structlog.get_logger()

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._queue = asyncio.Queue(maxsize=200)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug("event_subscribed", event_type=event_type)

    async def emit(self, event_type: str, data: Any = None):
        await self._queue.put((event_type, data))

    def emit_nowait(self, event_type: str, data: Any = None):
        try:
            self._queue.put_nowait((event_type, data))
        except asyncio.QueueFull:
            logger.warning("event_bus_full", event_type=event_type)

    async def _process_events(self):
        while self._running:
            try:
                event_type, data = await self._queue.get()
                if event_type in self._subscribers:
                    for callback in self._subscribers[event_type]:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("event_processing_error", error=str(e))

    def start(self):
        logger.info("starting_event_bus")
        self._running = True
        self._task = asyncio.create_task(self._process_events())

    async def stop(self):
        logger.info("stopping_event_bus")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
