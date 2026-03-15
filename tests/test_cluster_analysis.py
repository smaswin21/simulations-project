import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path

import numpy as np

from scripts.run_cluster_analysis import (
    _to_json_safe,
    average_pairwise_distance,
    build_diverse_cohort,
    cohort_trait_summary,
    exportable_profile,
    jsonl_line,
    load_jsonl,
    merge_profiles_by_pid,
    promote_temp_jsonl,
    summarize_runs,
)


def profile(pid: str, name: str, extraversion: float, agreeableness: float, conscientiousness: float, neuroticism: float, openness: float) -> dict:
    return {
        "pid": pid,
        "name": name,
        "big_five": {
            "extraversion": extraversion,
            "agreeableness": agreeableness,
            "conscientiousness": conscientiousness,
            "neuroticism": neuroticism,
            "openness": openness,
        },
        "crt_score": 0.0,
        "crt_max": 4.0,
        "risk_preference": 0.5,
        "has_dependents": False,
    }


class ClusterAnalysisTests(unittest.TestCase):
    def test_merge_profiles_by_pid_uses_pool_data(self):
        cohort_seed = [{"pid": "2", "cohort_type": "similar"}, {"pid": "1", "cohort_type": "similar"}]
        pool = [
            profile("1", "Ava", 0.1, 0.2, 0.3, 0.4, 0.5),
            profile("2", "Ben", 0.9, 0.8, 0.7, 0.6, 0.5),
        ]

        merged = merge_profiles_by_pid(cohort_seed, pool)

        self.assertEqual([item["pid"] for item in merged], ["2", "1"])
        self.assertEqual([item["name"] for item in merged], ["Ben", "Ava"])

    def test_build_diverse_cohort_excludes_similar_ids_and_is_deterministic(self):
        pool = [
            profile("1", "A", 0.0, 0.0, 0.0, 0.0, 0.0),
            profile("2", "B", 1.0, 0.0, 0.0, 0.0, 0.0),
            profile("3", "C", 0.0, 1.0, 0.0, 0.0, 0.0),
            profile("4", "D", 0.0, 0.0, 1.0, 0.0, 0.0),
            profile("5", "E", 0.0, 0.0, 0.0, 1.0, 0.0),
            profile("6", "F", 0.0, 0.0, 0.0, 0.0, 1.0),
        ]

        selected_a = build_diverse_cohort(pool, exclude_pids={"1"}, size=3)
        selected_b = build_diverse_cohort(pool, exclude_pids={"1"}, size=3)

        self.assertEqual([item["pid"] for item in selected_a], [item["pid"] for item in selected_b])
        self.assertNotIn("1", [item["pid"] for item in selected_a])
        self.assertEqual(len(selected_a), 3)

    def test_diverse_cohort_has_higher_pairwise_distance_than_similar_group(self):
        similar = [
            profile("10", "S1", 0.80, 0.50, 0.50, 0.40, 0.50),
            profile("11", "S2", 0.82, 0.49, 0.51, 0.39, 0.52),
            profile("12", "S3", 0.79, 0.48, 0.50, 0.41, 0.49),
        ]
        pool = [
            profile("20", "D1", 0.0, 0.0, 0.0, 0.0, 0.0),
            profile("21", "D2", 1.0, 0.0, 0.0, 0.0, 0.0),
            profile("22", "D3", 0.0, 1.0, 0.0, 0.0, 0.0),
            profile("23", "D4", 0.0, 0.0, 1.0, 0.0, 0.0),
            profile("24", "D5", 0.0, 0.0, 0.0, 1.0, 0.0),
            profile("25", "D6", 0.0, 0.0, 0.0, 0.0, 1.0),
        ]

        diverse = build_diverse_cohort(pool, exclude_pids=set(), size=3)

        similar_distance = average_pairwise_distance(
            np.vstack([list(item["big_five"].values()) for item in similar])
        )
        diverse_distance = average_pairwise_distance(
            np.vstack([list(item["big_five"].values()) for item in diverse])
        )

        self.assertGreater(diverse_distance, similar_distance)

    def test_cohort_trait_summary_contains_expected_fields(self):
        profiles = [
            profile("1", "Ava", 0.1, 0.2, 0.3, 0.4, 0.5),
            profile("2", "Ben", 0.9, 0.8, 0.7, 0.6, 0.5),
        ]

        summary = cohort_trait_summary(profiles)

        self.assertEqual(summary["size"], 2)
        self.assertEqual(summary["pids"], ["1", "2"])
        self.assertIn("extraversion", summary["mean_big_five"])
        self.assertIn("agreeableness", summary["std_big_five"])
        self.assertGreaterEqual(summary["average_pairwise_distance"], 0.0)

    def test_to_json_safe_converts_datetime_and_numpy_values(self):
        payload = {
            "created_at": datetime(2026, 3, 15, 12, 30, 45),
            "updated_date": date(2026, 3, 15),
            "updated_time": time(12, 30, 45),
            "array": np.asarray([1.0, 2.0], dtype=np.float64),
            "scalar": np.float32(3.5),
            "nested": [{"value": np.int64(7)}],
        }

        converted = _to_json_safe(payload)

        self.assertEqual(converted["created_at"], "2026-03-15T12:30:45")
        self.assertEqual(converted["updated_date"], "2026-03-15")
        self.assertEqual(converted["updated_time"], "12:30:45")
        self.assertEqual(converted["array"], [1.0, 2.0])
        self.assertEqual(converted["scalar"], 3.5)
        self.assertEqual(converted["nested"][0]["value"], 7)

    def test_exportable_profile_trims_operational_fields(self):
        raw_profile = {
            **profile("1", "Ava", 0.1, 0.2, 0.3, 0.4, 0.5),
            "_id": "mongo-id",
            "created_at": datetime(2026, 3, 15, 12, 30, 45),
            "updated_at": datetime(2026, 3, 15, 13, 0, 0),
            "cohort_type": "diverse",
            "extra_field": "ignore-me",
        }

        exported = exportable_profile(raw_profile)

        self.assertEqual(
            set(exported.keys()),
            {
                "pid",
                "name",
                "big_five",
                "crt_score",
                "crt_max",
                "risk_preference",
                "has_dependents",
                "cohort_type",
            },
        )
        self.assertEqual(exported["pid"], "1")
        self.assertNotIn("_id", exported)
        self.assertNotIn("created_at", exported)
        self.assertNotIn("updated_at", exported)

    def test_summarize_runs_works_from_in_memory_rows(self):
        runs = [
            {"resource_stock_final": 118, "gini_final": 0.8, "cooperation_rate_final": 1.0, "accountability_rate": 0.0, "speech_diversity_final": 0.9, "numeric_grounding_final": 0.1},
            {"resource_stock_final": 117, "gini_final": 0.75, "cooperation_rate_final": 0.9, "accountability_rate": 0.2, "speech_diversity_final": 0.8, "numeric_grounding_final": 0.2},
        ]

        summary = summarize_runs(runs)

        self.assertEqual(summary["num_runs"], 2)
        self.assertAlmostEqual(summary["resource_stock_final"]["mean"], 117.5)
        self.assertAlmostEqual(summary["gini_final"]["mean"], 0.775)

    def test_temp_jsonl_promotion_produces_valid_output(self):
        rows = [
            {"seed": 42, "resource_stock_final": 118},
            {"seed": 43, "resource_stock_final": 117},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            temp_path = tmpdir_path / ".cluster.tmp"
            final_path = tmpdir_path / "cluster.jsonl"
            with open(temp_path, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(jsonl_line(row))
            promote_temp_jsonl(temp_path, final_path)

            loaded = load_jsonl(final_path)

        self.assertEqual(loaded, rows)

    def test_load_jsonl_raises_with_path_and_line_number(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.jsonl"
            path.write_text('{"ok": 1}\n{"broken":\n', encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                rf"Malformed JSONL in .*{path.name} at line 2",
            ):
                load_jsonl(path)


if __name__ == "__main__":
    unittest.main()
