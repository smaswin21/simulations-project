"""
analyze_cohorts.py — Summarize similar vs diverse cohort results.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np


THESIS_OUTPUT_DIRNAME = "cohort-analysis"


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def mean_curve(runs: list[dict], key: str) -> np.ndarray:
    arrays = [np.asarray(run.get(key, []), dtype=float) for run in runs if run.get(key)]
    if not arrays:
        return np.array([])
    max_len = max(len(array) for array in arrays)
    padded = np.full((len(arrays), max_len), np.nan)
    for idx, array in enumerate(arrays):
        padded[idx, : len(array)] = array
    return np.nanmean(padded, axis=0)


def summarize_runs(runs: list[dict]) -> dict:
    if not runs:
        raise ValueError("No runs available to summarize.")

    def run_mean(key: str) -> float:
        per_run = [float(np.mean(run.get(key, []))) for run in runs if run.get(key)]
        return float(np.mean(per_run)) if per_run else 0.0

    return {
        "cohort_label": runs[0].get("cohort_label", ""),
        "cohort_type": runs[0].get("cohort_type", ""),
        "runs": len(runs),
        "mean_cooperation_rate": run_mean("cooperation_rate_over_time"),
        "mean_total_graze": run_mean("total_graze_over_time"),
        "final_stock_mean": float(np.mean([run.get("resource_stock_final", 0) for run in runs])),
        "final_gini_mean": float(np.mean([run.get("gini_final", 0.0) for run in runs])),
        "provider": runs[0].get("provider", ""),
        "model": runs[0].get("model", ""),
    }


def write_summary_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cohort_label",
        "cohort_type",
        "runs",
        "mean_cooperation_rate",
        "mean_total_graze",
        "final_stock_mean",
        "final_gini_mean",
        "provider",
        "model",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def thesis_label(tag: str) -> str:
    fixed_labels = {
        "diverse_traits": "Diverse Traits Cohort",
        "similar_agreeableness": "Similar Agreeableness Cohort",
        "similar_conscientiousness": "Similar Conscientiousness Cohort",
        "similar_extraversion": "Similar Extraversion Cohort",
        "similar_neuroticism": "Similar Neuroticism Cohort",
        "similar_openness": "Similar Openness Cohort",
        "memory_off": "Memory OFF",
    }
    if tag in fixed_labels:
        return fixed_labels[tag]
    words = tag.replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def default_output_paths(results_dir: Path, baseline_tag: str, pair_tag: str, condition: str) -> tuple[Path, Path]:
    thesis_dir = results_dir / THESIS_OUTPUT_DIRNAME
    condition_suffix = "memory-on" if condition == "B" else f"condition-{condition.lower()}"
    stem = f"{pair_tag.replace('_', '-')}-vs-{baseline_tag.replace('_', '-')}-{condition_suffix}"
    return (
        thesis_dir / f"{stem}-summary.csv",
        thesis_dir / f"{stem}.png",
    )


def plot_pairwise(
    baseline_runs: list[dict],
    comparison_runs: list[dict],
    baseline_label: str,
    comparison_label: str,
    output_path: Path,
    condition: str,
) -> None:
    baseline_curve = mean_curve(baseline_runs, "cooperation_rate_over_time")
    comparison_curve = mean_curve(comparison_runs, "cooperation_rate_over_time")
    if len(baseline_curve) == 0 or len(comparison_curve) == 0:
        raise ValueError("Missing cooperation_rate_over_time data for pairwise plot.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 5))
    plt.plot(np.arange(1, len(baseline_curve) + 1), baseline_curve, label=baseline_label, linewidth=2)
    plt.plot(np.arange(1, len(comparison_curve) + 1), comparison_curve, label=comparison_label, linewidth=2)
    plt.xlabel("Round")
    plt.ylabel("Mean Cooperation Rate")
    condition_label = "Memory ON" if condition == "B" else f"Condition {condition}"
    plt.title(f"Mean Cooperation Over Rounds: {comparison_label} vs {baseline_label} ({condition_label})")
    plt.ylim(0, 1.05)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def main(
    tags: list[str],
    baseline_tag: str,
    pair_tag: str,
    condition: str,
    summary_output: str | None = None,
    plot_output: str | None = None,
) -> None:
    results_dir = PROJECT_ROOT / "results"
    runs_by_tag: dict[str, list[dict]] = {}

    for tag in tags:
        path = results_dir / f"ablation_{condition}_{tag}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Missing results file: {path}")
        runs_by_tag[tag] = load_jsonl(path)

    summary_rows = [summarize_runs(runs_by_tag[tag]) for tag in tags]
    default_summary_path, default_plot_path = default_output_paths(
        results_dir=results_dir,
        baseline_tag=baseline_tag,
        pair_tag=pair_tag,
        condition=condition,
    )
    summary_path = Path(summary_output) if summary_output else default_summary_path
    write_summary_csv(summary_rows, summary_path)

    plot_path = Path(plot_output) if plot_output else default_plot_path
    plot_pairwise(
        baseline_runs=runs_by_tag[baseline_tag],
        comparison_runs=runs_by_tag[pair_tag],
        baseline_label=thesis_label(baseline_tag),
        comparison_label=thesis_label(pair_tag),
        output_path=plot_path,
        condition=condition,
    )

    print(f"Summary CSV written to: {summary_path}")
    print(f"Pairwise plot written to: {plot_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze similar vs diverse cohort results")
    parser.add_argument(
        "--tags",
        nargs="+",
        default=[
            "diverse_traits",
            "similar_agreeableness",
            "similar_conscientiousness",
            "similar_extraversion",
            "similar_neuroticism",
            "similar_openness",
        ],
    )
    parser.add_argument("--baseline-tag", type=str, default="diverse_traits")
    parser.add_argument("--pair-tag", type=str, default="similar_extraversion")
    parser.add_argument("--condition", type=str, default="B")
    parser.add_argument("--summary-output", type=str, default=None)
    parser.add_argument("--plot-output", type=str, default=None)
    args = parser.parse_args()
    main(
        tags=args.tags,
        baseline_tag=args.baseline_tag,
        pair_tag=args.pair_tag,
        condition=args.condition,
        summary_output=args.summary_output,
        plot_output=args.plot_output,
    )
