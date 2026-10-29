"""Монитор — «что система видит» и «о чём система думает»."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorEvent:
    t: int
    char: str
    mode: str          # perception | thinking | plan | motor
    origin: str | None = None


class Monitor:
    __slots__ = ("clock", "events")

    def __init__(self, clock) -> None:
        self.clock = clock
        self.events: list[MonitorEvent] = []

    def emit(self, char: str, mode: str, source=None, origin: str | None = None) -> None:
        self.events.append(MonitorEvent(self.clock.now, char, mode, origin))

    def text(self, mode: str | None = None, origin: str | None = None) -> str:
        return "".join(
            e.char
            for e in self.events
            if (mode is None or e.mode == mode) and (origin is None or e.origin == origin)
        )

    def since(self, index: int, mode: str | None = None) -> list[MonitorEvent]:
        return [e for e in self.events[index:] if mode is None or e.mode == mode]

    def clear(self) -> None:
        self.events.clear()

    def __len__(self) -> int:
        return len(self.events)
