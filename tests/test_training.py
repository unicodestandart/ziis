"""Долгое обучение сходится к правильному варианту.

Без предустановленных слогов уровень 1 учит и перекрывающиеся пары
(«ам» из «мама»), поэтому слово может собраться не тем. Предустановка
канонических слогов задаёт словарь, на котором верхние уровни собирают
слово и фразу; цепочка становится памятью только после подтверждения
в другом цикле.
"""

import unittest

from ziis.config import Config
from ziis.system import ZIIS

TEXT = "мама мыла раму"
BOOT = ("ма", "мы", "ла", "ра", "му")


def expand(fim, depth: int = 4) -> str:
    if depth == 0:
        return "?"
    parts = []
    for basic in fim.basics:
        if not basic.perm_links:
            continue
        link = sorted(basic.perm_links, key=lambda l: l.uid)[0]
        low = link.lower
        parts.append(expand(low.fim, depth - 1) if hasattr(low, "fim") else low.char)
    return "".join(parts)


def slots(fim) -> list[str]:
    out = []
    for basic in fim.basics:
        if not basic.perm_links:
            continue
        link = sorted(basic.perm_links, key=lambda l: l.uid)[0]
        low = link.lower
        out.append(expand(low.fim) if hasattr(low, "fim") else low.char)
    return out


def render(fim) -> str:
    return (" " if fim.level.index >= 3 else "").join(slots(fim))


class TrainingConvergenceTest(unittest.TestCase):
    def _train(self, epochs: int):
        net = ZIIS(
            Config(
                levels=3,
                level_sizes=(512, 256, 64),
                fim_groups=1,
                bootstrap_syllables=BOOT,
            )
        )
        start = 500
        for _ in range(epochs):
            net.remember(TEXT, start=start, settle_ms=1200)
            start = net.now + 400
        return net

    def test_first_epoch_does_not_freeze_a_level(self):
        net = self._train(1)
        self.assertEqual(net.levels[1].consolidated, [])

    def test_long_training_keeps_the_correct_word(self):
        net = self._train(8)
        words = [expand(f) for f in net.levels[1].consolidated]
        self.assertIn("мама", words)
        # Правильная память должна узнавать слово при первом предъявлении.
        memory = next(f for f in net.levels[1].consolidated if expand(f) == "мама")
        before = memory.head.recognitions
        net.type_text("мама")
        net.run(net.now + 600)
        self.assertGreater(memory.head.recognitions, before)

    def test_bootstrap_builds_the_phrase(self):
        net = ZIIS(
            Config(
                levels=3,
                level_sizes=(96, 72, 56),
                fim_groups=1,
                bootstrap_syllables=BOOT,
            )
        )
        start = 500
        for _ in range(10):
            net.remember(TEXT + " ", start=start, settle_ms=900)
            start = net.now + 400

        words = [render(f) for f in net.levels[1].consolidated]
        for word in ("мама", "мыла", "раму"):
            self.assertIn(word, words)

        phrases = [render(f) for f in net.levels[2].consolidated]
        self.assertIn(TEXT, phrases)

        memory = next(f for f in net.levels[2].consolidated if render(f) == TEXT)
        before = memory.head.recognitions
        net.type_text(TEXT + " ")
        net.run(net.now + 2500)
        self.assertGreater(memory.head.recognitions, before)

        thought = net.recall(TEXT)
        self.assertEqual(thought.replace(" ", ""), TEXT.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
