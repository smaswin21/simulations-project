"""
plot_ablation.py — Plot memory OFF vs ON ablation results.
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
        return [json.loads(line) for line in handle if line.strip()]


def compute_stats(runs: list[dict], key: str):
    arrays = [run[key] for run in runs if key in run]
    if not arrays:
        return np.array([]), np.array([])
    max_len = max(len(array) for array in arrays)
    padded = np.zeros((len(arrays), max_len))
    for idx, array in enumerate(arrays):
        padded[idx, : len(array)] = array
    return padded.mean(axis=0), padded.std(axis=0)


def _plot_series(ax, runs_a: list[dict], runs_b: list[dict], key: str, title: str, ylabel: str):
    mean_a, std_a = compute_stats(runs_a, key)
    mean_b, std_b = compute_stats(runs_b, key)
    if len(mean_a):
        rounds_a = np.arange(1, len(mean_a) + 1)
        ax.plot(rounds_a, mean_a, "r-o", label="A: Memory OFF", markersize=4)
        ax.fill_between(rounds_a, mean_a - std_a, mean_a + std_a, alpha=0.2, color="red")
    if len(mean_b):
        rounds_b = np.arange(1, len(mean_b) + 1)
        ax.plot(rounds_b, mean_b, "b-s", label="B: Memory ON", markersize=4)
        ax.fill_between(rounds_b, mean_b - std_b, mean_b + std_b, alpha=0.2, color="blue")
    ax.set_title(title)
    ax.set_xlabel("Round")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()


def main(output_path: str | None = None, tag: str = ""):
    results_dir = PROJECT_ROOT / "results"
    suffix = f"_{tag}" if tag else ""
    path_a = results_dir / f"ablation_A{suffix}.jsonl"
    path_b = results_dir / f"ablation_B{suffix}.jsonl"

    if not path_a.exists() or not path_b.exists():
        print("Missing ablation result files.")
        sys.exit(1)

    runs_a = load_jsonl(path_a)
    runs_b = load_jsonl(path_b)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), squeeze=False)
    _plot_series(axes[0, 0], runs_a, runs_b, "resource_stock_over_time", "Commons Stock", "Stock")
    _plot_series(axes[0, 1], runs_a, runs_b, "gini_over_time", "Social Inequality", "Gini")
    plt.suptitle("Heterogeneous MASTOC Ablation: Memory OFF vs ON", fontsize=14, fontweight="bold")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {output_path}")
    else:
        default_path = results_dir / "ablation_plots.png"
        plt.savefig(default_path, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {default_path}")

    print("\nSummary")
    for label, runs in [("A (Memory OFF)", runs_a), ("B (Memory ON)", runs_b)]:
        print(f"\nCondition {label}:")
        print(f"  Final stock: {np.mean([r.get('resource_stock_final', 0) for r in runs]):.2f}")
        print(f"  Final gini: {np.mean([r.get('gini_final', 0) for r in runs]):.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot ablation study results")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--tag", type=str, default="")
    args = parser.parse_args()
    main(args.output, args.tag)
