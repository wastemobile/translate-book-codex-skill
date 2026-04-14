import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import parallelism  # noqa: E402


class ParallelismTests(unittest.TestCase):
    def test_numeric_parallelism_is_clamped_to_hard_limit(self):
        self.assertEqual(parallelism.resolve_parallelism("9"), 3)
        self.assertEqual(parallelism.resolve_parallelism("0"), 1)

    def test_auto_parallelism_prefers_single_worker_when_load_is_high(self):
        with mock.patch.object(parallelism.os, "cpu_count", return_value=8), mock.patch.object(
            parallelism.os, "getloadavg", return_value=(7.0, 7.0, 7.0)
        ):
            self.assertEqual(parallelism.resolve_parallelism("auto"), 1)

    def test_auto_parallelism_uses_conservative_ceiling_when_load_is_low(self):
        with mock.patch.object(parallelism.os, "cpu_count", return_value=16), mock.patch.object(
            parallelism.os, "getloadavg", return_value=(1.0, 1.0, 1.0)
        ):
            self.assertEqual(parallelism.resolve_parallelism("auto"), 2)


if __name__ == "__main__":
    unittest.main()
