import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from results import graph_analysis


class GraphAnalysisTests(unittest.TestCase):
    def _render_and_capture_axis(self, render_fn, graph, metrics):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir, "plot.png")
            with patch.object(graph_analysis.plt, "savefig"), patch.object(graph_analysis.plt, "close"):
                render_fn(graph, metrics, output_path)
                figure = plt.gcf()
                self.addCleanup(plt.close, figure)
                return figure.axes[0]

    def test_build_interaction_graph_accumulates_repeated_contacts(self):
        rounds = [
            {"world_state": {"locations": {"Pasture": ["Alice", "Bob"], "River": ["Cara"]}}},
            {"world_state": {"locations": {"Pasture": ["Alice", "Bob", "Cara"]}}},
        ]

        graph = graph_analysis.build_interaction_graph(rounds)

        self.assertEqual(graph["Alice"]["Bob"]["weight"], 2)
        self.assertEqual(graph["Alice"]["Cara"]["weight"], 1)
        self.assertEqual(graph["Bob"]["Cara"]["weight"], 1)

    def test_build_analysis_summary_computes_thesis_ready_metrics(self):
        interaction_graph = graph_analysis.build_interaction_graph(
            [
                {"world_state": {"locations": {"Pasture": ["Alice", "Bob", "Cara"]}}},
                {"world_state": {"locations": {"Pasture": ["Alice", "Bob"]}}},
            ]
        )

        summary = graph_analysis.build_analysis_summary(interaction_graph)

        self.assertAlmostEqual(summary["interaction"]["interaction_density"], 1.0)
        self.assertEqual(summary["interaction"]["total_interaction_events"], 4)

    def test_plot_interaction_dynamics_uses_left_center_annotation_and_larger_legend(self):
        graph = graph_analysis.build_interaction_graph(
            [
                {"world_state": {"locations": {"Pasture": ["Alice", "Bob", "Cara"]}}},
                {"world_state": {"locations": {"Pasture": ["Alice", "Bob"]}}},
            ]
        )
        metrics = graph_analysis.summarize_interaction_dynamics(graph)

        axis = self._render_and_capture_axis(graph_analysis.plot_interaction_dynamics, graph, metrics)

        summary_boxes = [text for text in axis.texts if text.get_text().startswith("Network connectivity:")]
        self.assertEqual(len(summary_boxes), 1)
        summary_box = summary_boxes[0]
        self.assertEqual(summary_box.get_position(), graph_analysis.ANNOTATION_POSITION)
        self.assertEqual(summary_box.get_fontsize(), graph_analysis.ANNOTATION_FONT_SIZE)

        legend = axis.get_legend()
        self.assertIsNotNone(legend)
        self.assertEqual(legend.get_texts()[0].get_fontsize(), graph_analysis.LEGEND_FONT_SIZE)
        self.assertEqual(
            [text.get_text() for text in legend.get_texts()],
            [
                "Edge width = repeated co-presence across rounds",
                "Node size = interaction centrality",
            ],
        )

    def test_render_analysis_artifacts_emits_thesis_and_legacy_filenames(self):
        interaction_graph = graph_analysis.build_interaction_graph(
            [{"world_state": {"locations": {"Pasture": ["Alice", "Bob"]}}}]
        )
        analysis = graph_analysis.build_analysis_summary(interaction_graph)
        analysis["interaction_graph"] = interaction_graph

        with tempfile.TemporaryDirectory() as tmpdir:
            output_paths = graph_analysis.render_analysis_artifacts("run123", analysis, Path(tmpdir))

            self.assertTrue(output_paths["interaction"].exists())
            self.assertTrue(output_paths["interaction_legacy"].exists())

    def test_main_runs_end_to_end_with_mocked_db_payload(self):
        simulation = {
            "status": "completed",
            "rounds": [
                {
                    "world_state": {"locations": {"Pasture": ["Alice", "Bob"]}},
                }
            ],
            "final_summary": {"inventories": {"Alice": 3, "Bob": 1, "Regina": 0}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with patch("results.graph_analysis.load_simulation_from_db", return_value=simulation):
                with patch("results.graph_analysis.Path", side_effect=lambda *parts: Path(tmpdir, *parts)):
                    with patch("sys.stdout", stdout):
                        with patch("sys.argv", ["graph_analysis.py", "run123"]):
                            graph_analysis.main()

            output = stdout.getvalue()
            self.assertIn("RESULTS-READY SUMMARY FOR run123", output)
            self.assertIn("Interaction density", output)
            self.assertTrue(Path(tmpdir, "results", "analysis", "agent-interaction-network-run123.png").exists())


if __name__ == "__main__":
    unittest.main()
