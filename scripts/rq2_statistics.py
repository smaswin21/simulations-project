"""
rq2_statistics.py — Statistical analysis for RQ2 similar-vs-diverse cohort runs.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analyze_cohorts import THESIS_OUTPUT_DIRNAME, thesis_label


DEFAULT_MEMORY_ON_TAGS = [
    "diverse_traits",
    "similar_agreeableness",
    "similar_conscientiousness",
    "similar_extraversion",
    "similar_neuroticism",
    "similar_openness",
]

DEFAULT_METRICS = {
    "resource_stock_final": "Commons Stock",
    "gini_final": "Gini Coefficient",
}


@dataclass(frozen=True, slots=True)
class ConditionSpec:
    tag: str
    condition: str
    label: str
    path: Path


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def default_output_paths(output_dir: Path) -> tuple[Path, Path, Path, Path]:
    return (
        output_dir / "rq2-descriptive-stats.csv",
        output_dir / "rq2-anova-summary.csv",
        output_dir / "rq2-tukey-hsd.csv",
        output_dir / "rq2-statistics-report.txt",
    )


def build_condition_specs(
    results_dir: Path,
    memory_on_tags: list[str],
    memory_off_tag: str,
    memory_on_condition: str,
    memory_off_condition: str,
) -> list[ConditionSpec]:
    specs = [
        ConditionSpec(
            tag=tag,
            condition=memory_on_condition,
            label=f"{thesis_display_name(tag)} (Memory ON)",
            path=results_dir / f"ablation_{memory_on_condition}_{tag}.jsonl",
        )
        for tag in memory_on_tags
    ]
    specs.append(
        ConditionSpec(
            tag="memory_off",
            condition=memory_off_condition,
            label="Memory OFF",
            path=results_dir / f"ablation_{memory_off_condition}_{memory_off_tag}.jsonl",
        )
    )
    return specs


def thesis_display_name(tag: str) -> str:
    label = thesis_label(tag)
    return label.replace(" Cohort", "")


def extract_metric_values(runs: list[dict], key: str) -> np.ndarray:
    return np.asarray([float(run[key]) for run in runs if key in run], dtype=float)


def sample_sd(values: np.ndarray) -> float:
    if len(values) <= 1:
        return 0.0
    return float(np.std(values, ddof=1))


def descriptive_rows(grouped_runs: list[tuple[ConditionSpec, list[dict]]]) -> list[dict]:
    rows = []
    for spec, runs in grouped_runs:
        stock = extract_metric_values(runs, "resource_stock_final")
        gini = extract_metric_values(runs, "gini_final")
        rows.append(
            {
                "condition": spec.label,
                "runs": len(runs),
                "commons_stock_mean": float(np.mean(stock)) if len(stock) else 0.0,
                "commons_stock_sd": sample_sd(stock),
                "gini_mean": float(np.mean(gini)) if len(gini) else 0.0,
                "gini_sd": sample_sd(gini),
            }
        )
    return sorted(rows, key=lambda row: row["commons_stock_mean"], reverse=True)


def anova_row(metric_label: str, grouped_values: list[np.ndarray], alpha: float) -> dict:
    f_result = stats.f_oneway(*grouped_values)
    all_values = np.concatenate(grouped_values)
    grand_mean = float(np.mean(all_values))
    ss_between = float(sum(len(group) * (float(np.mean(group)) - grand_mean) ** 2 for group in grouped_values))
    ss_total = float(np.sum((all_values - grand_mean) ** 2))
    eta_squared = ss_between / ss_total if ss_total else 0.0
    total_n = int(sum(len(group) for group in grouped_values))
    k = len(grouped_values)
    return {
        "metric": metric_label,
        "f_statistic": float(f_result.statistic),
        "df_between": k - 1,
        "df_within": total_n - k,
        "p_value": float(f_result.pvalue),
        "eta_squared": float(eta_squared),
        "significant": "yes" if float(f_result.pvalue) < alpha else "no",
    }


def tukey_rows(
    metric_key: str,
    metric_label: str,
    grouped_runs: list[tuple[ConditionSpec, list[dict]]],
    alpha: float,
) -> list[dict]:
    labels = [spec.label for spec, _ in grouped_runs]
    grouped_values = [extract_metric_values(runs, metric_key) for _, runs in grouped_runs]
    tukey = stats.tukey_hsd(*grouped_values)
    intervals = tukey.confidence_interval(confidence_level=1 - alpha)

    rows = []
    for left_idx in range(len(labels)):
        for right_idx in range(left_idx + 1, len(labels)):
            rows.append(
                {
                    "metric": metric_label,
                    "comparison": f"{labels[left_idx]} vs {labels[right_idx]}",
                    "mean_difference_abs": abs(float(tukey.statistic[left_idx, right_idx])),
                    "p_value": float(tukey.pvalue[left_idx, right_idx]),
                    "confidence_interval_low": float(intervals.low[left_idx, right_idx]),
                    "confidence_interval_high": float(intervals.high[left_idx, right_idx]),
                    "significant": "yes" if float(tukey.pvalue[left_idx, right_idx]) < alpha else "no",
                }
            )
    return rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows available for {output_path.name}")
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def format_p_value(value: float) -> str:
    return "< .001" if value < 0.001 else f"{value:.3f}"


def write_report(
    descriptive: list[dict],
    anova_rows: list[dict],
    report_path: Path,
) -> None:
    best_stock = max(descriptive, key=lambda row: row["commons_stock_mean"])
    lowest_gini = min(descriptive, key=lambda row: row["gini_mean"])

    lines = [
        "RQ2 Statistical Summary",
        "",
        "ANOVA",
    ]
    for row in anova_rows:
        lines.append(
            (
                f"- {row['metric']}: F({row['df_between']}, {row['df_within']}) = "
                f"{row['f_statistic']:.3f}, p {format_p_value(row['p_value'])}, "
                f"eta^2 = {row['eta_squared']:.3f}, significant = {row['significant']}"
            )
        )

    lines.extend(
        [
            "",
            "Descriptive highlights",
            (
                f"- Highest commons stock: {best_stock['condition']} "
                f"(M = {best_stock['commons_stock_mean']:.3f}, SD = {best_stock['commons_stock_sd']:.3f})"
            ),
            (
                f"- Lowest gini coefficient: {lowest_gini['condition']} "
                f"(M = {lowest_gini['gini_mean']:.3f}, SD = {lowest_gini['gini_sd']:.3f})"
            ),
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(
    memory_on_tags: list[str],
    memory_off_tag: str,
    memory_on_condition: str,
    memory_off_condition: str,
    alpha: float,
    results_dir: str | None = None,
    output_dir: str | None = None,
) -> None:
    resolved_results_dir = Path(results_dir) if results_dir else PROJECT_ROOT / "results"
    resolved_output_dir = Path(output_dir) if output_dir else resolved_results_dir / THESIS_OUTPUT_DIRNAME
    specs = build_condition_specs(
        results_dir=resolved_results_dir,
        memory_on_tags=memory_on_tags,
        memory_off_tag=memory_off_tag,
        memory_on_condition=memory_on_condition,
        memory_off_condition=memory_off_condition,
    )

    grouped_runs: list[tuple[ConditionSpec, list[dict]]] = []
    for spec in specs:
        if not spec.path.exists():
            raise FileNotFoundError(f"Missing results file: {spec.path}")
        grouped_runs.append((spec, load_jsonl(spec.path)))

    descriptive = descriptive_rows(grouped_runs)
    grouped_stock = [extract_metric_values(runs, "resource_stock_final") for _, runs in grouped_runs]
    grouped_gini = [extract_metric_values(runs, "gini_final") for _, runs in grouped_runs]
    anova_rows = [
        anova_row(DEFAULT_METRICS["resource_stock_final"], grouped_stock, alpha),
        anova_row(DEFAULT_METRICS["gini_final"], grouped_gini, alpha),
    ]
    tukey = tukey_rows("resource_stock_final", DEFAULT_METRICS["resource_stock_final"], grouped_runs, alpha)
    tukey.extend(tukey_rows("gini_final", DEFAULT_METRICS["gini_final"], grouped_runs, alpha))

    descriptive_path, anova_path, tukey_path, report_path = default_output_paths(resolved_output_dir)
    write_csv(descriptive, descriptive_path)
    write_csv(anova_rows, anova_path)
    write_csv(tukey, tukey_path)
    write_report(descriptive, anova_rows, report_path)

    print(f"Descriptive statistics written to: {descriptive_path}")
    print(f"ANOVA summary written to:        {anova_path}")
    print(f"Tukey HSD results written to:    {tukey_path}")
    print(f"Text report written to:          {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the RQ2 statistical analysis for similar vs diverse cohorts")
    parser.add_argument("--memory-on-tags", nargs="+", default=DEFAULT_MEMORY_ON_TAGS)
    parser.add_argument("--memory-off-tag", type=str, default="diverse_traits")
    parser.add_argument("--memory-on-condition", type=str, default="B")
    parser.add_argument("--memory-off-condition", type=str, default="A")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--results-dir", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()
    main(
        memory_on_tags=args.memory_on_tags,
        memory_off_tag=args.memory_off_tag,
        memory_on_condition=args.memory_on_condition,
        memory_off_condition=args.memory_off_condition,
        alpha=args.alpha,
        results_dir=args.results_dir,
        output_dir=args.output_dir,
    )
