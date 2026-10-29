import unittest

from tests.helpers import make_net


class InstinctTest(unittest.TestCase):
    def test_three_letters_in_window_start_attention(self):
        net = make_net(instinct_threshold=3, instinct_hold_ms=600)
        net.type_text("мам")
        net.run(250)

        self.assertEqual(net.instinct.triggers, 1)
        self.assertTrue(net.instinct.ticking)
        self.assertGreater(net.instinct.ticks, 0)

    def test_two_letters_are_not_enough(self):
        net = make_net(instinct_threshold=3)
        net.type_text("ма")
        net.run(300)
        self.assertEqual(net.instinct.triggers, 0)

    def test_window_ends_with_double_pulse(self):
        net = make_net(instinct_threshold=3, instinct_hold_ms=400)
        net.type_text("мам")
        net.run(2000)
        self.assertEqual(net.instinct.double_pulses, 1)
        self.assertFalse(net.instinct.ticking)

    def test_reciprocal_support_from_network(self):
        net = make_net(instinct_threshold=3)
        self.assertFalse(net.instinct.ticking)
        net.instinct.on_head_spike(None)
        self.assertTrue(net.instinct.ticking)
        self.assertEqual(net.instinct.double_pulses, 0)

    def test_clocks_are_250ms_apart(self):
        net = make_net(instinct_threshold=1, instinct_hold_ms=1000)
        net.type_text("мама")
        net.run(1200)
        # ровно один такт на 250 мс окна активности
        self.assertGreaterEqual(net.instinct.ticks, 3)


if __name__ == "__main__":
    unittest.main()
