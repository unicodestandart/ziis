import unittest

from tests.helpers import isolate, make_net, wire


class CaptureTest(unittest.TestCase):
    def test_each_basic_keeps_its_own_ordinal(self):
        net = make_net(min_reports=4)
        fim = isolate(net)
        wire(net, fim, "мама")
        net.type_text("мама")
        net.run(350)

        for i, expected in enumerate("мама"):
            basic = fim.basics[i]
            self.assertIsNotNone(basic.frame_capture, f"B{i + 1} ничего не захватил")
            self.assertEqual(basic.frame_capture.lower.char, expected)

    def test_shutter_prevents_overwrite(self):
        net = make_net(min_reports=99)  # фиксация не наступит, кадры идут подряд
        fim = isolate(net)
        wire(net, fim, "мама")
        net.type_text("мамамама")       # два подряд идущих четырёхбуквенных такта
        net.run(390)                    # первый кадр завершён, второй ещё не начался

        self.assertEqual([b.captures for b in fim.basics], [1, 1, 1, 1])
        captured = "".join(b.frame_capture.lower.char for b in fim.basics)
        self.assertEqual(captured, "мама")

    def test_frame_captures_next_group(self):
        net = make_net(min_reports=99)
        fim = isolate(net)
        wire(net, fim, "мама")
        net.type_text("мама" * 4)
        net.run(1600)  # второй цикл 1000 мс, ещё раз по четыре буквы
        counts = [b.captures for b in fim.basics]
        self.assertGreaterEqual(sum(counts), 7, counts)   # второй кадр захвачен

    def test_one_spike_is_captured_by_one_neuron_only(self):
        net = make_net(min_reports=99)
        fim = isolate(net)
        wire(net, fim, "мама")
        # все четыре базовых слушают одну и ту же букву
        from ziis.links import UpDownLink

        for basic in fim.basics[1:]:
            UpDownLink(net, net.elements["м"], basic, net.cfg.updown_delay_ms)

        net.type_text("м", start=0)
        net.run(390)
        self.assertEqual(sum(b.captures for b in fim.basics), 1)

    def test_wave_without_input_captures_nothing(self):
        net = make_net()
        fim = isolate(net)
        net.run(500)
        self.assertEqual([b.captures for b in fim.basics], [0, 0, 0, 0])


if __name__ == "__main__":
    unittest.main()
