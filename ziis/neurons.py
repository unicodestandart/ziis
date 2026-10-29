"""Спайковые автоматы нейронов ЗИИС (Том 2, раздел «Правила работы нейронов»).

Кольцо ФИМ синхронное: инстинкт испускает спайк каждые 250 мс, и каждый
нейрон кольца выдаёт ровно один спайк за такт. Бегущей волны с задержкой
на синапс нет — возбуждение по базовым синапсам идёт в том же такте.
"""

from __future__ import annotations

from .config import MODE_GENERATE, MODE_RECOGNIZE, SPACE
from .links import STATE_1, STATE_2_PERM, STATE_2_TEMP


class Element:
    """Нейрон нулевого уровня: один на каждый уникальный символ."""

    __slots__ = (
        "net",
        "char",
        "is_instinct",
        "is_noise",
        "up_links",
        "perceptions",
        "pos",
    )

    def __init__(self, net, char: str, is_instinct: bool, is_noise: bool) -> None:
        self.net = net
        self.char = char
        self.is_instinct = is_instinct
        self.is_noise = is_noise
        self.up_links: list = []
        self.perceptions = 0
        self.pos = -1          # позиция на ленте ввода, в символах

    def key_press(self) -> None:
        self.perceptions += 1
        self.pos = self.net.tape_pos
        self.net.tape_pos += 1
        self.net.monitor.emit(self.char, "perception", source=self)
        if self.is_instinct:
            self.net.instinct.on_letter_spike()
        for link in self.up_links:
            link.fire_up()
        if self.char == SPACE:
            self.net.word_boundary()

    def recv_down(self, link) -> None:
        if link.state != STATE_2_PERM:
            return
        self.net.monitor.emit(
            self.char, "thinking", source=self, origin=link.upper.fim.gid
        )

    def label(self) -> str:
        return self.char

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Element {self.char!r}>"


class BasicNeuron:
    """Базовый нейрон кольца B1..B4.

    В обоих состояниях: спайк от предыдущего по номеру базового (или от
    головного для B1) передаётся следующему; спайк по синапсу «верх/низ»
    уходит головному по вспомогательному синапсу.
    """

    __slots__ = (
        "net",
        "fim",
        "index",
        "in_links",
        "is_consolidated",
        "frame_capture",
        "window_until",
        "lock_until",
        "temp_links",
        "perm_links",
        "permission_until",
        "aux_count",
        "pending_fix",
        "captures",
        "down_fires",
        "ups_received",
    )

    def __init__(self, net, fim, index: int) -> None:
        self.net = net
        self.fim = fim
        self.index = index
        self.in_links: list = []
        self.is_consolidated = False
        self.frame_capture = None
        self.window_until = -1
        self.lock_until = 0
        self.temp_links: set = set()
        self.perm_links: set = set()
        self.permission_until = 0
        self.aux_count = 0
        self.pending_fix = False
        self.captures = 0
        self.down_fires = 0
        self.ups_received = 0

    # ================= кадр =================
    def start_frame(self) -> None:
        self.frame_capture = None
        self.lock_until = 0
        # У узнавшего нейрона окно — это ещё не законченная волна: слог
        # может пересекать границу такта, и сброс окна рвал бы узнавание.
        if not self.is_consolidated:
            self.window_until = -1
        if self.pending_fix:
            return
        self.aux_count = 0
        for link in self.temp_links:
            if link.state == STATE_2_TEMP:
                link.state = STATE_1
        self.temp_links.clear()

    def open_window(self, now: int, window: int | None = None) -> None:
        """Такт инстинкта: кольцо проходит, открывая окно экспозиции.

        На уровне 1 лента идёт каждые 100 мс, поэтому слот берёт только
        следующую букву. 225 мс — затвор кинокамеры, а не разрешение
        пропускать чужие буквы: с окном 225 мс в слог попадало «ма_».
        """
        if now < self.lock_until:
            return
        if window is None:
            if self.fim.level.index == 1:
                # Первый слот ждёт свою букву весь затвор 225 мс: иначе ФИМ
                # без связи на первую букву теряет вторую пару («ла» в «мыла»).
                window = self.fim.exposure if self.index == 1 else self.net.cfg.element_step_ms
            else:
                window = self.fim.exposure
        self.window_until = now + window

    # ================= вход снизу =================
    def recv_up(self, link, span=None) -> None:
        """Спайк с нижнего уровня.

        Координат ленты нет. В записи слот принимает только следующий
        по номеру сигнал в пределах кадра, в узнавании — только следующий
        по номеру сигнал по постоянной связи. Всё остальное решает порядок.
        """
        now = self.net.now
        self.ups_received += 1
        if (
            not self.is_consolidated
            and self.fim.level.index == 1
            and getattr(link.lower, "char", None) == SPACE
        ):
            # Пробел — граница слова, а не слот слога: кадр закрывается,
            # следующая пара букв начинается с чистого места.
            self.fim.close_frame(now)
            self.fim.restart_frame(now)
            return

        if self.is_consolidated:
            if link.state != STATE_2_PERM:
                return
            if self.index != self.fim.rec_cursor:
                return
            # Окно экспозиции действует и при узнавании: иначе «м» в начале
            # «мыла» дожидалось «а» в конце слова и слог «ма» узнавался
            # там, где его нет.
            if now > self.window_until:
                return
            # Соседние слоты разделены шагом входа: залп копий одного
            # и того же слова не занимает два слота подряд.
            if self.index != 1 and now <= self.fim.rec_last:
                return
            self.fim.rec_last = now
            self.fire_down(now)
            self.fim.advance(self.index)
            if self.fim.rec_cursor != 1:
                # Волна узнавания вооружает следующий слот так же, как
                # волна записи: без этого окно второго слота не открывалось.
                # Выше первого уровня окно — на весь уровень: слово и фраза
                # идут через несколько тактов, а не через 225 мс.
                nxt = self.fim.basics[self.fim.rec_cursor - 1]
                win = None if self.fim.level.index == 1 else self.fim.window
                nxt.open_window(now, win)
            return

        # ---------- запись ----------
        # До фиксации нейрон не пишет новые связи: иначе в PERM попадут
        # чужие буквы из следующих циклов и паттерн перестанет быть парой.
        if self.pending_fix:
            return
        if not self.fim.active:
            return   # не её цикл: свободные ФИМ ждут своей очереди
        limit = self.fim.slot_limit
        if self.fim.cursor > limit:
            return
        if self.frame_capture is not None:
            return
        # Затвор закрывает слот от повторного захвата, но не запрещает ждать
        # свой отчёт. На уровне 1 лента идёт каждые 100 мс, и 225 мс — реальный
        # дедлайн. Выше отчёты редкие: слот ждёт свой сигнал до конца кадра.
        horizon = self.window_until
        if self.index != 1 and self.fim.level.index > 1:
            horizon = max(horizon, self.fim.frame_deadline)
        if now > horizon:
            return
        if self.index != self.fim.cursor:  # строго по порядку B1 -> B4
            return
        # Соседние слоты разделены шагом входа: один и тот же спайк
        # и одновременный залп копий не занимают два слота подряд.
        if now <= self.fim.last_capture_at:
            return
        self.frame_capture = link
        self.captures += 1
        self.fim.cursor = self.index + 1
        self.fim.last_capture_at = now
        if self.index == 1:
            self.fim.frame_deadline = now + self.fim.window
        if self.index < len(self.fim.basics):
            # Затвор следующего нейрона открывается в момент, когда волна
            # прошла через этот: окно отсчитывается от своей ступени,
            # а не от общего такта. Иначе цепочка рвалась на границе такта.
            self.fim.basics[self.index].open_window(now)
        self.fim.head.recv_report(self, link)
        # Цикл набирает минимум два разных базовых (ТЗ) и больше не пишет.
        if (
            self.fim.cursor > self.net.cfg.min_reports
            and self.net.cfg.min_support <= 1
        ):
            self.fim.try_consolidate()
        # Кольцо заполнено — кадр закрывается сразу, а не ждёт такта:
        # следующая пара букв должна начаться со следующей же буквы.
        if self.fim.cursor > limit and self.net.cfg.min_support > 1:
            self.fim.close_frame(now, force=True)
            self.fim.restart_frame(now)

    # ================= вспомогательный синапс =================
    def recv_aux(self) -> None:
        now = self.net.now
        cfg = self.net.cfg
        self.aux_count += 1

        if not self.is_consolidated:
            if self.frame_capture is not None:
                if now <= self.window_until:      # затвор кинокамеры
                    self.lock_until = self.fim.cycle_end
                if self.aux_count >= cfg.temp_aux:
                    if self.frame_capture.state == STATE_1:
                        self.frame_capture.state = STATE_2_TEMP
                    self.temp_links.add(self.frame_capture)
            if self.aux_count >= cfg.perm_aux and self.fim.head.is_consolidated:
                self._fixate()
        else:
            if self.aux_count >= 2:   # 2 спайка H = разрешение на выдачу
                self.permission_until = now + self.fim.cycle

    # ================= выдача вниз =================
    def fire_down(self, now: int | None = None) -> None:
        now = self.net.now if now is None else now
        if now > self.permission_until:
            return
        for link in sorted(self.perm_links, key=lambda l: l.uid):
            link.fire_down()
            self.down_fires += 1

    # ================= внутреннее =================
    def _fixate(self) -> None:
        self.is_consolidated = True
        self.pending_fix = False
        for link in self.temp_links:
            link.state = STATE_2_PERM
            self.perm_links.add(link)
        self.temp_links.clear()

    def label(self) -> str:
        return f"B{self.index}"


class HeadNeuron:
    """Головной нейрон H: тактирует кольцо, фиксирует и воспроизводит паттерн."""

    __slots__ = (
        "net",
        "fim",
        "up_links",
        "aux",
        "is_consolidated",
        "cycle_start",
        "cycle_end",
        "tick_index",
        "cycle_serial",
        "reporters",
        "activation_from_above",
        "ring_returned",
        "permission_until",
        "last_activity",
        "frames",
        "recognitions",
        "consolidations",
        "reports",
    )

    def __init__(self, net, fim) -> None:
        self.net = net
        self.fim = fim
        self.up_links: list = []
        self.aux: list = []
        self.is_consolidated = False
        self.cycle_start = 0
        self.cycle_end = fim.cycle
        self.tick_index = 0       # тактов в текущем цикле консолидации
        self.cycle_serial = 0
        self.reporters: set = set()
        self.activation_from_above = False
        self.ring_returned = False
        self.permission_until = 0
        self.last_activity = -10**9
        self.frames = 0
        self.recognitions = 0
        self.consolidations = 0
        self.reports = 0

    # ================= тактирование =================
    def on_clock(self) -> None:
        """Такт Инстинкта: кольцо проходит, B1 получает окно экспозиции.

        Остальные слоты вооружаются каскадом — в момент захвата предыдущего.
        """
        now = self.net.now
        # Оборванное узнавание не переживает цикл: иначе одна случайная
        # первая половина цепочки блокировала бы новое предъявление.
        if self.fim.rec_cursor != 1 and now - self.fim.rec_last >= self.fim.cycle:
            self.fim.rec_cursor = 1
        # Цикл консолидации: N_базовых тактов на каждый уровень выше.
        self.tick_index += 1
        if self.tick_index >= self.fim.ticks:
            self.close_cycle(now)
        self.fim.basics[0].open_window(now)
        self.frames += 1
        self.activation_from_above = False
        self.ring_returned = False

    def close_cycle(self, now: int) -> None:
        self.fim.end_cycle(now)

    def recv_report(self, basic, link) -> None:
        self.reporters.add(basic.index)
        self.fim.frame_capture[basic.index] = link
        self.reports += 1
        for aux in self.aux:                  # эхо всем базовым
            aux.to_basic(1)
        # два спайка от разных базовых внутри цикла -> консолидация сразу

    # ================= кольцо =================
    def ring_return(self) -> None:
        """Возбуждение дошло до головного нейрона по кольцу."""
        now = self.net.now
        self.ring_returned = True
        if not self.is_consolidated:
            return
        self.last_activity = now
        self.recognitions += 1
        self.fire_up()
        self.net.instinct.on_head_spike(self)

    # ================= фиксация =================
    def consolidate(self) -> None:
        cfg = self.net.cfg
        self.is_consolidated = True
        self.consolidations += 1
        # Смысл памяти фиксируем сразу — дедупликация должна видеть её
        # до того, как aux-спайки доведут связи до STATE_2_PERM.
        self.fim.snapshot = self.fim.candidate_text(sorted(self.fim.frame_capture))
        for index, link in self.fim.frame_capture.items():
            basic = self.fim.basics[index - 1]
            basic.temp_links.add(link)
            basic.pending_fix = True
            if link.state == STATE_1:
                link.state = STATE_2_TEMP
        for aux in self.aux:
            aux.to_basic(cfg.perm_aux)   # 3 спайка подряд -> STATE_2_PERM

    # ================= выдача =================
    def grant_permission(self) -> None:
        """2 спайка подряд от Инстинкта: разрешение на выдачу."""
        now = self.net.now
        self.permission_until = now + self.fim.cycle
        for basic in self.fim.basics:
            basic.aux_count = 0
            # Разрешение действительно сразу, не ожидая доставки aux-спайков:
            # иначе первый же проход выдачи уходил в пустоту.
            basic.permission_until = self.permission_until
        self.send_permission()

    def on_double_instinct(self) -> None:
        if not self.is_consolidated or not self.active():
            return
        self.grant_permission()
        self.fim.generation_pass()

    def send_permission(self) -> None:
        for aux in self.aux:
            aux.to_basic(2)

    def active(self, now: int | None = None) -> bool:
        now = self.net.now if now is None else now
        return bool(
            self.ring_returned
            or self.activation_from_above
            or now - self.last_activity <= self.net.cfg.activation_window_ms
        )

    def recv_down(self, link) -> None:
        """Возбуждение от верхнего уровня: активация и каскад вниз."""
        now = self.net.now
        self.activation_from_above = True
        self.last_activity = now
        if not self.is_consolidated:
            return
        self.grant_permission()
        self.fim.generation_pass()

    def fire_up(self, span=None) -> None:
        for link in self.up_links:
            link.fire_up(span)

    def label(self) -> str:
        return self.fim.gid
