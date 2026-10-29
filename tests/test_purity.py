import pathlib
import unittest

from ziis.config import Config

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANNED = (
    "numpy",
    "torch",
    "tensorflow",
    "sklearn",
    "backprop",
    "gradient",
    "float(",
    "math.exp",
    "math.log",
    "math.tanh",
    "loss",
    "optimizer",
    "random.gauss",
    "random.uniform",
)


class PurityTest(unittest.TestCase):
    def test_no_banned_constructs_in_sources(self):
        offenders = []
        for path in sorted((ROOT / "ziis").glob("*.py")):
            source = path.read_text(encoding="utf-8").lower()
            for token in BANNED:
                if token in source:
                    offenders.append(f"{path.name}: {token}")
        self.assertEqual(offenders, [], f"запрещённые конструкции: {offenders}")

    def test_all_numeric_config_values_are_int(self):
        cfg = Config()
        for name, value in cfg.__dict__.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                continue
            if isinstance(value, (tuple, list)):
                self.assertTrue(
                    all(isinstance(v, int) for v in value), f"{name} содержит не int"
                )
                continue
            self.fail(f"{name} = {value!r} не является целым")

    def test_timing_is_integer_milliseconds(self):
        cfg = Config()
        for level in range(1, cfg.levels + 1):
            for value in (
                cfg.cycle_ms(level),
                cfg.frame_ms(level),
                cfg.exposure_for(level),
                cfg.cycle_ms(level),
            ):
                self.assertIsInstance(value, int)
                self.assertGreater(value, 0)


if __name__ == "__main__":
    unittest.main()
