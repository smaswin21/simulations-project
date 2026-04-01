"""
plot_memory_only.py — Internal helpers for saving a single memory-on run plot.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np

import config.db as db

MEMORY_PLOTS_DIR = PROJECT_ROOT / "memory_plots"


def default_output_path(simulation_id: str) -> Path:
    return MEMORY_PLOTS_DIR / f"{simulation_id}.png"


def _model_name(simulation: dict) -> str:
    config = simulation.get("config") or {}
    model = (
        config.get("llm_model")
        or config.get("model")
        or config.get("llm_provider")
        or config.get("provider")
    )
    if not model:
        return "Unknown model"
    return str(model)


def _metrics_from_summary(simulation: dict) -> dict[str, list[float] | list[int]] | None:
    final_summary = simulation.get("final_summary") or {}
    metrics = final_summary.get("ablation_metrics") or {}
    stock = metrics.get("resource_stock_over_time")
    gini = metrics.get("gini_over_time")
    if stock and gini:
        return {
            "resource_stock_over_time": stock,
            "gini_over_time": gini,
        }
    return None


def _metrics_from_rounds(rounds: list[dict]) -> dict[str, list[float] | list[int]]:
    if not rounds:
        raise ValueError("Simulation has no rounds to reconstruct metrics from.")

    stock_over_time: list[int | float] = []
    gini_over_time: list[float] = []
    for round_data in rounds:
        world_state = round_data.get("world_state") or {}
        visualization_state = round_data.get("visualization_state") or {}

        stock = world_state.get("resource_depot")
        if stock is None:
            stock = visualization_state.get("stock")
        gini = world_state.get("gini")

        if stock is None or gini is None:
            raise ValueError("Simulation rounds are missing resource stock or gini values.")

        stock_over_time.append(stock)
        gini_over_time.append(gini)

    return {
        "resource_stock_over_time": stock_over_time,
        "gini_over_time": gini_over_time,
    }


def load_run_metrics(simulation_id: str) -> dict[str, object]:
    try:
        simulation = db.get_simulation(simulation_id)
    except Exception as exc:
        raise ValueError(f"Simulation '{simulation_id}' could not be loaded: {exc}") from exc

    if simulation is None:
        raise ValueError(f"Simulation '{simulation_id}' was not found.")

    metrics = _metrics_from_summary(simulation)
    if metrics is None:
        metrics = _metrics_from_rounds(simulation.get("rounds") or [])

    return {
        "simulation_id": simulation_id,
        "model_name": _model_name(simulation),
        "resource_stock_over_time": metrics["resource_stock_over_time"],
        "gini_over_time": metrics["gini_over_time"],
    }


def build_plot(run: dict[str, object], plot_title: str):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), squeeze=False)

    for axis, key, title, ylabel in [
        (axes[0, 0], "resource_stock_over_time", "Commons Stock", "Stock"),
        (axes[0, 1], "gini_over_time", "Social Inequality", "Gini"),
    ]:
        series = np.asarray(run[key], dtype=float)
        rounds = np.arange(1, len(series) + 1)
        axis.plot(rounds, series, "b-s", label=f"Memory ON ({run['model_name']})", markersize=4)
        axis.set_title(title)
        axis.set_xlabel("Round")
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.3)
        axis.legend()

    plt.suptitle(plot_title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    return fig, axes


def save_simulation_plot(
    simulation_id: str,
    output_path: str | Path | None = None,
    title: str | None = None,
) -> Path:
    run = load_run_metrics(simulation_id)
    plot_title = title or f"Memory ON Run: {run['model_name']}"
    build_plot(run, plot_title)

    destination = Path(output_path) if output_path else default_output_path(simulation_id)
    destination.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close()
    return destination
