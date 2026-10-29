import unittest

from tests.helpers import isolate, make_net, wire


class RecognitionTest(unittest.TestCase):
    def _learned(self):
        net = make_net(min_reports=4)
        fim = isolate(net)
        wire(net, fim, "мама")
        net.remember("мама", settle_ms=500)
        self.assertTrue(fim.head.is_consolidated)
        return net, fim

    def test_known_sequence_is_recognised(self):
        net, fim = self._learned()
        before = fim.head.recognitions
        net.type_text("мама", start=2000)
        net.run(2600)
        self.assertEqual(fim.head.recognitions, before + 1)

    def test_unknown_sequence_is_not_recognised(self):
        net, fim = self._learned()
        before = fim.head.recognitions
        net.type_text("папа", start=2000)
        net.run(2600)
        self.assertEqual(fim.head.recognitions, before)

    def test_broken_tail_is_not_recognised(self):
        net, fim = self._learned()
        before = fim.head.recognitions
        net.type_text("мамм", start=2000)
        net.run(2600)
        self.assertEqual(fim.head.recognitions, before)

    def test_recognition_reaches_upper_level(self):
        net = make_net(levels=2, level_sizes=(4, 4), upper_density_permille=1000)
        lower = isolate(net, 1, 0)
        wire(net, lower, "мама")
        # головной нейрон нижнего уровня -> базовые нейроны верхнего
        from ziis.links import UpDownLink

        upper = net.levels[1].fims[0]
        for i, basic in enumerate(upper.basics):
            UpDownLink(net, lower.head, basic, net.cfg.updown_delay_ms)

        net.remember("мама", settle_ms=500)
        before = sum(b.ups_received for b in upper.basics)
        net.type_text("мама", start=2000)
        net.run(2600)
        # узнавание нижнего уровня доходит до базовых нейронов верхнего
        self.assertGreater(sum(b.ups_received for b in upper.basics), before)


if __name__ == "__main__":
    unittest.main()
