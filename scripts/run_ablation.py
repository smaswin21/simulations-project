"""
run_ablation.py — Phase 5: Ablation study runner.

Compares Condition A (memory OFF) vs Condition B (memory ON) across
multiple seeded runs, collecting Gini and accountability metrics.

Usage:
    python -m scripts.run_ablation --runs 3 --rounds 15 --scenario simulations/tragedy_of_commons
    python -m scripts.run_ablation --runs 5 --rounds 10

Output:
    results/ablation_A.jsonl   (Condition A: memory OFF)
    results/ablation_B.jsonl   (Condition B: memory ON)
"""

import asyncio
import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import anthropic
from openai import AsyncOpenAI

import config.config as cfg
from config.scenario_loader import load_scenario
from agent_flow.agent import Agent
from agent_flow.persona_generator import generate_persona_prompt
from agent_flow.environment import Environment
from config.orchestrator import Orchestrator
from config.logger import Logger
from agent_flow.embedding import get_embed_model
import config.db as db


def _get_start_location(scenario: dict) -> str:
    for loc in scenario.get("locations", []):
        if loc.get("starting_location"):
            return loc.get("name")
    locations = scenario.get("locations", [])
    if locations:
        return locations[0].get("name")
    return "Village Square"


def _load_rules(scenario_dir: str):
    base = Path(scenario_dir)
    rules_path = base / "rules.py"
    if not rules_path.exists():
        return None
    module_name = f"scenario_rules_{rules_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, rules_path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def run_single(
    seed: int,
    condition: str,
    num_rounds: int,
    scenario_dir: str,
) -> dict:
    """
    Run one simulation with the given seed and condition.

    Args:
        seed: random seed for reproducibility
        condition: "A" (memory OFF) or "B" (memory ON)
        num_rounds: number of simulation rounds
        scenario_dir: path to scenario directory

    Returns:
        Dict with metrics for this run.
    """
    # Set seed
    random.seed(seed)

    # Toggle memory
    cfg.USE_LAYER2_MEMORY = (condition == "B")

    # Load scenario
    scenario = load_scenario(scenario_dir)
    scenario["start_location"] = _get_start_location(scenario)
    scenario["rules"] = _load_rules(scenario_dir)

    # Load profiles and build agents
    profiles = db.load_profiles()

    agent_count = scenario.get("agents", {}).get("count")
    if agent_count and len(profiles) > agent_count:
        profiles = profiles[:agent_count]

    agents = []
    for profile in profiles:
        persona = generate_persona_prompt(profile, scenario)
        agent = Agent(profile, persona, scenario)
        agents.append(agent)

    # Build world
    env = Environment(agents, scenario)
    logger = Logger()

    if cfg.USE_OLLAMA:
        client = AsyncOpenAI(base_url=cfg.API_BASE, api_key=cfg.API_KEY)
    else:
        client = anthropic.AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)

    # Run simulation
    orch = Orchestrator(agents, env, logger, client, scenario,
                        condition=condition, seed=seed)
    await orch.run_simulation(num_rounds)

    # Collect metrics
    metrics = orch.get_metrics_summary()
    metrics["condition"] = condition
    metrics["seed"] = seed

    return metrics


async def main(num_runs: int, num_rounds: int, scenario_dir: str, tag: str = ""):
    """Run the full ablation study."""
    print(f"\n{'='*60}")
    print(f"  ABLATION STUDY")
    print(f"  Runs per condition: {num_runs}")
    print(f"  Rounds per run:     {num_rounds}")
    print(f"  Scenario:           {scenario_dir}")
    print(f"{'='*60}\n")

    # Initialize embedding model once
    get_embed_model()

    # Prepare output directory
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    suffix = f"_{tag}" if tag else ""
    path_a = results_dir / f"ablation_A{suffix}.jsonl"
    path_b = results_dir / f"ablation_B{suffix}.jsonl"

    # Generate seeds upfront for reproducibility
    seeds = list(range(42, 42 + num_runs))

    # ── Condition A: Memory OFF ──────────────────────────────
    print(f"{'─'*50}")
    print(f"  CONDITION A: Memory OFF ({num_runs} runs)")
    print(f"{'─'*50}\n")

    with open(path_a, "w") as f:
        for i, seed in enumerate(seeds):
            print(f"\n  --- Run A-{i+1}/{num_runs} (seed={seed}) ---")
            metrics = await run_single(seed, "A", num_rounds, scenario_dir)
            f.write(json.dumps(metrics) + "\n")
            f.flush()
            print(f"  Gini={metrics['gini_final']:.3f}  "
                  f"Accountability={metrics['accountability_events']}/{metrics['total_speech_acts']}")

    # ── Condition B: Memory ON ───────────────────────────────
    print(f"\n{'─'*50}")
    print(f"  CONDITION B: Memory ON ({num_runs} runs)")
    print(f"{'─'*50}\n")

    with open(path_b, "w") as f:
        for i, seed in enumerate(seeds):
            print(f"\n  --- Run B-{i+1}/{num_runs} (seed={seed}) ---")
            metrics = await run_single(seed, "B", num_rounds, scenario_dir)
            f.write(json.dumps(metrics) + "\n")
            f.flush()
            print(f"  Gini={metrics['gini_final']:.3f}  "
                  f"Accountability={metrics['accountability_events']}/{metrics['total_speech_acts']}")

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ABLATION COMPLETE")
    print(f"  Results written to:")
    print(f"    {path_a}")
    print(f"    {path_b}")
    print(f"{'='*60}\n")

    # Restore default
    cfg.USE_LAYER2_MEMORY = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ablation study: memory ON vs OFF")
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of runs per condition (default: 3)")
    parser.add_argument("--rounds", type=int, default=cfg.NUM_ROUNDS,
                        help=f"Rounds per simulation (default: {cfg.NUM_ROUNDS})")
    parser.add_argument("--scenario", type=str, default="simulations/tragedy_of_commons",
                        help="Path to scenario directory")
    parser.add_argument("--tag", type=str, default="",
                        help="Tag for output files (e.g., 'commons_ablation')")
    args = parser.parse_args()

    asyncio.run(main(args.runs, args.rounds, args.scenario, args.tag))
