"""Моторный контур: волевой шлюз и выходные элементы."""

from __future__ import annotations

from .links import STATE_2_PERM


class MotorGate:
    """Волевой шлюз: действие разрешено только при активном «Ц» и погашенном «С»."""

    __slots__ = ("net",)

    def __init__(self, net) -> None:
        self.net = net

    def allows_motor(self) -> bool:
        if not self.net.cfg.motor_enabled:
            return False
        motivation = self.net.motivation
        return motivation.target_active() and not motivation.stress_active()


class MotorElement:
    """Выходной элемент: привод, манипулятор, реле.

    Нисходящая волна сама по себе не двигает привод: нужен разрешающий
    сигнал от целевого инстинкта. Без него система лишь «проигрывает»
    последовательность на сенсорных элементах (внутреннее планирование).
    """

    __slots__ = ("net", "name", "up_links", "actuations", "plans")

    def __init__(self, net, name: str) -> None:
        self.net = net
        self.name = name
        self.up_links: list = []
        self.actuations = 0
        self.plans = 0

    def recv_down(self, link) -> None:
        if link.state != STATE_2_PERM:
            return
        if self.net.gate.allows_motor():
            self.actuations += 1
            self.net.monitor.emit(self.name, "motor", source=self)
        else:
            self.plans += 1
            self.net.monitor.emit(self.name, "plan", source=self)

    def label(self) -> str:
        return self.name

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MotorElement {self.name}>"
