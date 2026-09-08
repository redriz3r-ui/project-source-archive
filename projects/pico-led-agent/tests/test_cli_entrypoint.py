import subprocess
import sys
import unittest


class CliEntrypointTests(unittest.TestCase):
    def test_module_invocation_runs_main(self):
        result = subprocess.run(
            [sys.executable, "-m", "led_agent.cli", "--transport", "sim", "show", "eyes"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("simulated", result.stdout)
        self.assertIn('"cmd": "play"', result.stdout)


if __name__ == "__main__":
    unittest.main()
