import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import run_simulation


class AutoPlotTests(unittest.TestCase):
    def test_auto_save_memory_plot_uses_logger_simulation_id(self):
        logger = type("LoggerStub", (), {"simulation_id": "abc123"})()
        scenario = {"simulation": {"name": "Commons Test"}}

        with patch(
            "scripts.plot_memory_only.save_simulation_plot",
            return_value=Path("memory_plots/abc123.png"),
        ) as save_plot:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                destination = run_simulation._auto_save_memory_plot(logger, scenario, 15)

        self.assertEqual(destination, Path("memory_plots/abc123.png"))
        save_plot.assert_called_once_with(
            simulation_id="abc123",
            title="Commons Test — Memory ON (15 rounds)",
        )
        self.assertIn("Memory plot saved to: memory_plots/abc123.png", stdout.getvalue())

    def test_auto_save_memory_plot_warns_instead_of_failing(self):
        logger = type("LoggerStub", (), {"simulation_id": "abc123"})()
        scenario = {"simulation": {"name": "Commons Test"}}

        with patch(
            "scripts.plot_memory_only.save_simulation_plot",
            side_effect=RuntimeError("plot broke"),
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                destination = run_simulation._auto_save_memory_plot(logger, scenario, 15)

        self.assertIsNone(destination)
        self.assertIn("Warning: failed to save memory plot", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
