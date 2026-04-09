"""Thesis-oriented post-simulation graph analysis for MASTOC runs."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

ANNOTATION_POSITION = (0.03, 0.56)
ANNOTATION_FONT_SIZE = 13
ANNOTATION_BOX_STYLE = "round,pad=0.45"
ANNOTATION_FACE_COLOR = "#f5f1d3"
ANNOTATION_ALPHA = 0.95
ANNOTATION_EDGE_COLOR = "#7a734d"
LEGEND_FONT_SIZE = 12
LEGEND_MARKER_SIZE = 12
LEGEND_HANDLE_LENGTH = 2.0
LEGEND_BORDER_PAD = 0.7
LEGEND_LABEL_SPACING = 0.6


def load_simulation_from_db(simulation_id: str) -> dict:
    """Load a simulation document from MongoDB by its _id."""
    from config.db import get_simulation

    sim = get_simulation(simulation_id)
    if sim is None:
        raise ValueError(f"Simulation not found: {simulation_id}")
    return sim


def list_simulations():
    """List recent simulations from MongoDB."""
    from config.db import get_all_simulations

    sims = get_all_simulations(limit=20)
    if not sims:
        print("  No simulations found in database.")
        return []
    print(f"\n  {'_id':<26}  {'Status':<12}  {'Rounds':<8}  {'Agents':<8}  {'Timestamp'}")
    print(f"  {'-' * 26}  {'-' * 12}  {'-' * 8}  {'-' * 8}  {'-' * 20}")
    for sim in sims:
        num_agents = sim.get("config", {}).get("num_agents", "?")
        num_rounds = sim.get("config", {}).get("num_rounds", "?")
        timestamp = str(sim.get("timestamp", ""))[:19]
        print(
            f"  {sim['_id']:<26}  {sim.get('status', '?'):<12}  "
            f"{num_rounds:<8}  {num_agents:<8}  {timestamp}"
        )
    return sims


def extract_rounds_and_summary(simulation: dict) -> tuple[list, dict]:
    """Return round logs and final summary in one place."""
    return simulation.get("rounds", []), simulation.get("final_summary", {})


def build_interaction_graph(rounds: list[dict]) -> nx.Graph:
    """Build an agent-agent interaction graph from repeated co-presence events."""
    graph = nx.Graph()
    repeated_contacts = defaultdict(int)

    for round_data in rounds:
        locations = round_data.get("world_state", {}).get("locations", {})
        for agents in locations.values():
            for index, agent_a in enumerate(agents):
                for agent_b in agents[index + 1 :]:
                    pair = tuple(sorted((agent_a, agent_b)))
                    repeated_contacts[pair] += 1

    for (agent_a, agent_b), weight in repeated_contacts.items():
        graph.add_edge(agent_a, agent_b, weight=weight)

    return graph


def summarize_interaction_dynamics(graph: nx.Graph) -> dict:
    """Compute thesis-friendly coordination metrics from the interaction graph."""
    if graph.number_of_nodes() == 0:
        return {
            "interaction_density": 0.0,
            "local_coordination": 0.0,
            "total_interaction_events": 0,
            "most_central_interactors": [],
        }

    weighted_degree = dict(graph.degree(weight="weight"))
    return {
        "interaction_density": nx.density(graph),
        "local_coordination": nx.average_clustering(graph, weight="weight"),
        "total_interaction_events": int(sum(weighted_degree.values()) / 2),
        "most_central_interactors": sorted(weighted_degree.items(), key=lambda item: item[1], reverse=True)[:5],
    }


def build_analysis_summary(interaction_graph: nx.Graph) -> dict:
    """Package derived post-simulation interaction analysis into one structure."""
    return {"interaction": summarize_interaction_dynamics(interaction_graph)}


def _safe_node_sizes(graph, weighted_degree: dict[str, float], floor: float, span: float) -> list[float]:
    if not graph.nodes():
        return []
    max_weight = max(weighted_degree.values(), default=1) or 1
    return [(weighted_degree.get(node, 0) / max_weight) * span + floor for node in graph.nodes()]


def _save_current_figure(primary_path: Path, alias_path: Path | None = None) -> list[Path]:
    primary_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(primary_path, dpi=300, bbox_inches="tight")
    saved_paths = [primary_path]
    if alias_path is not None and alias_path != primary_path:
        plt.savefig(alias_path, dpi=300, bbox_inches="tight")
        saved_paths.append(alias_path)
    return saved_paths


def _add_summary_box(axis, annotation: str) -> None:
    axis.text(
        *ANNOTATION_POSITION,
        annotation,
        transform=axis.transAxes,
        fontsize=ANNOTATION_FONT_SIZE,
        verticalalignment="center",
        linespacing=1.3,
        bbox=dict(
            boxstyle=ANNOTATION_BOX_STYLE,
            facecolor=ANNOTATION_FACE_COLOR,
            edgecolor=ANNOTATION_EDGE_COLOR,
            alpha=ANNOTATION_ALPHA,
        ),
    )


def _add_plot_legend(axis, legend_handles: list[Line2D]) -> None:
    axis.legend(
        handles=legend_handles,
        loc="lower left",
        frameon=True,
        fontsize=LEGEND_FONT_SIZE,
        markerscale=1.15,
        handlelength=LEGEND_HANDLE_LENGTH,
        borderpad=LEGEND_BORDER_PAD,
        labelspacing=LEGEND_LABEL_SPACING,
    )


def plot_interaction_dynamics(graph: nx.Graph, metrics: dict, output_path: Path, alias_path: Path | None = None):
    """Render thesis-ready agent-agent coordination dynamics."""
    plt.figure(figsize=(12, 8))
    axis = plt.gca()
    positions = nx.spring_layout(graph, k=2.2, iterations=80, seed=42)
    weighted_degree = dict(graph.degree(weight="weight"))
    node_sizes = _safe_node_sizes(graph, weighted_degree, floor=450, span=1850)

    edge_weights = [graph[u][v]["weight"] for u, v in graph.edges()]
    max_weight = max(edge_weights, default=1) or 1
    edge_widths = [(weight / max_weight) * 5.0 + 0.8 for weight in edge_weights]

    nx.draw_networkx_edges(
        graph,
        positions,
        width=edge_widths,
        alpha=0.45,
        edge_color="#4c72b0",
        ax=axis,
    )
    nx.draw_networkx_nodes(
        graph,
        positions,
        node_size=node_sizes,
        node_color="#c8e1ef",
        edgecolors="black",
        linewidths=1.8,
        ax=axis,
    )
    nx.draw_networkx_labels(graph, positions, font_size=9, font_weight="bold", ax=axis)

    top_names = ", ".join(name for name, _ in metrics["most_central_interactors"][:3]) or "No repeated contacts"
    annotation = (
        f"Network connectivity: {metrics['interaction_density']:.2f}\n"
        f"Group coordination: {metrics['local_coordination']:.2f}\n"
        f"Repeated encounters: {metrics['total_interaction_events']}\n"
        f"Central agents: {top_names}"
    )
    _add_summary_box(axis, annotation)

    legend_handles = [
        Line2D([0], [0], color="#4c72b0", lw=2.5, label="Edge width = repeated co-presence across rounds"),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#c8e1ef",
            markeredgecolor="black",
            markersize=LEGEND_MARKER_SIZE,
            label="Node size = interaction centrality",
        ),
    ]
    _add_plot_legend(axis, legend_handles)
    plt.axis("off")
    plt.tight_layout()
    saved_paths = _save_current_figure(output_path, alias_path)
    for path in saved_paths:
        print(f"  Saved: {path}")
    plt.close()


def print_thesis_summary(simulation_id: str, rounds: list[dict], analysis: dict):
    """Print a compact summary that can be cited in the Results section."""
    interaction = analysis["interaction"]

    print(f"\n  {'=' * 58}")
    print(f"  RESULTS-READY SUMMARY FOR {simulation_id}")
    print(f"  {'=' * 58}")
    print(f"  Rounds analyzed:              {len(rounds)}")
    print(f"  Interaction density:          {interaction['interaction_density']:.3f}")
    print(f"  Local coordination:           {interaction['local_coordination']:.3f}")
    print(f"  Repeated interaction events:  {interaction['total_interaction_events']}")

    top_interactors = ", ".join(name for name, _ in interaction["most_central_interactors"][:3]) or "n/a"
    print(f"  Most central interactors:     {top_interactors}")
    print("  Interpretation focus:         coordination structure and recurring co-presence patterns")


def render_analysis_artifacts(simulation_id: str, analysis: dict, output_dir: Path) -> dict[str, Path]:
    """Render the thesis-oriented agent interaction figure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    interaction_path = output_dir / f"agent-interaction-network-{simulation_id}.png"
    legacy_interaction_path = output_dir / f"{simulation_id}_social.png"

    plot_interaction_dynamics(
        analysis["interaction_graph"],
        analysis["interaction"],
        interaction_path,
        alias_path=legacy_interaction_path,
    )

    return {
        "interaction": interaction_path,
        "interaction_legacy": legacy_interaction_path,
    }


def main():
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python -m results.graph_analysis <simulation_id>")
        print("  python -m results.graph_analysis --list")
        print("\nExamples:")
        print("  python -m results.graph_analysis --list              # list recent simulations")
        print("  python -m results.graph_analysis 699da2333fd2229ff50410bc  # analyze by _id")
        sys.exit(1)

    if sys.argv[1] == "--list":
        list_simulations()
        sys.exit(0)

    simulation_id = sys.argv[1]
    print(f"\n{'=' * 60}")
    print(f"  ANALYZING SIMULATION: {simulation_id}")
    print(f"{'=' * 60}\n")

    print("  Loading run data from MongoDB...")
    simulation = load_simulation_from_db(simulation_id)
    rounds, final_summary = extract_rounds_and_summary(simulation)
    print(f"  Loaded {len(rounds)} rounds, status: {simulation.get('status', '?')}")

    if not rounds:
        print("  No round data found. Nothing to analyze.")
        sys.exit(1)

    print("\n  Deriving interaction structure from round logs...")
    interaction_graph = build_interaction_graph(rounds)
    print(
        f"  {interaction_graph.number_of_nodes()} agents, "
        f"{interaction_graph.number_of_edges()} repeated-contact links"
    )

    print("\n  Computing thesis-oriented summary metrics...")
    analysis = build_analysis_summary(interaction_graph)
    analysis["interaction_graph"] = interaction_graph

    print("\n  Rendering thesis-ready figures...")
    render_analysis_artifacts(simulation_id, analysis, Path("results") / "analysis")

    print_thesis_summary(simulation_id, rounds, analysis)
    print("\n  Done!\n")


if __name__ == "__main__":
    main()
