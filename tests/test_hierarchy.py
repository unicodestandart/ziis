"""Уровень 2 собирает слово из слогов, записанных на уровне 1.

Дубль одной и той же памяти уровню не нужен: второй ФИМ с тем же «ма»
остаётся свободным. Слово собирается, когда один и тот же слог приходит
в два слота подряд — «ма» + «ма».
"""

import unittest

from tests.helpers import isolate, make_net, wire


class HierarchyTest(unittest.TestCase):
    def _net(self):
        net = make_net(levels=2, level_sizes=(4, 4), min_reports=2)
        low_a = isolate(net, 1, 0)
        low_b = isolate(net, 1, 1)
        wire(net, low_a, "ма")
        wire(net, low_b, "ма")      # та же самая память — копия не нужна

        from ziis.links import UpDownLink

        high = isolate(net, 2, 0)
        # один слог в двух слотах: первый и второй слог слова
        UpDownLink(net, low_a.head, high.basics[0], net.cfg.updown_delay_ms)
        UpDownLink(net, low_a.head, high.basics[1], net.cfg.updown_delay_ms)
        return net, low_a, low_b, high

    def _expanded(self, fim) -> str:
        parts = []
        for basic in fim.basics:
            if not basic.perm_links:
                parts.append("·")
                continue
            link = sorted(basic.perm_links, key=lambda l: l.uid)[0]
            parts.append(link.lower.fim.pattern_text().replace("·", ""))
        return "".join(parts).replace("·", "")

    def test_duplicate_memories_are_both_fixed(self):
        net, low_a, low_b, _high = self._net()
        net.type_text("мама")
        net.run(1000)

        self.assertTrue(low_a.head.is_consolidated)
        self.assertTrue(low_b.head.is_consolidated)

    def test_two_syllables_become_a_word(self):
        net, _low_a, _low_b, high = self._net()
        net.type_text("мама")
        net.run(1200)

        self.assertTrue(high.head.is_consolidated)
        self.assertEqual(self._expanded(high), "мама")


if __name__ == "__main__":
    unittest.main()
