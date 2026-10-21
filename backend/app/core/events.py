import asyncio
import json
from typing import Dict, List, Any, Optional
from app.core.logging import logger

class EventBus:
    """
    In-memory pub-sub event bus for streaming live workflow events to frontend clients via SSE.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        self._subscribers[run_id].append(queue)
        logger.debug(f"New SSE subscriber attached to run {run_id}")
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        if run_id in self._subscribers:
            if queue in self._subscribers[run_id]:
                self._subscribers[run_id].remove(queue)
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]
        logger.debug(f"SSE subscriber removed from run {run_id}")

    async def publish(self, run_id: Any, event_type: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """
        Publishes an event to all subscribers listening to this run_id and a global channel.
        Supports both positional (run_id, event_type, data) and single-dictionary payload signatures.
        """
        if isinstance(run_id, dict):
            payload_dict = run_id
            target_run_id = str(payload_dict.get("run_id", "global"))
            ev_type = str(event_type or payload_dict.get("event_type") or payload_dict.get("type", "EVENT"))
            data_dict = data if data is not None else payload_dict.get("data", payload_dict)
        else:
            target_run_id = str(run_id)
            ev_type = str(event_type or "EVENT")
            data_dict = data if data is not None else {}

        message = {
            "run_id": target_run_id,
            "event_type": ev_type,
            "data": data_dict,
        }
        json_payload = json.dumps(message)

        # Notify run-specific subscribers
        target_queues = list(self._subscribers.get(target_run_id, []))
        # Also notify global subscribers
        global_queues = list(self._subscribers.get("global", []))

        for q in target_queues + global_queues:
            try:
                q.put_nowait(json_payload)
            except asyncio.QueueFull:
                logger.warning(f"Subscriber queue full for run {target_run_id}. Dropping event.")

event_bus = EventBus()
