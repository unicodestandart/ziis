import unittest

from ziis.links import UpDownLink
from ziis.motor import MotorElement
from tests.helpers import force_perm, isolate, make_net, wire


class MotorTest(unittest.TestCase):
    def _net(self):
        net = make_net(motor_enabled=True)
        fim = isolate(net)
        wire(net, fim, "мама")
        net.remember("мама", settle_ms=500)

        motor = MotorElement(net, "рука")
        link = UpDownLink(net, motor, fim.basics[0], 0)
        force_perm(fim, 0, link)
        return net, fim, motor

    def test_without_target_instinct_only_planning(self):
        net, fim, motor = self._net()
        net.play(fim)
        self.assertEqual(motor.plans, 1)
        self.assertEqual(motor.actuations, 0)

    def test_target_instinct_opens_gate(self):
        net, fim, motor = self._net()
        net.motivation.excite_target(hold_ms=5000)
        net.play(fim)
        self.assertEqual(motor.actuations, 1)
        self.assertEqual(motor.plans, 0)

    def test_reciprocal_inhibition(self):
        net, _fim, _motor = self._net()
        motivation = net.motivation

        self.assertTrue(motivation.excite_target(hold_ms=5000))
        # сразу после возбуждения «Ц» стресс заторможен
        self.assertFalse(motivation.excite_stress(hold_ms=5000))
        self.assertTrue(motivation.target_active())

        # через окно торможения стресс пробивает и гасит цель
        net.run(net.now + 500)
        self.assertTrue(motivation.excite_stress(hold_ms=5000))
        self.assertTrue(motivation.stress_active())
        self.assertFalse(motivation.target_active())

    def test_stress_blocks_motor_shutter(self):
        net, fim, motor = self._net()
        net.motivation.excite_stress(hold_ms=5000)
        net.play(fim)
        self.assertEqual(motor.actuations, 0)
        self.assertEqual(motor.plans, 1)


if __name__ == "__main__":
    unittest.main()
