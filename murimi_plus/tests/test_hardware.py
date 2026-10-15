import os
import tempfile
import unittest

from murimi_plus.hardware import choose


class HardwareTests(unittest.TestCase):
    def test_normal_laptop(self):
        args, why = choose("/app", ram_gb=8, cpus=8, force_low=False)
        self.assertEqual(args[2:], ["-t", "4", "-c", "4096"])
        self.assertTrue(args[1].endswith("qwen2.5-1.5b-instruct-q4_k_m.gguf"))

    def test_low_ram_shrinks_context_and_threads(self):
        args, why = choose("/app", ram_gb=4, cpus=2, force_low=False)
        self.assertEqual(args[2:], ["-t", "2", "-c", "2048"])
        self.assertIn("low-end", why)

    def test_lite_model_only_if_present(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("lite", choose(d, ram_gb=3, cpus=2, force_low=False)[0][1])
            os.makedirs(os.path.join(d, "model"))
            open(os.path.join(d, "model", "lite.gguf"), "w").close()
            self.assertTrue(choose(d, ram_gb=3, cpus=2, force_low=False)[0][1].endswith("lite.gguf"))
            self.assertNotIn("lite", choose(d, ram_gb=8, cpus=8, force_low=False)[0][1])

    def test_unknown_ram_keeps_normal(self):
        self.assertIn("4096", choose("/app", ram_gb=None, cpus=4, force_low=False)[0])


if __name__ == "__main__":
    unittest.main()
