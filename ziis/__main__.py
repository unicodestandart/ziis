"""CLI текстового стенда ЗИИС."""

from __future__ import annotations

import argparse
import sys
import time
import unittest

from .config import Config
from .system import ZIIS


def build_config(
    levels: int,
    seed: int,
    groups: int | None = None,
    bootstrap: tuple[str, ...] = (),
) -> Config:
    base = Config()
    sizes = list(base.level_sizes)
    while len(sizes) < levels:
        sizes.append(max(4, sizes[-1] // 2))
    return Config(
        levels=levels,
        level_sizes=tuple(sizes[:levels]),
        seed=seed,
        fim_groups=base.fim_groups if groups is None else groups,
        bootstrap_syllables=bootstrap,
    )


def cmd_demo(args) -> int:
    bootstrap = tuple(
        s.strip() for s in args.bootstrap.split(",") if s.strip()
    )
    cfg = build_config(args.levels, args.seed, args.groups, bootstrap)
    started = time.perf_counter()
    net = ZIIS(cfg)
    build_ms = int((time.perf_counter() - started) * 1000)

    print("=" * 78)
    print("ЗИИС — зооморфная искусственная интеллектуальная система")
    print(f"уровней: {cfg.levels}, ФИМ по уровням: {cfg.level_sizes[:cfg.levels]}")
    print(f"групп ФИМ: {cfg.fim_groups}, предустановленные слоги: {cfg.bootstrap_syllables or 'нет'}")
    print(f"сборка сети: {build_ms} мс, синапсов: {_link_count(net)}")
    print("=" * 78)

    text = args.text
    epochs = max(1, args.epochs)
    print(f"\n[ВХОД] {text!r}  (буфер клавиатуры, шаг {cfg.element_step_ms} мс)")
    started = time.perf_counter()
    for _ in range(epochs):
        # Пробел в конце — граница между предъявлениями: без него конец
        # фразы слипается с началом следующей и верхние уровни пишут мусор.
        net.remember(text + " ", settle_ms=900)
    sim_ms = int((time.perf_counter() - started) * 1000)

    seen = net.monitor.text("perception")
    print(f"\n[ЧТО СИСТЕМА УВИДЕЛА] {seen[:len(text)]!r}  (предъявлений: {epochs})")
    print(f"\n[ЗАПОМНЕНО]  (симуляция {sim_ms} мс, событий {net.clock.processed})")
    print(net.report())

    prompt = text if args.recall is None else args.recall
    print(f"\n[МЫШЛЕНИЕ]  предъявлено {prompt!r}")
    thought = net.recall(prompt, prefer_level=1)
    memory = net.last_memory
    label = f"{memory.gid} {memory.pattern_text()!r}" if memory else "нет активной памяти"
    print(f"  воспроизведение помнящего ФИМ: {thought!r}  <- {label}")
    cascade = net.recall(prompt)
    top = net.last_memory
    top_label = f"{top.gid} {top.pattern_text()!r}" if top else "нет"
    print(f"  каскад от верхнего уровня ({top_label}): {cascade[:100]!r}")
    parallel = net.recall_all(prompt)
    shown = parallel[:120]
    tail = "..." if len(parallel) > len(shown) else ""
    print(f"  параллельный залп всех активных очагов ({len(parallel)} символ.): {shown!r}{tail}")
    print("\n[СОСТОЯНИЕ ПОСЛЕ ВОСПРОИЗВЕДЕНИЯ]")
    print(net.report())

    print("\n[СТАТИСТИКА]")
    print(
        f"  тактов инстинкта: {net.instinct.ticks}, "
        f"двойных импульсов: {net.instinct.double_pulses}"
    )
    print(f"  всего событий: {net.clock.processed}")
    return 0


def _link_count(net) -> int:
    total = 0
    for level in net.levels:
        for basic in level.basics:
            total += len(basic.in_links)
    return total


def cmd_selftest(_args) -> int:
    loader = unittest.TestLoader()
    suite = loader.discover("tests", top_level_dir=".")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ziis",
        description="Текстовый стенд ЗИИС на спайковых автоматах (архитектура В. А. Сычёва)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="записать текст и воспроизвести его из памяти")
    demo.add_argument("--text", default="мама мыла раму", help="текст для запоминания")
    demo.add_argument("--levels", type=int, default=9, help="число уровней ФИМ (1..9)")
    demo.add_argument(
        "--epochs", type=int, default=24, help="сколько раз предъявить текст при обучении"
    )
    demo.add_argument("--seed", type=int, default=Config.seed, help="зерно топологии")
    demo.add_argument(
        "--groups", type=int, default=None, help="сколько групп ФИМ работают по очереди"
    )
    demo.add_argument(
        "--bootstrap",
        default="",
        help="предустановленные слоги через запятую, например: ма,мы,ла,ра,му",
    )
    demo.add_argument(
        "--recall", default=None, help="что предъявить системе (по умолчанию весь текст)"
    )
    demo.set_defaults(func=cmd_demo)

    test = sub.add_parser("selftest", help="прогнать тесты")
    test.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
