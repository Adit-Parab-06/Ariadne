import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

REPLAY_DIR = Path(__file__).resolve().parent.parent.parent / "replays"


class EventBus:
    def __init__(self, tenant: str, run_id: str):
        self.tenant = tenant
        self.run_id = run_id
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self.events: List[Dict[str, Any]] = []
        self._seq = 0
        self.finished = False

        REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        self.replay_file = REPLAY_DIR / f"{tenant}_{run_id}.jsonl"

    def publish(self, event_type: str, agent: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Publishes an event with thread-safe sequence numbering and replay persistence."""
        with self._cond:
            event = {
                "seq": self._seq,
                "ts": int(time.time() * 1000),
                "type": event_type,
                "agent": agent,
                "data": data,
            }
            self._seq += 1
            self.events.append(event)

            if event_type in ("run.completed", "run.failed"):
                self.finished = True

            # Append to disk replay log
            try:
                with open(self.replay_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as e:
                logger.warning(f"Failed to append replay log {self.replay_file}: {e}")

            self._cond.notify_all()
            return event

    def subscribe(self, from_seq: int = 0, timeout: float = 30.0) -> Generator[Dict[str, Any], None, None]:
        """
        Yields stored events from sequence `from_seq`, then blocks and yields live events
        as they are published until run.completed or run.failed.
        """
        current_seq = from_seq
        while True:
            with self._cond:
                # Catch up on any events published so far
                while current_seq < len(self.events):
                    event = self.events[current_seq]
                    current_seq += 1
                    yield event
                    if event["type"] in ("run.completed", "run.failed"):
                        return

                if self.finished:
                    return

                # Wait for new events
                notified = self._cond.wait(timeout=timeout)
                if not notified:
                    # Timeout reached without event, yield keepalive heartbeat if needed
                    yield {
                        "seq": -1,
                        "ts": int(time.time() * 1000),
                        "type": "heartbeat",
                        "agent": "system",
                        "data": {},
                    }


_BUS_REGISTRY: Dict[str, EventBus] = {}
_BUS_LOCK = threading.Lock()


def get_bus(tenant: str, run_id: str) -> EventBus:
    """Returns or creates the singleton EventBus for a given run, loading past events from disk if present."""
    key = f"{tenant}:{run_id}"
    with _BUS_LOCK:
        if key not in _BUS_REGISTRY:
            bus = EventBus(tenant, run_id)
            if bus.replay_file.exists():
                try:
                    with open(bus.replay_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                bus.events.append(json.loads(line))
                    bus._seq = len(bus.events)
                    if bus.events and bus.events[-1].get("type") in ("run.completed", "run.failed"):
                        bus.finished = True
                except Exception as e:
                    logger.warning(f"Error loading replay file {bus.replay_file}: {e}")
            _BUS_REGISTRY[key] = bus
        return _BUS_REGISTRY[key]
