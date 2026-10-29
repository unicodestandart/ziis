"""Подсистема инстинктов.

  * AttentionInstinct — Инстинкт внимания «В»: глобальный тактовый генератор
    и триггер значимости.
  * MotivationPair   — реципрокная пара «С» (стресс) / «Ц» (цель).
"""

from __future__ import annotations

from collections import deque


class AttentionInstinct:
    __slots__ = (
        "net",
        "recent",
        "ticking",
        "external",
        "active_until",
        "ticks",
        "double_pulses",
        "triggers",
    )

    def __init__(self, net) -> None:
        self.net = net
        self.recent: deque[int] = deque()
        self.ticking = False
        self.external = False
        self.active_until = -1
        self.ticks = 0
        self.double_pulses = 0
        self.triggers = 0

    # ---------------- запуск от внешней среды ----------------
    def on_letter_spike(self) -> None:
        cfg = self.net.cfg
        now = self.net.now
        # Глобальный такт запускается первым же символом: иначе первые две
        # буквы предъявления не попадают ни в одно окно, и слово пишется
        # с середины — «мама» даёт «ма» + «ам» вместо «ма» + «ма».
        if not self.ticking:
            self._start(now)
        self.recent.append(now)
        while self.recent and now - self.recent[0] > cfg.instinct_window_ms:
            self.recent.popleft()
        if len(self.recent) < cfg.instinct_threshold:
            return
        self.recent.clear()
        self.triggers += 1
        self.external = True
        self.active_until = max(self.active_until, now + cfg.instinct_hold_ms)
        if not self.ticking:
            self._start(now)

    # ---------------- реципрокная поддержка от сети ----------------
    def on_head_spike(self, head) -> None:
        cfg = self.net.cfg
        now = self.net.now
        if not self.ticking:
            self._start(now)
        self.active_until = max(self.active_until, now + cfg.reciprocal_hold_ms)

    def _start(self, now: int) -> None:
        self.ticking = True
        self.active_until = max(
            self.active_until, now + self.net.cfg.reciprocal_hold_ms
        )
        self.net.clock.schedule(0, self._tick)

    # ---------------- тактирование ----------------
    def _tick(self) -> None:
        now = self.net.now
        if now > self.active_until:
            self.ticking = False
            if self.external:
                self.external = False
                self.emit_double()
            return
        self.ticks += 1
        for level in self.net.levels:
            for head in level.heads:
                head.on_clock()
        self.net.clock.schedule(self.net.cfg.instinct_period_ms, self._tick)

    # ---------------- 2 спайка подряд ----------------
    def emit_double(self) -> None:
        if self.net.now <= self.net.silent_until:
            return          # идёт воспроизведение: повторный залп не нужен
        self.double_pulses += 1
        for level in self.net.levels:
            for head in level.heads:
                head.on_double_instinct()

    def is_active(self) -> bool:
        return self.ticking or self.net.now <= self.active_until


class MotivationPair:
    """Стрессовый «С» и Целевой «Ц» инстинкты с взаимным торможением."""

    __slots__ = (
        "net",
        "inhibit_ms",
        "stress_until",
        "target_until",
        "stress_block_until",
        "target_block_until",
    )

    def __init__(self, net, inhibit_ms: int = 400) -> None:
        self.net = net
        self.inhibit_ms = inhibit_ms
        self.stress_until = -1
        self.target_until = -1
        self.stress_block_until = -1
        self.target_block_until = -1

    def excite_stress(self, hold_ms: int = 500) -> bool:
        """Возбуждение «С». Пока цель активна — стресс заторможен."""
        now = self.net.now
        if now <= self.stress_block_until:
            return False
        self.stress_until = now + hold_ms
        self.target_until = -1                       # цель мгновенно погашена
        self.target_block_until = now + self.inhibit_ms
        return True

    def excite_target(self, hold_ms: int = 500) -> bool:
        """Возбуждение «Ц». Пока активен стресс — цель заторможена."""
        now = self.net.now
        if now <= self.target_block_until:
            return False
        self.target_until = now + hold_ms
        self.stress_until = -1                       # стресс мгновенно погашен
        self.stress_block_until = now + self.inhibit_ms
        return True

    def stress_active(self) -> bool:
        return self.net.now <= self.stress_until

    def target_active(self) -> bool:
        return self.net.now <= self.target_until
