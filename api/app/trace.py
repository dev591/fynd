"""Trace events: every pipeline hop emits one. The dashboard's live rail renders these over SSE."""
import asyncio, time
from collections import deque
from dataclasses import dataclass, asdict, field


@dataclass
class TraceEvent:
    request_id: str
    layer: str
    status: str  # start | hit | miss | done | error
    ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    detail: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def dict(self):
        return asdict(self)


class TraceBus:
    def __init__(self, history: int = 500):
        self.history = deque(maxlen=history)
        self.subs: set[asyncio.Queue] = set()

    def emit(self, ev: TraceEvent):
        self.history.append(ev)
        for q in list(self.subs):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:  # slow consumer: drop, never block the pipeline
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subs.discard(q)


bus = TraceBus()
