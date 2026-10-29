import unittest

from ziis.clock import EventClock


class ClockTest(unittest.TestCase):
    def test_ordering_by_time_and_sequence(self):
        clock = EventClock()
        order = []
        clock.schedule(10, order.append, "b")
        clock.schedule(5, order.append, "a")
        clock.schedule(10, order.append, "c")
        clock.run()
        self.assertEqual(order, ["a", "b", "c"])

    def test_integer_time_only(self):
        clock = EventClock()
        clock.schedule(100, lambda: None)
        clock.run()
        self.assertEqual(clock.now, 100)
        self.assertIsInstance(clock.now, int)

    def test_negative_delay_rejected(self):
        clock = EventClock()
        with self.assertRaises(ValueError):
            clock.schedule(-1, lambda: None)

    def test_run_until_stops_early(self):
        clock = EventClock()
        fired = []
        clock.schedule(500, fired.append, "late")
        clock.run(until=100)
        self.assertEqual(fired, [])
        self.assertEqual(clock.now, 100)


if __name__ == "__main__":
    unittest.main()
