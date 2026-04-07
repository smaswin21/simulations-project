import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")

from results import graph_analysis


class GraphAnalysisTests(unittest.TestCase):
    def test_build_interaction_graph_accumulates_repeated_contacts(self):
        rounds = [
            {"world_state": {"locations": {"Pasture": ["Alice", "Bob"], "River": ["Cara"]}}},
            {"world_state": {"locations": {"Pasture": ["Alice", "Bob", "Cara"]}}},
        ]

        graph = graph_analysis.build_interaction_graph(rounds)

        self.assertEqual(graph["Alice"]["Bob"]["weight"], 2)
        self.assertEqual(graph["Alice"]["Cara"]["weight"], 1)
        self.assertEqual(graph["Bob"]["Cara"]["weight"], 1)

    def test_build_resource_dynamics_graph_creates_extraction_and_transfer_edges(self):
        rounds = [
            {
                "outcomes": [
                    {"agent": "Alice", "action": "graze", "detail": "Grazed 4 units from the pasture."},
                    {"agent": "Regina", "action": "sanction", "detail": "Queued sanction against Alice for next round."},
                    {"agent": "Bob", "action": "share", "detail": "Shared 3 units to Cara."},
                ]
            }
        ]

        graph = graph_analysis.build_resource_dynamics_graph(rounds)

        self.assertEqual(graph["COMMONS"]["Alice"]["weight"], 4)
        self.assertEqual(graph["Regina"]["Alice"]["weight"], 2)
        self.assertEqual(graph["Bob"]["Cara"]["weight"], 3)

    def test_build_analysis_summary_computes_thesis_ready_metrics(self):
        interaction_graph = graph_analysis.build_interaction_graph(
            [
                {"world_state": {"locations": {"Pasture": ["Alice", "Bob", "Cara"]}}},
                {"world_state": {"locations": {"Pasture": ["Alice", "Bob"]}}},
            ]
        )
        resource_graph = graph_analysis.build_resource_dynamics_graph(
            [
                {
                    "outcomes": [
                        {"agent": "Alice", "action": "graze", "detail": "Grazed 4 units from the pasture."},
                        {"agent": "Bob", "action": "graze", "detail": "Grazed 2 units from the pasture."},
                        {"agent": "Regina", "action": "sanction", "detail": "Queued sanction against Alice for next round."},
                    ]
                }
            ]
        )
        final_summary = {"inventories": {"Alice": 5, "Bob": 3, "Cara": 1, "Regina": 0}}

        summary = graph_analysis.build_analysis_summary(interaction_graph, resource_graph, final_summary)

        self.assertAlmostEqual(summary["interaction"]["interaction_density"], 1.0)
        self.assertEqual(summary["interaction"]["total_interaction_events"], 4)
        self.assertEqual(summary["resource"]["total_extracted"], 6)
        self.assertEqual(summary["resource"]["total_redistributed"], 2)
        self.assertEqual(summary["resource"]["top_accountability_actors"][0][0], "Regina")
        self.assertGreater(summary["resource"]["end_state_gini"], 0.0)

    def test_render_analysis_artifacts_emits_thesis_and_legacy_filenames(self):
        interaction_graph = graph_analysis.build_interaction_graph(
            [{"world_state": {"locations": {"Pasture": ["Alice", "Bob"]}}}]
        )
        resource_graph = graph_analysis.build_resource_dynamics_graph(
            [{"outcomes": [{"agent": "Alice", "action": "graze", "detail": "Grazed 3 units from the pasture."}]}]
        )
        analysis = graph_analysis.build_analysis_summary(
            interaction_graph,
            resource_graph,
            {"inventories": {"Alice": 3, "Bob": 1}},
        )
        analysis["interaction_graph"] = interaction_graph
        analysis["resource_graph"] = resource_graph

        with tempfile.TemporaryDirectory() as tmpdir:
            output_paths = graph_analysis.render_analysis_artifacts("run123", analysis, Path(tmpdir))

            self.assertTrue(output_paths["interaction"].exists())
            self.assertTrue(output_paths["resource"].exists())
            self.assertTrue(output_paths["interaction_legacy"].exists())
            self.assertTrue(output_paths["resource_legacy"].exists())

    def test_main_runs_end_to_end_with_mocked_db_payload(self):
        simulation = {
            "status": "completed",
            "rounds": [
                {
                    "world_state": {"locations": {"Pasture": ["Alice", "Bob"]}},
                    "outcomes": [
                        {"agent": "Alice", "action": "graze", "detail": "Grazed 3 units from the pasture."},
                        {"agent": "Regina", "action": "sanction", "detail": "Queued sanction against Alice for next round."},
                    ],
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
            self.assertTrue(Path(tmpdir, "results", "analysis", "resource-flow-network-run123.png").exists())


if __name__ == "__main__":
    unittest.main()
