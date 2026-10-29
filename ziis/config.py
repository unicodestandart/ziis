"""Единая конфигурация ЗИИС: только целочисленные константы и дискретные флаги.

Никаких весов, float, матриц и функций потерь в системе нет и быть не может.
Вся временная база — целые миллисекунды.
"""

from __future__ import annotations

from dataclasses import dataclass, replace as _replace

SPACE = " "
LETTERS = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
NOISE_CHARS = ("#", "@", "&", "*", "÷")

# Частота встречаемости символов в русском языке, промилле.
# Используется ровно для одного: число выходящих из Элемента синапсов
# прямо пропорционально частоте буквы в языке.
FREQ_PERMILLE = {
    " ": 175,
    "о": 90,
    "е": 72,
    "а": 66,
    "и": 62,
    "н": 53,
    "т": 52,
    "с": 45,
    "р": 40,
    "в": 38,
    "л": 35,
    "к": 28,
    "м": 26,
    "д": 25,
    "п": 23,
    "у": 21,
    "я": 17,
    "ы": 16,
    "ь": 14,
    "г": 14,
    "з": 13,
    "б": 13,
    "ч": 12,
    "й": 10,
    "х": 8,
    "ж": 7,
    "ю": 5,
    "ш": 5,
    "ц": 4,
    "щ": 3,
    "э": 3,
    "ф": 2,
    "ъ": 1,
    "ё": 1,
}

MODE_WRITE = "write"
MODE_RECOGNIZE = "recognize"
MODE_GENERATE = "generate"


@dataclass(frozen=True)
class Config:
    # --- общее ---
    seed: int = 20261028
    n_basic: int = 4
    levels: int = 9
    level_sizes: tuple[int, ...] = (96, 72, 56, 44, 36, 28, 22, 18, 14)
    max_events: int = 20_000_000

    # --- уровень 0: тактирование входа ---
    element_step_ms: int = 100    # следующий символ в сеть через 100 мс
    exposure_ms: int = 225        # окно экспозиции «затвора» (п. 3.2 ТЗ)
    element_cycle_ms: int = 250   # T_цикл(0) = один такт инстинкта

    # --- инстинкт внимания «В» ---
    instinct_period_ms: int = 250
    instinct_window_ms: int = 300
    instinct_threshold: int = 3
    instinct_hold_ms: int = 1000
    reciprocal_hold_ms: int = 600
    permission_hold_ms: int = 900
    activation_window_ms: int = 2000

    # --- синапсы ---
    updown_delay_ms: int = 1
    aux_delay_ms: int = 1

    # --- консолидация ---
    min_reports: int = 2   # минимум разных базовых нейронов в цикле
    max_slots: int = 2     # слот-пара: каждый уровень складывает два сигнала нижнего
    # Сколько групп ФИМ работают по очереди: свободные ФИМ не все сразу
    # бросаются на первое слово, а сменяются от цикла к циклу.
    fim_groups: int = 4
    # Пробел закрывает слово на этом уровне: кадр оценивается и начинается
    # заново, поэтому слово не сшивается с соседним. 0 — не разрывать.
    word_break_level: int = 2
    # Слоги, предустановленные на уровне 1: с них системе легче начать,
    # как будто они уже выучены. Пустой кортеж — ничего не предустанавливать.
    bootstrap_syllables: tuple[str, ...] = ()
    # Если слоги предустановлены, уровень 1 замораживается: он больше
    # не пишет мусор, и верхние уровни учатся на готовых слогах.
    bootstrap_freeze: bool = True
    level_slots: tuple[int, ...] = (2, 2, 4, 4, 4, 4, 4, 4, 4)
    min_support: int = 2   # сколько циклов должна подтвердиться цепочка
    temp_aux: int = 2      # 2 спайка -> STATE_2_TEMP
    perm_aux: int = 3      # 3 спайка -> STATE_2_PERM

    # --- топология межуровневых связей ---
    letter_scale: int = 10
    # Плотность связей верхних уровней: каждый базовый нейрон должен получать
    # возбуждение от большинства головных нейронов нижнего уровня. При 250‰
    # пары «слово1 + слово2» не находили себе ФИМ, и спайки не шли выше.
    upper_density_permille: int = 800

    # --- моторный контур ---
    motor_enabled: bool = False

    # ------------------------------------------------------------------
    def cycle_ms(self, level: int) -> int:
        """Цикл консолидации уровня L: 250 мс × L.

        L1 = 250 мс, L2 = 500 мс, L3 = 750 мс, L4 = 1000 мс,
        L5 = 1250 мс, ... L9 = 2250 мс.
        """
        return self.element_cycle_ms * level

    def ticks_per_cycle(self, level: int) -> int:
        """Сколько тактов Инстинкта (250 мс) длится цикл уровня L."""
        return self.cycle_ms(level) // self.instinct_period_ms

    def frame_ms(self, level: int) -> int:
        """Один цикл консолидации = один кадр записи."""
        return self.cycle_ms(level)

    def slots_for(self, level: int) -> int:
        if 1 <= level <= len(self.level_slots):
            return self.level_slots[level - 1]
        return self.level_slots[-1]

    def capture_window_ms(self, level: int) -> int:
        return self.cycle_ms(level) + self.element_cycle_ms * max(0, self.slots_for(level) - 2)



    def exposure_for(self, level: int) -> int:
        """Окно экспозиции затвора — 225 мс на любом уровне."""
        return self.exposure_ms

    def min_support_for(self, level: int) -> int:
        """Сколько подтверждений нужно уровню.

        Нижние уровни видят один и тот же слог и слово сотни раз, и без
        повторного подтверждения они забиваются случайными обрывками.
        Верхние уровни видят сюжет редко: требовать двух его предъявлений —
        значит вообще никогда не записать ни одной длинной последовательности.
        """
        return self.min_support if level <= 3 else 1

    def size_of(self, level: int) -> int:
        if 1 <= level <= len(self.level_sizes):
            return self.level_sizes[level - 1]
        return self.level_sizes[-1]

    def replace(self, **kwargs) -> "Config":
        return _replace(self, **kwargs)


def lite_config(**kwargs) -> Config:
    """Компактная конфигурация для тестов и быстрых прогонов."""
    base = dict(
        levels=1,
        level_sizes=(8,),
        letter_scale=0,
        upper_density_permille=500,
        instinct_hold_ms=400,
        reciprocal_hold_ms=400,
        permission_hold_ms=600,
    )
    base.update(kwargs)
    return Config(**base)
