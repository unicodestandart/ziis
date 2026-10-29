import unittest

from ziis.system import ZIIS
from tests.helpers import isolate, make_net, wire


class DeterminismTest(unittest.TestCase):
    def test_two_runs_are_identical(self):
        def run():
            net = make_net(seed=777)
            isolate(net)
            wire(net, net.levels[0].fims[0], "мама")
            net.remember("мама")
            return net.monitor.text(), net.stats()["events"], net.report()

        first = run()
        second = run()
        self.assertEqual(first, second)

    def test_different_seed_gives_different_topology(self):
        a = ZIIS(seed_config(1))
        b = ZIIS(seed_config(2))
        self.assertNotEqual(
            [id(l) for l in a.levels[0].fims[0].basics[0].in_links][:1],
            [id(l) for l in b.levels[0].fims[0].basics[0].in_links][:1],
        )


def seed_config(seed):
    from ziis.config import Config

    return Config(seed=seed, levels=1, level_sizes=(16,), letter_scale=1)


if __name__ == "__main__":
    unittest.main()
