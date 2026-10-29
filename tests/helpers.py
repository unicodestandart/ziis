"""Общие помощники тестов: маленькая сеть и точная разводка синапсов."""

from __future__ import annotations

from ziis.config import lite_config
from ziis.links import STATE_2_PERM, UpDownLink
from ziis.system import ZIIS


def make_net(**kwargs) -> ZIIS:
    params = dict(
        levels=1,
        level_sizes=(4,),
        letter_scale=0,
        upper_density_permille=0,
        instinct_threshold=1,
        min_support=1,        # тесты автомата проверяют фиксацию, а не обучение
        fim_groups=1,        # в тестах автомата очередь групп отключена
        element_cycle_ms=1000,  # тестам нужен кадр из 4 тактов, чтобы осмотреть захваты
    )
    params.update(kwargs)
    return ZIIS(lite_config(**params))


def isolate(net: ZIIS, level: int = 1, index: int = 0):
    """Снять с ФИМ все случайные связи: тест должен быть однозначным."""
    fim = net.levels[level - 1].fims[index]
    for basic in fim.basics:
        for link in list(basic.in_links):
            if link in link.lower.up_links:
                link.lower.up_links.remove(link)
            basic.in_links.remove(link)
    return fim


def wire(net: ZIIS, fim, text: str) -> list:
    """Жёстко подключить символы текста к базовым нейронам B1..Bn по порядку."""
    links = []
    for i, char in enumerate(text):
        links.append(
            UpDownLink(
                net,
                lower=net.elements[char],
                upper=fim.basics[i],
                delay=net.cfg.updown_delay_ms,
            )
        )
    return links


def force_perm(fim, basic_index: int, link) -> None:
    """Пометить связь как постоянную (для тестов нисходящего вывода)."""
    link.state = STATE_2_PERM
    fim.basics[basic_index].perm_links.add(link)
