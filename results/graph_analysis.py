"""Thesis-oriented post-simulation graph analysis for MASTOC runs."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
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


def _extract_first_int(text: str) -> int | None:
    match = re.search(r"(\d+)", text or "")
    return int(match.group(1)) if match else None


def _extract_named_target(text: str) -> str | None:
    match = re.search(r"(?:against|to)\s+([A-Za-z]+)", text or "")
    return match.group(1) if match else None


def build_resource_dynamics_graph(rounds: list[dict]) -> nx.DiGraph:
    """Build a commons-to-agent and agent-to-agent flow graph from outcomes."""
    graph = nx.DiGraph()
    flow_totals = defaultdict(int)
    graph.add_node("COMMONS")

    for round_data in rounds:
        for outcome in round_data.get("outcomes", []):
            agent = outcome.get("agent")
            action = outcome.get("action")
            detail = outcome.get("detail", "")

            if not agent:
                continue

            if action == "graze" and "Grazed" in detail:
                amount = _extract_first_int(detail)
                if amount is not None:
                    flow_totals[("COMMONS", agent)] += amount
                continue

            if action in {"sanction", "share"}:
                target = _extract_named_target(detail)
                amount = _extract_first_int(detail)
                if target is not None:
                    flow_totals[(agent, target)] += amount if amount is not None else 2

    for (source, target), weight in flow_totals.items():
        graph.add_edge(source, target, weight=weight)

    return graph


def calculate_gini(values: list[float]) -> float:
    """Calculate the Gini coefficient (0 = equal, 1 = unequal)."""
    if not values:
        return 0.0

    sorted_values = np.array(sorted(values), dtype=float)
    total = np.sum(sorted_values)
    if total <= 0:
        return 0.0

    n = len(sorted_values)
    weighted_sum = np.sum(np.arange(1, n + 1) * sorted_values)
    return float((2 * weighted_sum) / (n * total) - (n + 1) / n)


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
        "most_central_interactors": sorted(
            weighted_degree.items(), key=lambda item: item[1], reverse=True
        )[:5],
    }


def summarize_resource_dynamics(resource_graph: nx.DiGraph, final_summary: dict) -> dict:
    """Compute extraction, accountability, and inequality metrics."""
    inventories = final_summary.get("inventories", {})
    resource_values = list(inventories.values())
    extraction_by_agent = defaultdict(int)
    redistribution_by_agent = defaultdict(int)

    for source, target, data in resource_graph.edges(data=True):
        weight = data.get("weight", 0)
        if source == "COMMONS":
            extraction_by_agent[target] += weight
        else:
            redistribution_by_agent[source] += weight

    extraction_total = sum(extraction_by_agent.values())
    redistribution_total = sum(redistribution_by_agent.values())
    return {
        "end_state_gini": calculate_gini(resource_values),
        "mean_final_resources": float(np.mean(resource_values)) if resource_values else 0.0,
        "resource_dispersion": float(np.std(resource_values)) if resource_values else 0.0,
        "total_extracted": extraction_total,
        "total_redistributed": redistribution_total,
        "top_accountability_actors": sorted(
            redistribution_by_agent.items(), key=lambda item: item[1], reverse=True
        )[:5],
        "final_inventories": inventories,
    }


def build_analysis_summary(
    interaction_graph: nx.Graph, resource_graph: nx.DiGraph, final_summary: dict
) -> dict:
    """Package all derived post-simulation analysis into one structure."""
    return {
        "interaction": summarize_interaction_dynamics(interaction_graph),
        "resource": summarize_resource_dynamics(resource_graph, final_summary),
    }


def _safe_node_sizes(graph, weighted_degree: dict[str, float], floor: float, span: float) -> list[float]:
    if not graph.nodes():
        return []
    max_weight = max(weighted_degree.values(), default=1) or 1
    return [(weighted_degree.get(node, 0) / max_weight) * span + floor for node in graph.nodes()]


def _resource_layout(graph: nx.DiGraph) -> dict:
    positions = {"COMMONS": (0.0, 1.05)}
    agents = sorted(node for node in graph.nodes() if node != "COMMONS")
    if not agents:
        return positions

    for index, agent in enumerate(agents):
        angle = 2 * np.pi * index / len(agents)
        positions[agent] = (0.9 * np.cos(angle), 0.75 * np.sin(angle) - 0.25)
    return positions


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


def plot_resource_dynamics(graph: nx.DiGraph, metrics: dict, output_path: Path, alias_path: Path | None = None):
    """Render thesis-ready agent-environment extraction and accountability dynamics."""
    plt.figure(figsize=(12, 8))
    axis = plt.gca()
    positions = _resource_layout(graph)
    inventories = metrics["final_inventories"]
    max_inventory = max(inventories.values(), default=1) or 1

    node_sizes = []
    node_colors = []
    for node in graph.nodes():
        if node == "COMMONS":
            node_sizes.append(950)
            node_colors.append("#f1c40f")
        else:
            inventory = inventories.get(node, 0)
            node_sizes.append((inventory / max_inventory) * 1200 + 260)
            node_colors.append("#d7ecf4")

    max_weight = max((data["weight"] for _, _, data in graph.edges(data=True)), default=1) or 1
    for source, target, data in graph.edges(data=True):
        weight = data["weight"]
        is_extraction = source == "COMMONS"
        nx.draw_networkx_edges(
            graph,
            positions,
            edgelist=[(source, target)],
            width=(weight / max_weight) * 4.5 + 1.0,
            edge_color="#315efb" if is_extraction else "#2e8b57",
            alpha=0.55 if is_extraction else 0.75,
            arrows=True,
            arrowsize=18,
            arrowstyle="->",
            ax=axis,
        )

    nx.draw_networkx_nodes(
        graph,
        positions,
        node_size=node_sizes,
        node_color=node_colors,
        edgecolors="black",
        linewidths=1.8,
        ax=axis,
    )
    nx.draw_networkx_labels(graph, positions, font_size=9, font_weight="bold", ax=axis)

    top_names = ", ".join(name for name, _ in metrics["top_accountability_actors"][:3]) or "No accountability transfers"
    annotation = (
        f"Final inequality (Gini): {metrics['end_state_gini']:.2f}\n"
        f"Commons extracted: {metrics['total_extracted']} units\n"
        f"Agent transfers: {metrics['total_redistributed']} units\n"
        f"Key accountability agents: {top_names}"
    )
    _add_summary_box(axis, annotation)

    legend_handles = [
        Line2D([0], [0], color="#315efb", lw=2.5, label="Blue edge = extraction from the commons"),
        Line2D([0], [0], color="#2e8b57", lw=2.5, label="Green edge = sanction/share transfer between agents"),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#f1c40f",
            markeredgecolor="black",
            markersize=LEGEND_MARKER_SIZE,
            label="Gold node = commons stock source",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#d7ecf4",
            markeredgecolor="black",
            markersize=LEGEND_MARKER_SIZE,
            label="Agent node size = final held resources",
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
    resource = analysis["resource"]

    print(f"\n  {'=' * 58}")
    print(f"  RESULTS-READY SUMMARY FOR {simulation_id}")
    print(f"  {'=' * 58}")
    print(f"  Rounds analyzed:              {len(rounds)}")
    print(f"  Interaction density:          {interaction['interaction_density']:.3f}")
    print(f"  Local coordination:           {interaction['local_coordination']:.3f}")
    print(f"  Repeated interaction events:  {interaction['total_interaction_events']}")
    print(f"  End-state inequality (Gini):  {resource['end_state_gini']:.3f}")
    print(f"  Total extracted:              {resource['total_extracted']}")
    print(f"  Total accountability flows:   {resource['total_redistributed']}")
    print(f"  Mean final resources:         {resource['mean_final_resources']:.1f}")
    print(f"  Resource dispersion:          {resource['resource_dispersion']:.1f}")

    top_interactors = ", ".join(name for name, _ in interaction["most_central_interactors"][:3]) or "n/a"
    top_accountability = ", ".join(name for name, _ in resource["top_accountability_actors"][:3]) or "n/a"
    print(f"  Most central interactors:     {top_interactors}")
    print(f"  Top accountability actors:    {top_accountability}")
    print("  Interpretation focus:         coordination structure + extraction/accountability dynamics")


def render_analysis_artifacts(simulation_id: str, analysis: dict, output_dir: Path) -> dict[str, Path]:
    """Render both thesis-oriented post-analysis figures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    interaction_path = output_dir / f"agent-interaction-network-{simulation_id}.png"
    resource_path = output_dir / f"resource-flow-network-{simulation_id}.png"
    legacy_interaction_path = output_dir / f"{simulation_id}_social.png"
    legacy_resource_path = output_dir / f"{simulation_id}_resource.png"

    plot_interaction_dynamics(
        analysis["interaction_graph"],
        analysis["interaction"],
        interaction_path,
        alias_path=legacy_interaction_path,
    )
    plot_resource_dynamics(
        analysis["resource_graph"],
        analysis["resource"],
        resource_path,
        alias_path=legacy_resource_path,
    )

    return {
        "interaction": interaction_path,
        "resource": resource_path,
        "interaction_legacy": legacy_interaction_path,
        "resource_legacy": legacy_resource_path,
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

    print("\n  Deriving resource extraction and accountability flows...")
    resource_graph = build_resource_dynamics_graph(rounds)
    print(f"  {resource_graph.number_of_edges()} directed flows")

    print("\n  Computing thesis-oriented summary metrics...")
    analysis = build_analysis_summary(interaction_graph, resource_graph, final_summary)
    analysis["interaction_graph"] = interaction_graph
    analysis["resource_graph"] = resource_graph

    print("\n  Rendering thesis-ready figures...")
    render_analysis_artifacts(simulation_id, analysis, Path("results") / "analysis")

    print_thesis_summary(simulation_id, rounds, analysis)
    print("\n  Done!\n")


if __name__ == "__main__":
    main()
