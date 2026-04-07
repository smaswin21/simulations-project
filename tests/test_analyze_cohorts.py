import csv
import json
import tempfile
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from scripts import analyze_cohorts


class AnalyzeCohortsTests(unittest.TestCase):
    def test_thesis_label_maps_default_tags(self):
        self.assertEqual(analyze_cohorts.thesis_label("diverse_traits"), "Diverse Traits Cohort")
        self.assertEqual(
            analyze_cohorts.thesis_label("similar_extraversion"),
            "Similar Extraversion Cohort",
        )

    def test_default_output_paths_are_thesis_friendly(self):
        summary_path, plot_path = analyze_cohorts.default_output_paths(
            results_dir=Path("/tmp/results"),
            baseline_tag="diverse_traits",
            pair_tag="similar_extraversion",
            condition="B",
        )

        self.assertEqual(
            summary_path,
            Path("/tmp/results/cohort-analysis/similar-extraversion-vs-diverse-traits-memory-on-summary.csv"),
        )
        self.assertEqual(
            plot_path,
            Path("/tmp/results/cohort-analysis/similar-extraversion-vs-diverse-traits-memory-on.png"),
        )

    def test_summarize_runs_tolerates_missing_total_graze(self):
        rows = [
            {
                "cohort_label": "diverse_traits",
                "cohort_type": "diverse",
                "cooperation_rate_over_time": [0.5, 1.0],
                "resource_stock_final": 110,
                "gini_final": 0.4,
                "provider": "openai",
                "model": "gpt-5.4",
            }
        ]

        summary = analyze_cohorts.summarize_runs(rows)

        self.assertEqual(summary["mean_total_graze"], 0.0)
        self.assertEqual(summary["mean_cooperation_rate"], 0.75)

    def test_main_writes_two_row_summary_and_plot_to_thesis_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            results_dir = project_root / "results"
            results_dir.mkdir()

            diverse_rows = [
                {
                    "cohort_label": "diverse_traits",
                    "cohort_type": "diverse",
                    "cooperation_rate_over_time": [0.4, 0.6, 0.8],
                    "total_graze_over_time": [8, 9, 10],
                    "resource_stock_final": 109,
                    "gini_final": 0.41,
                    "provider": "openai",
                    "model": "gpt-5.4",
                }
            ]
            similar_rows = [
                {
                    "cohort_label": "similar_extraversion",
                    "cohort_type": "similar",
                    "cooperation_rate_over_time": [0.6, 0.7, 0.9],
                    "total_graze_over_time": [7, 7, 8],
                    "resource_stock_final": 113,
                    "gini_final": 0.36,
                    "provider": "openai",
                    "model": "gpt-5.4",
                }
            ]

            (results_dir / "ablation_B_diverse_traits.jsonl").write_text(
                "\n".join(json.dumps(row) for row in diverse_rows) + "\n",
                encoding="utf-8",
            )
            (results_dir / "ablation_B_similar_extraversion.jsonl").write_text(
                "\n".join(json.dumps(row) for row in similar_rows) + "\n",
                encoding="utf-8",
            )

            original_root = analyze_cohorts.PROJECT_ROOT
            analyze_cohorts.PROJECT_ROOT = project_root
            try:
                analyze_cohorts.main(
                    tags=["diverse_traits", "similar_extraversion"],
                    baseline_tag="diverse_traits",
                    pair_tag="similar_extraversion",
                    condition="B",
                )
            finally:
                analyze_cohorts.PROJECT_ROOT = original_root

            summary_path = (
                results_dir
                / "cohort-analysis"
                / "similar-extraversion-vs-diverse-traits-memory-on-summary.csv"
            )
            plot_path = (
                results_dir
                / "cohort-analysis"
                / "similar-extraversion-vs-diverse-traits-memory-on.png"
            )

            self.assertTrue(summary_path.exists())
            self.assertTrue(plot_path.exists())

            with open(summary_path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 2)
            self.assertEqual([row["cohort_label"] for row in rows], ["diverse_traits", "similar_extraversion"])


if __name__ == "__main__":
    unittest.main()
