"""Сборка ЗИИС: входной буфер, уровни, тактирование, прогон."""

from __future__ import annotations

import random
from collections import deque

from .clock import EventClock
from .config import (
    FREQ_PERMILLE,
    LETTERS,
    NOISE_CHARS,
    SPACE,
    Config,
)
from .fim import Level
from .instinct import AttentionInstinct, MotivationPair
from .links import STATE_2_PERM, UpDownLink
from .monitor import Monitor
from .motor import MotorElement, MotorGate
from .neurons import Element


class InputBuffer:
    """Входной буфер клавиатуры.

    Физическая скорость набора не важна: символы выталкиваются в сеть
    строго с шагом 100 мс.
    """

    __slots__ = ("net", "queue", "scheduled", "last_press", "session_hold_ms")

    def __init__(self, net) -> None:
        self.net = net
        self.queue: deque[str] = deque()
        self.scheduled = False
        self.last_press = -10**9
        # такт продолжает идти, пока оператор не замолчал на это время
        self.session_hold_ms = 500

    def press(self, char: str) -> None:
        self.queue.append(char)
        self.last_press = self.net.now
        if not self.scheduled:
            self.scheduled = True
            self.net.clock.schedule(0, self._flush)

    def _flush(self) -> None:
        now = self.net.now
        if self.queue:
            char = self.queue.popleft()
            element = self.net.elements.get(char)
            if element is not None:
                element.key_press()
        if self.queue or now - self.last_press < self.session_hold_ms:
            self.net.clock.schedule(self.net.cfg.element_step_ms, self._flush)
        else:
            self.scheduled = False


class ZIIS:
    def __init__(self, cfg: Config | None = None) -> None:
        self.cfg = cfg or Config()
        self.clock = EventClock(max_events=self.cfg.max_events)
        self.monitor = Monitor(self.clock)
        self.elements: dict[str, Element] = {}
        self.levels: list[Level] = []
        self.buffer = InputBuffer(self)
        self.instinct = AttentionInstinct(self)
        self.motivation = MotivationPair(self)
        self.gate = MotorGate(self)
        self.motor_elements: dict[str, MotorElement] = {}
        self.last_memory = None
        self.tape_pos = 0            # позиция на ленте ввода, в символах
        self.silent_until = -1       # на время воспроизведения такт не дублирует
        self._rng = random.Random(self.cfg.seed)
        self._build()
        self._bootstrap()

    # ------------------------------------------------------------------
    @property
    def now(self) -> int:
        return self.clock.now

    def _build(self) -> None:
        chars = list(LETTERS) + [SPACE] + list(NOISE_CHARS)
        for char in chars:
            self.elements[char] = Element(
                self,
                char,
                is_instinct=(char in LETTERS or char == SPACE),
                is_noise=char in NOISE_CHARS,
            )

        lower_nodes: list = list(self.elements.values())
        for level_index in range(1, self.cfg.levels + 1):
            level = Level(self, level_index, self.cfg.size_of(level_index))
            self.levels.append(level)
            self._connect(lower_nodes, level)
            lower_nodes = list(level.heads)

    def _connect(self, lower_nodes: list, level: Level) -> None:
        total = len(level.basics)
        if total == 0:
            return
        for node in lower_nodes:
            count = self._fanout(node, total)
            if count <= 0:
                continue
            picks = self._rng.sample(range(total), min(count, total))
            for index in picks:
                UpDownLink(
                    self, lower=node, upper=level.basics[index], delay=self.cfg.updown_delay_ms
                )

    def _fanout(self, node, total: int) -> int:
        # Число синапсов Элемента пропорционально частоте буквы в языке.
        char = getattr(node, "char", None)
        if char is not None:
            weight = FREQ_PERMILLE.get(char, 0)
            return max(2, weight * total * self.cfg.letter_scale // 1000)
        return self.cfg.upper_density_permille * total // 1000

    def _bootstrap(self) -> None:
        """Предустановленные слоги уровня 1: готовые закреплённые связи."""
        syllables = tuple(self.cfg.bootstrap_syllables)
        if not syllables or not self.levels:
            return
        level = self.levels[0]
        for index, text in enumerate(syllables):
            if index >= len(level.fims) or not text:
                break
            fim = level.fims[index]
            for slot, char in enumerate(text[: self.cfg.n_basic]):
                element = self.elements.get(char)
                if element is None:
                    break
                link = UpDownLink(
                    self, element, fim.basics[slot], self.cfg.updown_delay_ms
                )
                link.state = STATE_2_PERM
                basic = fim.basics[slot]
                basic.perm_links.add(link)
                basic.is_consolidated = True
                basic.pending_fix = False
            else:
                fim.head.is_consolidated = True
                fim.head.consolidations += 1
                fim.snapshot = text
        if self.cfg.bootstrap_freeze:
            for fim in level.fims:
                if not fim.head.is_consolidated:
                    fim.frozen = True
                    fim.active = False

    # ------------------------------------------------------------------
    # ввод
    # ------------------------------------------------------------------
    def type_text(
        self, text: str, start: int | None = None, gap_ms: int | None = None
    ) -> int:
        start = self.now if start is None else start
        gap = self.cfg.element_step_ms if gap_ms is None else gap_ms
        for index, char in enumerate(text):
            self.clock.at(start + index * gap, self.buffer.press, char)
        return start + max(len(text) - 1, 0) * gap

    def run(self, until: int | None = None) -> int:
        return self.clock.run(until)

    def remember(
        self,
        text: str,
        start: int | None = None,
        gap_ms: int | None = None,
        settle_ms: int | None = None,
    ) -> int:
        end = self.type_text(text, start, gap_ms)
        settle = (
            self.cfg.instinct_hold_ms + 200 if settle_ms is None else settle_ms
        )
        self.run(end + settle)
        return end

    # ------------------------------------------------------------------
    # узнавание и воспроизведение
    # ------------------------------------------------------------------
    def word_boundary(self) -> None:
        """Пробел: слово закончилось. Разрыв только на уровне слов."""
        index = self.cfg.word_break_level
        if index < 2 or index > len(self.levels):
            return
        now = self.now
        for fim in self.levels[index - 1].fims:
            fim.close_word(now)

    def command(self) -> None:
        """Моторная/мыслительная команда: 2 спайка подряд от Инстинкта."""
        self.instinct.emit_double()

    def active_memories(self) -> list:
        return [
            fim
            for level in self.levels
            for fim in level.fims
            if fim.head.is_consolidated and fim.head.active()
        ]

    def best_memory(self):
        """Самый старший и самый полный активный ФИМ."""
        best = None
        best_key = None
        for fim in self.active_memories():
            key = (
                fim.level.index,
                sum(len(b.perm_links) for b in fim.basics),
                fim.head.last_activity,
            )
            if best_key is None or key > best_key:
                best, best_key = fim, key
        return best

    def recall(
        self,
        prompt: str,
        gap_ms: int | None = None,
        span_ms: int | None = None,
        prefer_level: int | None = None,
    ) -> str:
        """Предъявить текст и воспроизвести самый полный из узнавших ФИМ."""
        end = self.type_text(prompt, gap_ms=gap_ms)
        self.run(end + 3 * self.cfg.element_step_ms + 600)

        def rank(f):
            return (
                -f.level.index,
                -sum(len(b.perm_links) for b in f.basics),
                -f.head.last_activity,
            )

        candidates = sorted(self.active_memories(), key=rank)
        if prefer_level is not None:
            candidates = [f for f in candidates if f.level.index == prefer_level]
        candidates = candidates[:6]
        self.last_memory = candidates[0] if candidates else None
        for fim in candidates:
            text = self.play(fim, span_ms=span_ms)
            if text:
                self.last_memory = fim
                return text
        return ""

    def recall_all(
        self, prompt: str, gap_ms: int | None = None, span_ms: int | None = None
    ) -> str:
        """Параллельное воспроизведение всех активных очагов (как в ТЗ)."""
        mark = len(self.monitor)
        end = self.type_text(prompt, gap_ms=gap_ms)
        self.run(end + 3 * self.cfg.element_step_ms + 600)
        self.command()
        self.run(self.now + (span_ms or self.cfg.permission_hold_ms + 200))
        return "".join(e.char for e in self.monitor.since(mark, mode="thinking"))

    def play(self, fim, span_ms: int | None = None) -> str:
        """Прямое воспроизведение конкретного ФИМ (диагностика и тесты)."""
        mark = len(self.monitor)
        span = span_ms or self.cfg.instinct_period_ms + 50
        # Один проход, а не самовоспроизведение: такт инстинкта за это время
        # не должен повторно запускать все активные очаги.
        self.silent_until = self.now + span
        fim.head.grant_permission()
        # разрешение идёт по вспомогательным синапсам 1 мс — даём ему дойти
        self.run(self.now + self.cfg.aux_delay_ms)
        fim.generation_pass()
        # каскад вниз до элементов идёт в этом же такте
        self.run(self.now + (span_ms or self.cfg.instinct_period_ms + 50))
        return "".join(e.char for e in self.monitor.since(mark, mode="thinking"))

    # ------------------------------------------------------------------
    # статистика
    # ------------------------------------------------------------------
    def stats(self) -> dict:
        levels = []
        for level in self.levels:
            consolidated = level.consolidated
            perm = sum(
                len(b.perm_links) for f in level.fims for b in f.basics
            )
            levels.append(
                {
                    "level": level.index,
                    "size": level.size,
                    "consolidated": len(consolidated),
                    "perm_links": perm,
                    "patterns": [f.pattern_text() for f in consolidated],
                }
            )
        return {
            "now": self.now,
            "events": self.clock.processed,
            "levels": levels,
            "instinct": {
                "ticks": self.instinct.ticks,
                "double_pulses": self.instinct.double_pulses,
                "triggers": self.instinct.triggers,
            },
            "monitor": {
                "perception": len(self.monitor.text("perception")),
                "thinking": len(self.monitor.text("thinking")),
            },
        }

    def report(self) -> str:
        stats = self.stats()
        lines = [f"t = {stats['now']} мс, событий: {stats['events']}"]
        for level in stats["levels"]:
            lines.append(
                f"  уровень {level['level']}: ФИМ {level['consolidated']}/{level['size']}, "
                f"PERM-связей {level['perm_links']}"
            )
            for pattern in level["patterns"][:12]:
                lines.append(f"      {pattern}")
            if len(level["patterns"]) > 12:
                lines.append(f"      ... ещё {len(level['patterns']) - 12}")
        instinct = stats["instinct"]
        lines.append(
            f"  инстинкт: тактов {instinct['ticks']}, "
            f"запусков {instinct['triggers']}, двойных импульсов {instinct['double_pulses']}"
        )
        return "\n".join(lines)
