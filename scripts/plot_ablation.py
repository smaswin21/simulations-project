"""
plot_ablation.py — Phase 5: Visualize ablation study results.

Reads results/ablation_A.jsonl and results/ablation_B.jsonl and produces
two comparison plots:
  1. Gini coefficient over rounds (Condition A vs B, mean +/- std)
  2. Accountability events over rounds (Condition A vs B, mean +/- std)

Usage:
    python -m scripts.plot_ablation
    python -m scripts.plot_ablation --output results/ablation_plots.png
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("This script requires matplotlib and numpy.")
    print("Install with: pip install matplotlib numpy")
    sys.exit(1)


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    results = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def compute_stats(runs: list[dict], key: str):
    """
    Compute mean and std across runs for a per-round array key.

    Returns (mean_array, std_array) as numpy arrays.
    """
    arrays = [run[key] for run in runs if key in run]
    if not arrays:
        return np.array([]), np.array([])

    # Pad to max length if runs have different round counts
    max_len = max(len(a) for a in arrays)
    padded = np.zeros((len(arrays), max_len))
    for i, a in enumerate(arrays):
        padded[i, :len(a)] = a

    return padded.mean(axis=0), padded.std(axis=0)


def main(output_path: str | None = None, tag: str = ""):
    results_dir = PROJECT_ROOT / "results"
    suffix = f"_{tag}" if tag else ""
    path_a = results_dir / f"ablation_A{suffix}.jsonl"
    path_b = results_dir / f"ablation_B{suffix}.jsonl"

    if not path_a.exists() or not path_b.exists():
        print(f"Missing result files. Run the ablation study first:")
        print(f"  python -m scripts.run_ablation")
        sys.exit(1)

    runs_a = load_jsonl(path_a)
    runs_b = load_jsonl(path_b)

    print(f"Loaded {len(runs_a)} Condition A runs, {len(runs_b)} Condition B runs")

    # ── Plot 1: Gini over rounds ─────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    mean_a, std_a = compute_stats(runs_a, "gini_over_time")
    mean_b, std_b = compute_stats(runs_b, "gini_over_time")

    rounds_a = np.arange(1, len(mean_a) + 1)
    rounds_b = np.arange(1, len(mean_b) + 1)

    ax = axes[0, 0]
    ax.plot(rounds_a, mean_a, "r-o", label="A: Memory OFF", markersize=4)
    ax.fill_between(rounds_a, mean_a - std_a, mean_a + std_a, alpha=0.2, color="red")
    ax.plot(rounds_b, mean_b, "b-s", label="B: Memory ON", markersize=4)
    ax.fill_between(rounds_b, mean_b - std_b, mean_b + std_b, alpha=0.2, color="blue")
    ax.set_xlabel("Round")
    ax.set_ylabel("Gini Coefficient")
    ax.set_title("Medicine Distribution Inequality (Gini)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)

    # ── Plot 2: Accountability over rounds ───────────────────
    mean_a2, std_a2 = compute_stats(runs_a, "accountability_over_time")
    mean_b2, std_b2 = compute_stats(runs_b, "accountability_over_time")

    rounds_a2 = np.arange(1, len(mean_a2) + 1)
    rounds_b2 = np.arange(1, len(mean_b2) + 1)

    ax2 = axes[0, 1]
    ax2.plot(rounds_a2, mean_a2, "r-o", label="A: Memory OFF", markersize=4)
    ax2.fill_between(rounds_a2, mean_a2 - std_a2, mean_a2 + std_a2, alpha=0.2, color="red")
    ax2.plot(rounds_b2, mean_b2, "b-s", label="B: Memory ON", markersize=4)
    ax2.fill_between(rounds_b2, mean_b2 - std_b2, mean_b2 + std_b2, alpha=0.2, color="blue")
    ax2.set_xlabel("Round")
    ax2.set_ylabel("Accountability Events")
    ax2.set_title("Agents Referencing Others' Past Actions")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(bottom=0)

    # ── Plot 3: Cooperation rate over rounds (bottom-left) ───
    mean_a3, std_a3 = compute_stats(runs_a, "cooperation_rate_over_time")
    mean_b3, std_b3 = compute_stats(runs_b, "cooperation_rate_over_time")
    rounds_a3 = np.arange(1, len(mean_a3) + 1)
    rounds_b3 = np.arange(1, len(mean_b3) + 1)

    ax3 = axes[1, 0]
    if len(mean_a3) > 0:
        ax3.plot(rounds_a3, mean_a3, "r-o", label="A: Memory OFF", markersize=4)
        ax3.fill_between(rounds_a3, mean_a3 - std_a3, mean_a3 + std_a3, alpha=0.2, color="red")
    if len(mean_b3) > 0:
        ax3.plot(rounds_b3, mean_b3, "b-s", label="B: Memory ON", markersize=4)
        ax3.fill_between(rounds_b3, mean_b3 - std_b3, mean_b3 + std_b3, alpha=0.2, color="blue")
    ax3.set_xlabel("Round")
    ax3.set_ylabel("Cooperation Rate")
    ax3.set_title("Fraction of Agents Within Sustainable Quota")
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 1.05)

    # ── Plot 4: Resource stock over rounds (bottom-right) ────
    mean_a4, std_a4 = compute_stats(runs_a, "resource_stock_over_time")
    mean_b4, std_b4 = compute_stats(runs_b, "resource_stock_over_time")
    rounds_a4 = np.arange(1, len(mean_a4) + 1)
    rounds_b4 = np.arange(1, len(mean_b4) + 1)

    ax4 = axes[1, 1]
    if len(mean_a4) > 0:
        ax4.plot(rounds_a4, mean_a4, "r-o", label="A: Memory OFF", markersize=4)
        ax4.fill_between(rounds_a4, mean_a4 - std_a4, mean_a4 + std_a4, alpha=0.2, color="red")
    if len(mean_b4) > 0:
        ax4.plot(rounds_b4, mean_b4, "b-s", label="B: Memory ON", markersize=4)
        ax4.fill_between(rounds_b4, mean_b4 - std_b4, mean_b4 + std_b4, alpha=0.2, color="blue")
    ax4.axhline(y=20, color="gray", linestyle="--", alpha=0.5, label="Collapse threshold")
    ax4.set_xlabel("Round")
    ax4.set_ylabel("Resource Stock")
    ax4.set_title("Commons Pool Level (Headline Figure)")
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim(bottom=0)

    plt.suptitle("Ablation Study: Memory ON vs OFF", fontsize=14, fontweight="bold")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {output_path}")
    else:
        default_path = results_dir / "ablation_plots.png"
        plt.savefig(str(default_path), dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {default_path}")

    # ── Print summary table ──────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  SUMMARY")
    print(f"{'='*50}")

    for label, runs in [("A (Memory OFF)", runs_a), ("B (Memory ON)", runs_b)]:
        ginis = [r["gini_final"] for r in runs]
        acc_rates = [r["accountability_rate"] for r in runs]
        coop_rates = [r.get("cooperation_rate_final", 0) for r in runs]
        final_stocks = [r.get("resource_stock_final", 0) for r in runs]
        print(f"\n  Condition {label}:")
        print(f"    Gini (final):        {np.mean(ginis):.3f} +/- {np.std(ginis):.3f}")
        print(f"    Accountability rate: {np.mean(acc_rates):.3f} +/- {np.std(acc_rates):.3f}")
        if any(coop_rates):
            print(f"    Cooperation rate:    {np.mean(coop_rates):.3f} +/- {np.std(coop_rates):.3f}")
            print(f"    Final stock:         {np.mean(final_stocks):.1f} +/- {np.std(final_stocks):.1f}")

    print(f"\n{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot ablation study results")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file path for the plot (default: results/ablation_plots.png)")
    parser.add_argument("--tag", type=str, default="",
                        help="Tag for input files (e.g., 'commons_ablation')")
    args = parser.parse_args()
    main(args.output, getattr(args, 'tag', ''))
