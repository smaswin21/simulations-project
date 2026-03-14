# Post-analysis graphs (reads from MongoDB)

# Output needed is:
    # a. Social interaction graph
    # b. Resource distribution graph

# Import necessary libraries

import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx
import matplotlib.pyplot as plt
import numpy as np


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
    print(f"  {'-'*26}  {'-'*12}  {'-'*8}  {'-'*8}  {'-'*20}")
    for s in sims:
        num_agents = s.get("config", {}).get("num_agents", "?")
        num_rounds = s.get("config", {}).get("num_rounds", "?")
        ts = str(s.get("timestamp", ""))[:19]
        print(f"  {s['_id']:<26}  {s.get('status', '?'):<12}  {num_rounds:<8}  {num_agents:<8}  {ts}")
    return sims


# Build social interaction graph
def build_social_graph(rounds: list) -> nx.Graph:
    """Build graph where edges = agents at same location together."""
    G = nx.Graph()

    # Count how many times each pair was together
    together_count = defaultdict(int)

    for round_data in rounds:
        locations = round_data['world_state']['locations']

        # For each location, count all pairs
        for loc, agents in locations.items():
            for i in range(len(agents)):
                for j in range(i + 1, len(agents)):
                    pair = tuple(sorted([agents[i], agents[j]]))
                    together_count[pair] += 1

    # Add edges
    for (agent1, agent2), count in together_count.items():
        G.add_edge(agent1, agent2, weight=count)

    return G


# Build resource distribution graph
def build_resource_graph(rounds: list) -> nx.DiGraph:
    """Build directed graph of resource flows."""
    G = nx.DiGraph()
    flows = defaultdict(int)

    for round_data in rounds:
        for outcome in round_data.get('outcomes', []):
            agent = outcome['agent']
            action = outcome['action']
            detail = outcome['detail']

            if action == 'graze' and 'Grazed' in detail:
                import re as _re
                m = _re.search(r'(\d+)', detail)
                if m:
                    flows[('DEPOT', agent)] += int(m.group(1))

            elif action == 'sanction' and 'against' in detail:
                import re as _re
                match = _re.search(r'against\s+([A-Za-z]+)', detail)
                if match:
                    flows[(agent, match.group(1))] += 2

    # Add edges
    G.add_node('DEPOT')
    for (source, target), amount in flows.items():
        G.add_edge(source, target, weight=amount)

    return G


# Metric calculations

# 1. Gini coefficient of resource distribution
def calculate_gini(values: list) -> float:
    """Calculate Gini coefficient (0=equal, 1=unequal)."""
    sorted_values = sorted(values)
    n = len(sorted_values)
    cumsum = np.cumsum(sorted_values)
    return (2 * np.sum((np.arange(1, n + 1) * sorted_values))) / (n * np.sum(sorted_values)) - (n + 1) / n



def analyze_graphs(social_G, resource_G, rounds, final_summary):
    """Calculate key metrics."""
    inventories = final_summary['inventories']

    metrics = {}

    # Social metrics
    metrics['density'] = nx.density(social_G)
    metrics['avg_clustering'] = nx.average_clustering(social_G, weight='weight')

    # Most social agents
    degree = dict(social_G.degree(weight='weight'))
    metrics['most_social'] = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:5]

    # Resource distribution
    resource_values = list(inventories.values())
    if sum(resource_values) > 0:
        metrics['gini'] = calculate_gini(resource_values)
    else:
        metrics['gini'] = 0.0
    metrics['mean_resource'] = np.mean(resource_values)
    metrics['std_resource'] = np.std(resource_values)

    # Who harvested and sanctioned
    claimed = defaultdict(int)
    shared = defaultdict(int)

    for source, target, data in resource_G.edges(data=True):
        amount = data['weight']
        if source == 'DEPOT':
            claimed[target] += amount
        else:
            shared[source] += amount

    metrics['total_claimed'] = sum(claimed.values())
    metrics['total_shared'] = sum(shared.values())

    # Redistribution ratios
    ratios = {}
    for agent in claimed:
        ratio = shared.get(agent, 0) / claimed[agent] if claimed[agent] > 0 else 0
        ratios[agent] = ratio

    metrics['top_sharers'] = sorted(ratios.items(), key=lambda x: x[1], reverse=True)[:5]
    metrics['final_inventories'] = inventories

    return metrics



def plot_social_graph(G, metrics, output_path):
    """Visualize social interaction network."""
    plt.figure(figsize=(12, 8))

    # Layout
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Node sizes based on how social they are
    degrees = dict(G.degree(weight='weight'))
    max_degree = max(degrees.values()) if degrees.values() else 1
    node_sizes = [degrees[node] / max_degree * 2000 + 300 for node in G.nodes()]

    # Edge widths based on time together
    edge_weights = [G[u][v]['weight'] for u, v in G.edges()]
    max_weight = max(edge_weights) if edge_weights else 1
    edge_widths = [w / max_weight * 5 + 0.5 for w in edge_weights]

    # Draw
    nx.draw_networkx_edges(G, pos, width=edge_widths, alpha=0.3, edge_color='gray')
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color='skyblue',
                          edgecolors='black', linewidths=2, alpha=0.9)
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight='bold')

    plt.title('Social Interaction Network\n(Bigger nodes = more social)',
              fontsize=14, fontweight='bold', pad=20)

    # Stats box
    stats = f"Density: {metrics['density']:.2f}\nAvg Clustering: {metrics['avg_clustering']:.2f}"
    plt.text(0.02, 0.98, stats, transform=plt.gca().transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  Saved: {output_path}")
    plt.close()


def plot_resource_graph(G, metrics, output_path):
    """Visualize resource flow network."""
    plt.figure(figsize=(12, 8))

    # Layout: depot at top, agents in circle
    pos = {'DEPOT': (0, 1)}
    agents = [n for n in G.nodes() if n != 'DEPOT']
    for i, agent in enumerate(agents):
        angle = 2 * np.pi * i / len(agents)
        pos[agent] = (0.8 * np.cos(angle), 0.8 * np.sin(angle) - 0.3)

    # Node sizes based on final resource amount
    inventories = metrics['final_inventories']
    max_med = max(inventories.values()) if inventories.values() else 1
    node_sizes = []
    node_colors = []

    for node in G.nodes():
        if node == 'DEPOT':
            node_sizes.append(800)
            node_colors.append('gold')
        else:
            amount = inventories.get(node, 0)
            node_sizes.append(amount / max_med * 1000 + 200)
            node_colors.append('lightblue')

    # Draw edges
    for (u, v) in G.edges():
        weight = G[u][v]['weight']
        max_weight = max(d['weight'] for _, _, d in G.edges(data=True))
        width = weight / max_weight * 4 + 1

        color = 'blue' if u == 'DEPOT' else 'green'
        alpha = 0.5 if u == 'DEPOT' else 0.7

        nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], width=width,
                              edge_color=color, alpha=alpha, arrows=True,
                              arrowsize=15, arrowstyle='->')

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors,
                          edgecolors='black', linewidths=2)
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight='bold')

    plt.title('Resource Flow Network\n(Blue=Claims, Green=Shares)',
              fontsize=14, fontweight='bold', pad=20)

    # Stats box
    stats = (f"Gini: {metrics['gini']:.2f}\n"
             f"Claimed: {metrics['total_claimed']} units\n"
             f"Shared: {metrics['total_shared']} units")
    plt.text(0.02, 0.98, stats, transform=plt.gca().transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightcyan', alpha=0.8))

    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  Saved: {output_path}")
    plt.close()



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

    print(f"\n{'='*60}")
    print(f"  ANALYZING SIMULATION: {simulation_id}")
    print(f"{'='*60}\n")

    # Load from MongoDB
    print("  Loading data from MongoDB...")
    sim = load_simulation_from_db(simulation_id)
    rounds = sim.get("rounds", [])
    final_summary = sim.get("final_summary", {})
    print(f"  Loaded {len(rounds)} rounds, status: {sim.get('status', '?')}")

    if not rounds:
        print("  No round data found. Nothing to analyze.")
        sys.exit(1)

    print("\n  Building social network...")
    social_G = build_social_graph(rounds)
    print(f"  {social_G.number_of_nodes()} agents, {social_G.number_of_edges()} connections")

    print("\n  Building resource flow...")
    resource_G = build_resource_graph(rounds)
    print(f"  {resource_G.number_of_edges()} transfers")

    # Analyze
    print("\n  Calculating metrics...")
    metrics = analyze_graphs(social_G, resource_G, rounds, final_summary)

    # Visualize
    print("\n  Creating visualizations...")
    output_dir = Path("results") / "analysis"
    output_dir.mkdir(exist_ok=True)

    social_path = output_dir / f"{simulation_id}_social.png"
    resource_path = output_dir / f"{simulation_id}_resource.png"

    plot_social_graph(social_G, metrics, str(social_path))
    plot_resource_graph(resource_G, metrics, str(resource_path))

    # Print summary
    print(f"\n  {'='*50}")
    print(f"  METRICS SUMMARY")
    print(f"  {'='*50}")
    print(f"  Social density:    {metrics['density']:.3f}")
    print(f"  Avg clustering:    {metrics['avg_clustering']:.3f}")
    print(f"  Gini coefficient:  {metrics['gini']:.3f}")
    print(f"  Mean resource:     {metrics['mean_resource']:.1f}")
    print(f"  Std resource:      {metrics['std_resource']:.1f}")
    print(f"  Total claimed:     {metrics['total_claimed']}")
    print(f"  Total shared:      {metrics['total_shared']}")
    print(f"\n  Most social agents:")
    for name, deg in metrics['most_social']:
        print(f"    {name}: {deg}")
    if metrics['top_sharers']:
        print(f"\n  Top sanctioners (sanction/harvest ratio):")
        for name, ratio in metrics['top_sharers']:
            print(f"    {name}: {ratio:.2f}")

    print("\n  Done!\n")


if __name__ == "__main__":
    main()
