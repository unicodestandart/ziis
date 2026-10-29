"""ФИМ — функциональный искусственный мемстинкт и уровень сети.

Кольцо: H -> B1 -> B2 -> B3 -> B4 -> H. Возбуждение по базовым синапсам
идёт в одном такте инстинкта (250 мс), поэтому передача реализована
синхронным вызовом, а не отложенными событиями.

В логике нет координат ленты. Слот принимает сигнал только по порядку
номеров и только в пределах кадра. Смысл памяти — это путь по закреплённым
связям до элементов, а не участок текста: текст нужен лишь для показа.
"""

from __future__ import annotations

from .config import MODE_GENERATE, MODE_RECOGNIZE, MODE_WRITE
from .links import AuxLink
from .neurons import BasicNeuron, HeadNeuron


def node_id(node) -> str:
    """Идентичность узла нижнего уровня: ФИМ или символ рецептора."""
    fim = getattr(node, "fim", None)
    return fim.gid if fim is not None else getattr(node, "char", "?")


class FIM:
    __slots__ = (
        "net",
        "level",
        "index",
        "head",
        "basics",
        "cursor",
        "frame_capture",
        "frame_deadline",
        "last_capture_at",
        "rec_cursor",
        "rec_last",
        "support",
        "snapshot",
        "cycle",
        "ticks",
        "exposure",
        "active",
        "frozen",
        "slot_limit",
        "window",
        "gid",
    )

    def __init__(self, net, level, index: int) -> None:
        cfg = net.cfg
        self.net = net
        self.level = level
        self.index = index
        self.gid = f"L{level.index}:{index}"
        self.active = True
        self.frozen = False
        self.cycle = cfg.cycle_ms(level.index)
        self.ticks = cfg.ticks_per_cycle(level.index)
        self.exposure = cfg.exposure_for(level.index)
        self.slot_limit = (
            cfg.min_reports if cfg.min_support <= 1 else cfg.slots_for(level.index)
        )
        self.window = cfg.capture_window_ms(level.index)

        self.head = HeadNeuron(net, self)
        self.basics = [BasicNeuron(net, self, i + 1) for i in range(cfg.n_basic)]
        for basic in self.basics:
            self.head.aux.append(AuxLink(net, self.head, basic, cfg.aux_delay_ms))

        self.cursor = 1
        self.frame_capture: dict[int, object] = {}
        self.frame_deadline = -1     # кадр живёт один цикл от первого сигнала
        self.last_capture_at = -1    # время последнего занятого слота
        self.rec_cursor = 1
        self.rec_last = -10**9
        # Свидетели по циклам: цепочка становится памятью только если
        # повторилась, а не потому что случайно попалась первой.
        self.support: dict[tuple[int, ...], int] = {}
        self.snapshot = ""       # смысл памяти сразу после фиксации
        self.head.cycle_end = self.cycle

    # ------------------------------------------------------------------
    @property
    def cycle_end(self) -> int:
        return self.head.cycle_end

    def mode(self) -> str:
        if not self.head.is_consolidated:
            return MODE_WRITE
        if self.net.now <= self.head.permission_until:
            return MODE_GENERATE
        return MODE_RECOGNIZE

    def end_cycle(self, now: int) -> None:
        """Граница цикла.

        Кадр закрывается, когда кольцо заполнено или истёк его цикл.
        Такт не режет кадр пополам: слог — это пара подряд идущих букв,
        а не «то, что успело до следующего такта».
        """
        keep = (
            not self.head.is_consolidated
            and self.frame_capture
            and not self.frame_ready(now)
        )
        if not keep:
            self.close_frame(now)
        self.start_cycle(now, keep_frame=keep)

    def frame_ready(self, now: int) -> bool:
        """Кадр готов к оценке: кольцо заполнено или цикл кадра истёк."""
        if len(self.frame_capture) >= min(self.slot_limit, len(self.basics)):
            return True
        return self.frame_deadline >= 0 and now >= self.frame_deadline

    def close_frame(self, now: int, force: bool = False) -> None:
        if not self.head.is_consolidated and self.frame_capture:
            if force or self.frame_ready(now):
                self.try_consolidate()
        self.reset_frame(now)

    def close_word(self, now: int) -> None:
        """Пробел: слово закончилось.

        Недособранная пара слогов не становится памятью слова: уровень
        слов оценивает только то, что успело сложиться до пробела.
        """
        if self.head.is_consolidated:
            return
        if self.frame_capture:
            self.try_consolidate()
        self.reset_frame(now)
        if self.active and not self.head.is_consolidated:
            self.basics[0].open_window(now)

    def start_cycle(self, now: int, keep_frame: bool = False) -> None:
        self.head.tick_index = 0
        self.head.cycle_end = now + self.cycle
        if not keep_frame:
            self.reset_frame(now)

    def reset_frame(self, now: int) -> None:
        self.cursor = 1
        self.frame_deadline = -1
        self.last_capture_at = -1
        self.frame_capture.clear()
        # Счёт отчётов относится к одному кадру: не очистив его, ФИМ
        # консолидировался по устаревшим свидетельствам прошлого кадра.
        self.head.reporters.clear()
        for basic in self.basics:
            basic.start_frame()

    def restart_frame(self, now: int) -> None:
        """Новый кадр с этого же места: следующая пара идёт сразу за парой."""
        self.reset_frame(now)
        self.basics[0].open_window(now)

    # ------------------------------------------------------------------
    def expanded(self, depth: int = 12) -> str:
        """Смысл памяти: путь по закреплённым связям до элементов.

        Буква существует только в рецепторе-Элементе; выше лежит путь.
        Поэтому текст памяти восстанавливается рекурсией по связям,
        а не хранится отдельно.
        """
        if depth == 0:
            return "?"
        if not any(b.perm_links for b in self.basics):
            return self.snapshot
        out = []
        for basic in self.basics:
            if not basic.perm_links:
                continue
            link = sorted(basic.perm_links, key=lambda l: l.uid)[0]
            low = link.lower
            fim = getattr(low, "fim", None)
            out.append(
                fim.expanded(depth - 1) if fim is not None else getattr(low, "char", "?")
            )
        return (" " if self.level.index >= 3 else "").join(out)

    def candidate_text(self, slots) -> str:
        """Текст, который получится, если фиксировать текущую цепочку."""
        out = []
        for i in slots:
            low = self.frame_capture[i].lower
            fim = getattr(low, "fim", None)
            out.append(fim.expanded() if fim is not None else getattr(low, "char", "?"))
        return "".join(out)

    def try_consolidate(self) -> None:
        """Конец цикла: подтверждённая цепочка становится памятью.

        Захваченная один раз цепочка — только свидетель. Пока она не
        повторится в другом цикле, ФИМ остаётся свободным и продолжает
        пробовать: так долгое обучение сходится к тому, что в тексте
        действительно повторяется, а не к тому, что случайно попало первым.
        """
        head = self.head
        if head.is_consolidated:
            return
        slots = sorted(self.frame_capture)
        if len(slots) < self.net.cfg.min_reports:
            return
        key = tuple(self.frame_capture[i].uid for i in slots)
        seen = self.support.get(key, 0) + 1
        self.support[key] = seen
        if seen < self.net.cfg.min_support_for(self.level.index):
            return
        head.consolidate()
        head.fire_up()
        self.net.instinct.on_head_spike(head)
        self.net.levels[self.level.index - 1].rotate()

    def advance(self, from_index: int) -> None:
        """Возбуждение идёт дальше по кольцу в строгом порядке номеров.

        Нейрон без закреплённых связей не является элементом паттерна
        и пропускается насквозь; нейрон с закреплённой связью ждёт свой
        собственный спайк снизу.
        """
        j = from_index
        while True:
            j += 1
            if j > len(self.basics):
                self.rec_cursor = 1
                self.head.ring_return()
                return
            if self.basics[j - 1].perm_links:
                self.rec_cursor = j
                return

    def generation_pass(self) -> None:
        """Нисходящая выдача: сигналы уходят вниз в записанном порядке."""
        for basic in self.basics:
            basic.fire_down(self.net.now)

    # ------------------------------------------------------------------
    def pattern(self) -> list[str]:
        out: list[str] = []
        for basic in self.basics:
            if basic.perm_links:
                link = sorted(basic.perm_links, key=lambda l: l.uid)[0]
                label = getattr(link.lower, "label", None)
                out.append(label() if callable(label) else "?")
            else:
                out.append("·")
        return out

    def pattern_text(self) -> str:
        """Смысл памяти по слотам: текст, а не номера нижних ФИМ."""
        out: list[str] = []
        for basic in self.basics:
            if not basic.perm_links:
                out.append("·")
                continue
            link = sorted(basic.perm_links, key=lambda l: l.uid)[0]
            low = link.lower
            fim = getattr(low, "fim", None)
            text = fim.expanded() if fim is not None else getattr(low, "char", "?")
            out.append(text.replace(" ", "_"))
        # Пробел показываем как «_»: иначе он неотличим от пустого слота «·».
        # На уровне фраз слова разделяются пробелом, иначе «мама мыла раму»
        # читается как одно слово.
        sep = " " if self.level.index >= 3 else ""
        return sep.join(out)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FIM {self.gid} {self.pattern_text()}>"


class Level:
    __slots__ = ("net", "index", "size", "fims", "basics", "heads", "group", "groups", "last_rotate")

    def __init__(self, net, index: int, size: int) -> None:
        self.net = net
        self.index = index
        self.size = size
        self.fims = [FIM(net, self, i) for i in range(size)]
        self.basics = [b for f in self.fims for b in f.basics]
        self.heads = [f.head for f in self.fims]
        self.groups = max(1, net.cfg.fim_groups)
        self.group = 0
        self.last_rotate = -10**9
        self._apply_group()

    def _apply_group(self) -> None:
        for i, fim in enumerate(self.fims):
            fim.active = (not fim.frozen) and (i % self.groups) == self.group

    def rotate(self, now: int | None = None) -> None:
        """Следующий цикл пишет следующая группа ФИМ."""
        now = self.net.now if now is None else now
        if now - self.last_rotate < self.net.cfg.cycle_ms(self.index):
            return
        self.last_rotate = now
        self.group = (self.group + 1) % self.groups
        self._apply_group()

    @property
    def consolidated(self) -> list[FIM]:
        return [f for f in self.fims if f.head.is_consolidated]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Level {self.index} size={self.size}>"
