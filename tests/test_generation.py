import unittest

from tests.helpers import isolate, make_net, wire


class GenerationTest(unittest.TestCase):
    def _learned(self):
        net = make_net(min_reports=4)
        fim = isolate(net)
        wire(net, fim, "мама")
        net.remember("мама", settle_ms=500)
        self.assertTrue(fim.head.is_consolidated)
        return net, fim

    def test_downward_wave_reproduces_order(self):
        net, fim = self._learned()
        mark = len(net.monitor)
        text = net.play(fim)

        self.assertEqual(text, "мама")
        self.assertEqual(net.monitor.since(mark, mode="thinking")[0].char, "м")

    def test_down_spikes_in_recorded_order(self):
        net, fim = self._learned()
        net.play(fim)
        self.assertEqual([b.down_fires for b in fim.basics], [1, 1, 1, 1])

    def test_no_permission_no_output(self):
        net, fim = self._learned()
        mark = len(net.monitor)
        net.type_text("мама", start=2000)
        net.run(2600)
        self.assertEqual(net.monitor.since(mark, mode="thinking"), [])

    def test_command_plays_back_active_memory(self):
        net, fim = self._learned()
        mark = len(net.monitor)
        net.type_text("мама", start=2000)
        net.run(2600)
        net.command()
        net.run(net.now + 1000)
        thought = "".join(e.char for e in net.monitor.since(mark, mode="thinking"))
        self.assertIn("мама", thought)


if __name__ == "__main__":
    unittest.main()
