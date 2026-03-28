import unittest
from unittest.mock import patch

import matplotlib
import numpy as np

matplotlib.use("Agg")

from scripts import plot_memory_only


class PlotMemoryOnlyTests(unittest.TestCase):
    def test_default_output_path_uses_memory_plots_directory(self):
        path = plot_memory_only.default_output_path("abc123")

        self.assertEqual(path.name, "abc123.png")
        self.assertEqual(path.parent.name, "memory_plots")

    def test_load_run_metrics_prefers_final_summary_metrics(self):
        simulation = {
            "config": {
                "llm_model": "claude-sonnet-4-6",
            },
            "final_summary": {
                "ablation_metrics": {
                    "resource_stock_over_time": [120, 118, 115],
                    "gini_over_time": [0.0, 0.1, 0.2],
                }
            },
            "rounds": [
                {"world_state": {"resource_depot": 999, "gini": 0.9}},
            ],
        }

        with patch("scripts.plot_memory_only.db.get_simulation", return_value=simulation):
            run = plot_memory_only.load_run_metrics("abc123")

        self.assertEqual(run["simulation_id"], "abc123")
        self.assertEqual(run["model_name"], "claude-sonnet-4-6")
        self.assertEqual(run["resource_stock_over_time"], [120, 118, 115])
        self.assertEqual(run["gini_over_time"], [0.0, 0.1, 0.2])

    def test_load_run_metrics_reconstructs_from_rounds_when_summary_missing(self):
        simulation = {
            "config": {
                "llm_model": "gpt-5.4",
            },
            "final_summary": {},
            "rounds": [
                {"world_state": {"resource_depot": 120, "gini": 0.0}},
                {"world_state": {"resource_depot": 116, "gini": 0.2}},
                {"world_state": {"resource_depot": 110, "gini": 0.3}},
            ],
        }

        with patch("scripts.plot_memory_only.db.get_simulation", return_value=simulation):
            run = plot_memory_only.load_run_metrics("def456")

        self.assertEqual(run["model_name"], "gpt-5.4")
        self.assertEqual(run["resource_stock_over_time"], [120, 116, 110])
        self.assertEqual(run["gini_over_time"], [0.0, 0.2, 0.3])

    def test_build_plot_single_run_draws_exact_series_and_uses_model_label(self):
        run = {
            "simulation_id": "run-1",
            "model_name": "claude-sonnet-4-6",
            "resource_stock_over_time": [120, 110, 100],
            "gini_over_time": [0.0, 0.1, 0.2],
        }

        fig, axes = plot_memory_only.build_plot(run, "Single Run")

        stock_line = axes[0, 0].lines[0]
        gini_line = axes[0, 1].lines[0]
        np.testing.assert_allclose(stock_line.get_ydata(), np.array([120, 110, 100]))
        np.testing.assert_allclose(gini_line.get_ydata(), np.array([0.0, 0.1, 0.2]))
        self.assertEqual(stock_line.get_label(), "Memory ON (claude-sonnet-4-6)")
        self.assertEqual(len(axes[0, 0].collections), 0)
        self.assertEqual(len(axes[0, 1].collections), 0)
        plot_memory_only.plt.close(fig)

    def test_save_simulation_plot_default_title_uses_model_name(self):
        simulation = {
            "config": {
                "llm_model": "claude-sonnet-4-6",
            },
            "final_summary": {
                "ablation_metrics": {
                    "resource_stock_over_time": [120, 118, 115],
                    "gini_over_time": [0.0, 0.1, 0.2],
                }
            },
            "rounds": [],
        }

        with patch("scripts.plot_memory_only.db.get_simulation", return_value=simulation):
            with patch("scripts.plot_memory_only.build_plot") as build_plot:
                with patch("scripts.plot_memory_only.plt.savefig"):
                    with patch("scripts.plot_memory_only.plt.close"):
                        plot_memory_only.save_simulation_plot("abc123")

        _, plot_title = build_plot.call_args[0]
        self.assertEqual(plot_title, "Memory ON Run: claude-sonnet-4-6")

    def test_load_run_metrics_raises_clear_error_for_invalid_id(self):
        with patch("scripts.plot_memory_only.db.get_simulation", side_effect=ValueError("bad object id")):
            with self.assertRaisesRegex(ValueError, "could not be loaded"):
                plot_memory_only.load_run_metrics("not-an-object-id")


if __name__ == "__main__":
    unittest.main()
