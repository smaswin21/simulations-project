"""
plot_cluster_analysis.py — Plot similar vs diverse memory-on cohort analysis.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        rows = []
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSONL in {path} at line {line_number}: {exc.msg}"
                ) from exc
        return rows


def compute_stats(runs: list[dict], key: str):
    arrays = [run[key] for run in runs if key in run]
    if not arrays:
        return np.array([]), np.array([])
    max_len = max(len(array) for array in arrays)
    padded = np.zeros((len(arrays), max_len))
    for idx, array in enumerate(arrays):
        padded[idx, : len(array)] = array
    return padded.mean(axis=0), padded.std(axis=0)


def plot_time_series(ax, similar_runs: list[dict], diverse_runs: list[dict], key: str, title: str, ylabel: str):
    mean_similar, std_similar = compute_stats(similar_runs, key)
    mean_diverse, std_diverse = compute_stats(diverse_runs, key)

    if len(mean_similar):
        rounds = np.arange(1, len(mean_similar) + 1)
        ax.plot(rounds, mean_similar, "o-", color="#d95f02", label="Similar Extraversion", markersize=4)
        ax.fill_between(rounds, mean_similar - std_similar, mean_similar + std_similar, alpha=0.18, color="#d95f02")
    if len(mean_diverse):
        rounds = np.arange(1, len(mean_diverse) + 1)
        ax.plot(rounds, mean_diverse, "s-", color="#1b9e77", label="Diverse Big Five", markersize=4)
        ax.fill_between(rounds, mean_diverse - std_diverse, mean_diverse + std_diverse, alpha=0.18, color="#1b9e77")

    ax.set_title(title)
    ax.set_xlabel("Round")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()


def plot_final_bar(ax, similar_runs: list[dict], diverse_runs: list[dict], metric: str, title: str):
    similar_values = [float(run.get(metric, 0.0)) for run in similar_runs]
    diverse_values = [float(run.get(metric, 0.0)) for run in diverse_runs]
    means = [
        float(np.mean(similar_values)) if similar_values else 0.0,
        float(np.mean(diverse_values)) if diverse_values else 0.0,
    ]
    stds = [
        float(np.std(similar_values)) if similar_values else 0.0,
        float(np.std(diverse_values)) if diverse_values else 0.0,
    ]

    labels = ["Similar", "Diverse"]
    colors = ["#d95f02", "#1b9e77"]
    ax.bar(labels, means, yerr=stds, color=colors, alpha=0.85, capsize=5)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)


def main(output_path: str | None = None, tag: str = ""):
    results_dir = PROJECT_ROOT / "results"
    suffix = f"_{tag}" if tag else ""
    similar_path = results_dir / f"cluster_similar_extraversion{suffix}.jsonl"
    diverse_path = results_dir / f"cluster_diverse_bigfive{suffix}.jsonl"
    summary_path = results_dir / f"cluster_analysis_summary{suffix}.json"

    if not similar_path.exists() or not diverse_path.exists():
        print("Missing cluster analysis result files.")
        sys.exit(1)

    similar_runs = load_jsonl(similar_path)
    diverse_runs = load_jsonl(diverse_path)
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}

    fig, axes = plt.subplots(2, 3, figsize=(18, 10), squeeze=False)
    plot_time_series(axes[0, 0], similar_runs, diverse_runs, "resource_stock_over_time", "Commons Stock", "Stock")
    plot_time_series(axes[0, 1], similar_runs, diverse_runs, "gini_over_time", "Wealth Inequality", "Gini")
    plot_final_bar(axes[0, 2], similar_runs, diverse_runs, "resource_stock_final", "Final Stock")
    plot_final_bar(axes[1, 0], similar_runs, diverse_runs, "gini_final", "Final Gini")
    plot_final_bar(axes[1, 1], similar_runs, diverse_runs, "cooperation_rate_final", "Final Cooperation")
    plot_final_bar(axes[1, 2], similar_runs, diverse_runs, "accountability_rate", "Accountability Rate")

    winner = summary.get("comparison", {}).get("winner", "unknown")
    plt.suptitle(
        f"Memory-On Cluster Analysis: Similar Extraversion vs Diverse Big Five (winner: {winner})",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {output_path}")
    else:
        default_path = results_dir / "cluster_analysis_plots.png"
        plt.savefig(default_path, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {default_path}")

    print("\nSummary")
    for label, runs in [("Similar Extraversion", similar_runs), ("Diverse Big Five", diverse_runs)]:
        print(f"\nCohort {label}:")
        print(f"  Final stock: {np.mean([r.get('resource_stock_final', 0) for r in runs]):.2f}")
        print(f"  Final gini: {np.mean([r.get('gini_final', 0) for r in runs]):.3f}")
        print(f"  Final cooperation: {np.mean([r.get('cooperation_rate_final', 0) for r in runs]):.3f}")
        print(f"  Accountability rate: {np.mean([r.get('accountability_rate', 0) for r in runs]):.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot cluster-specific cohort analysis")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--tag", type=str, default="")
    args = parser.parse_args()
    main(args.output, args.tag)
