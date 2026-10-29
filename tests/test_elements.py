import unittest

from tests.helpers import isolate, make_net, wire


class ElementTest(unittest.TestCase):
    def test_keypress_goes_up_and_to_monitor(self):
        net = make_net()
        fim = isolate(net)
        wire(net, fim, "мама")
        element = net.elements["м"]
        before = len(element.up_links)

        net.type_text("м")
        net.run(5)

        self.assertGreaterEqual(before, 1)
        self.assertEqual(net.monitor.text("perception"), "м")

    def test_input_buffer_quantises_to_100ms(self):
        net = make_net()
        # физический набор в 10 раз быстрее буфера
        net.type_text("мама", start=0, gap_ms=10)
        net.run(1000)
        times = [e.t for e in net.monitor.events if e.mode == "perception"]
        self.assertEqual(times, [0, 100, 200, 300])

    def test_noise_chars_do_not_reach_instinct(self):
        net = make_net(instinct_threshold=3)
        for char in ("#", "@", "&"):
            self.assertTrue(net.elements[char].is_noise)
            self.assertFalse(net.elements[char].is_instinct)
        net.type_text("###@@@&&&")
        net.run(500)
        self.assertEqual(net.instinct.triggers, 0)


if __name__ == "__main__":
    unittest.main()
