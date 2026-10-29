"""Синапсы ЗИИС.

Весов нет. Синапс — проводник спайка с целочисленной задержкой.
Межуровневый синапс «верх/низ» дополнительно имеет дискретный флаг состояния.
"""

from __future__ import annotations

STATE_1 = 1        # состояние существует топологически, но не закреплено
STATE_2_TEMP = 2   # временная фиксация на один цикл консолидации
STATE_2_PERM = 3   # постоянная фиксация

STATE_NAMES = {
    STATE_1: "STATE_1",
    STATE_2_TEMP: "STATE_2_TEMP",
    STATE_2_PERM: "STATE_2_PERM",
}


class UpDownLink:
    """Двухсторонний межуровневый синапс «верх/низ».

    Реализован как два параллельных разнонаправленных односторонних канала,
    которые делят один дискретный флаг состояния.
    """

    __slots__ = ("net", "lower", "upper", "state", "delay", "uid")

    _counter = 0

    def __init__(self, net, lower, upper, delay: int) -> None:
        self.net = net
        self.lower = lower      # узел нижележащего уровня (Элемент или H)
        self.upper = upper      # базовый нейрон вышележащего уровня
        self.state = STATE_1
        self.delay = delay
        UpDownLink._counter += 1
        self.uid = UpDownLink._counter
        lower.up_links.append(self)
        upper.in_links.append(self)

    # канал вверх: нижний -> верхний (восприятие, узнавание)
    # span — участок ленты в координатах символов входа (начало, конец).
    # Верхний слот принимает его, только если он начинается там, где кончился
    # предыдущий: так паттерн верхнего уровня остаётся непрерывным куском ленты.
    def fire_up(self, span: tuple[int, int] | None = None, count: int = 1) -> None:
        for _ in range(count):
            self.net.clock.schedule(self.delay, self.upper.recv_up, self, span)

    # канал вниз: верхний -> нижний (мышление, выдача)
    def fire_down(self, count: int = 1) -> None:
        for _ in range(count):
            self.net.clock.schedule(self.delay, self.lower.recv_down, self)

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return (
            f"<UpDownLink {self.lower!r}->{self.upper!r} {STATE_NAMES[self.state]}>"
        )


class AuxLink:
    """Вспомогательный синапс головной <-> базовый нейрон (внутри ФИМ)."""

    __slots__ = ("net", "head", "basic", "delay")

    def __init__(self, net, head, basic, delay: int) -> None:
        self.net = net
        self.head = head
        self.basic = basic
        self.delay = delay

    def to_basic(self, count: int = 1) -> None:
        for _ in range(count):
            self.net.clock.schedule(self.delay, self.basic.recv_aux)

    def to_head(self) -> None:
        self.net.clock.schedule(self.delay, self.head.recv_aux_from_basic, self.basic)
