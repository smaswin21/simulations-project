import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import rq2_statistics


class RQ2StatisticsTests(unittest.TestCase):
    def test_build_condition_specs_uses_expected_paths(self):
        specs = rq2_statistics.build_condition_specs(
            results_dir=Path("/tmp/results"),
            memory_on_tags=["diverse_traits", "similar_extraversion"],
            memory_off_tag="diverse_traits",
            memory_on_condition="B",
            memory_off_condition="A",
        )

        self.assertEqual(specs[0].path, Path("/tmp/results/ablation_B_diverse_traits.jsonl"))
        self.assertEqual(specs[1].label, "Similar Extraversion (Memory ON)")
        self.assertEqual(specs[2].path, Path("/tmp/results/ablation_A_diverse_traits.jsonl"))
        self.assertEqual(specs[2].label, "Memory OFF")

    def test_main_writes_descriptive_anova_and_tukey_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            results_dir = project_root / "results"
            results_dir.mkdir()

            base_rows = {
                "diverse_traits": [(109, 0.327), (110, 0.330), (109, 0.324)],
                "similar_agreeableness": [(115, 0.573), (114, 0.548), (116, 0.598)],
                "similar_conscientiousness": [(116, 0.706), (117, 0.727), (118, 0.748)],
                "similar_extraversion": [(112, 0.482), (113, 0.503), (115, 0.524)],
                "similar_neuroticism": [(107, 0.472), (109, 0.493), (109, 0.514)],
                "similar_openness": [(116, 0.722), (117, 0.743), (118, 0.764)],
            }
            memory_off_rows = [(107, 0.622), (109, 0.643), (109, 0.664)]

            for tag, values in base_rows.items():
                rows = [
                    {
                        "resource_stock_final": stock,
                        "gini_final": gini,
                        "cohort_label": tag,
                        "cohort_type": "diverse" if tag == "diverse_traits" else "similar",
                    }
                    for stock, gini in values
                ]
                (results_dir / f"ablation_B_{tag}.jsonl").write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n",
                    encoding="utf-8",
                )

            memory_off = [
                {
                    "resource_stock_final": stock,
                    "gini_final": gini,
                    "cohort_label": "diverse_traits",
                    "cohort_type": "diverse",
                }
                for stock, gini in memory_off_rows
            ]
            (results_dir / "ablation_A_diverse_traits.jsonl").write_text(
                "\n".join(json.dumps(row) for row in memory_off) + "\n",
                encoding="utf-8",
            )

            rq2_statistics.main(
                memory_on_tags=rq2_statistics.DEFAULT_MEMORY_ON_TAGS,
                memory_off_tag="diverse_traits",
                memory_on_condition="B",
                memory_off_condition="A",
                alpha=0.05,
                results_dir=str(results_dir),
                output_dir=str(results_dir / "cohort-analysis"),
            )

            descriptive_path = results_dir / "cohort-analysis" / "rq2-descriptive-stats.csv"
            anova_path = results_dir / "cohort-analysis" / "rq2-anova-summary.csv"
            tukey_path = results_dir / "cohort-analysis" / "rq2-tukey-hsd.csv"
            report_path = results_dir / "cohort-analysis" / "rq2-statistics-report.txt"

            self.assertTrue(descriptive_path.exists())
            self.assertTrue(anova_path.exists())
            self.assertTrue(tukey_path.exists())
            self.assertTrue(report_path.exists())

            with open(descriptive_path, newline="", encoding="utf-8") as handle:
                descriptive_rows = list(csv.DictReader(handle))
            with open(anova_path, newline="", encoding="utf-8") as handle:
                anova_rows = list(csv.DictReader(handle))
            with open(tukey_path, newline="", encoding="utf-8") as handle:
                tukey_rows = list(csv.DictReader(handle))

            self.assertEqual(len(descriptive_rows), 7)
            self.assertEqual(descriptive_rows[0]["condition"], "Similar Conscientiousness (Memory ON)")
            self.assertEqual(len(anova_rows), 2)
            self.assertEqual(anova_rows[0]["metric"], "Commons Stock")
            self.assertEqual(anova_rows[1]["metric"], "Gini Coefficient")
            self.assertEqual(len(tukey_rows), 42)
            self.assertIn("Highest commons stock", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
