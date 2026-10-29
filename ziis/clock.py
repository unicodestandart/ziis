"""Детерминированная очередь событий в целых миллисекундах.

Модель времени: simulated time, шаг не фиксирован, события исполняются
строго по (время, порядок постановки). Никакой случайности при исполнении нет.
"""

from __future__ import annotations

import heapq
import itertools


class EventClock:
    __slots__ = ("now", "_heap", "_seq", "max_events", "processed")

    def __init__(self, max_events: int = 4_000_000) -> None:
        self.now = 0
        self._heap: list = []
        self._seq = itertools.count()
        self.max_events = max_events
        self.processed = 0

    # ------------------------------------------------------------------
    def schedule(self, delay: int, fn, *args) -> None:
        if delay < 0:
            raise ValueError("отрицательная задержка синапса запрещена")
        heapq.heappush(self._heap, (self.now + delay, next(self._seq), fn, args))

    def at(self, time: int, fn, *args) -> None:
        heapq.heappush(self._heap, (max(time, self.now), next(self._seq), fn, args))

    # ------------------------------------------------------------------
    def run(self, until: int | None = None) -> int:
        steps = 0
        while self._heap:
            time = self._heap[0][0]
            if until is not None and time > until:
                break
            _, _, fn, args = heapq.heappop(self._heap)
            self.now = time
            self.processed += 1
            fn(*args)
            steps += 1
            if self.processed > self.max_events:
                raise RuntimeError(
                    "превышен лимит событий: в сети возник незатухающий цикл возбуждения"
                )
        if until is not None and self.now < until:
            self.now = until
        return steps

    @property
    def busy(self) -> bool:
        return bool(self._heap)

    def peek(self) -> int | None:
        return self._heap[0][0] if self._heap else None
