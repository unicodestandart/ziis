import unittest

from ziis.links import STATE_2_PERM, STATE_2_TEMP
from tests.helpers import isolate, make_net, wire


class ConsolidationTest(unittest.TestCase):
    def test_two_reports_are_enough(self):
        net = make_net(min_reports=2)
        fim = isolate(net)
        wire(net, fim, "ма")
        net.remember("ма", settle_ms=500)

        self.assertTrue(fim.head.is_consolidated)
        self.assertEqual(fim.pattern_text(), "ма··")

    def test_three_reports_required_when_configured(self):
        net = make_net(min_reports=3)
        fim = isolate(net)
        wire(net, fim, "ма")
        net.remember("ма", settle_ms=500)

        self.assertFalse(fim.head.is_consolidated)

    def test_single_report_is_not_a_memory(self):
        net = make_net(min_reports=2)
        fim = isolate(net)
        wire(net, fim, "м")
        net.remember("м", settle_ms=500)

        self.assertFalse(fim.head.is_consolidated)

    def test_links_become_permanent(self):
        net = make_net(min_reports=4)
        fim = isolate(net)
        links = wire(net, fim, "мама")
        net.remember("мама", settle_ms=500)

        self.assertTrue(all(link.state == STATE_2_PERM for link in links))
        self.assertTrue(all(b.is_consolidated for b in fim.basics))
        self.assertEqual(
            [len(b.perm_links) for b in fim.basics], [1, 1, 1, 1]
        )

    def test_temporary_state_before_fixation(self):
        net = make_net(min_reports=9)  # фиксация не наступит
        fim = isolate(net)
        links = wire(net, fim, "мама")
        net.remember("мама", settle_ms=40)   # внутри первого кадра

        self.assertFalse(fim.head.is_consolidated)
        # на первом кадре связь успела получить 2 вспомогательных спайка
        self.assertIn(links[0].state, (STATE_2_TEMP, STATE_2_PERM))

    def test_cycle_does_not_consolidate_random_fim(self):
        net = make_net()
        other = net.levels[0].fims[1]
        self.assertFalse(other.head.is_consolidated)


if __name__ == "__main__":
    unittest.main()
