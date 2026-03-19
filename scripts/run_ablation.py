"""
run_ablation.py — Run memory OFF vs memory ON ablations.
"""

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config.db as db
import config.config as cfg
from agent_flow.agent import Agent
from agent_flow.embedding import get_embed_model
from agent_flow.environment import Environment
from agent_flow.persona_generator import generate_persona_prompt
from config.cohorts import load_cohort_profiles
from config.llms import create_provider
from config.logger import Logger
from config.orchestrator import Orchestrator
from config.scenario_loader import load_scenario
from run_simulation import assign_roles


def _get_start_location(scenario: dict) -> str:
    for loc in scenario.get("locations", []):
        if loc.get("starting_location"):
            return loc.get("name")
    locations = scenario.get("locations", [])
    if locations:
        return locations[0].get("name")
    return "Village Council"


def _load_rules(scenario_dir: str):
    rules_path = Path(scenario_dir) / "rules.py"
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
    cohort_file: str | None = None,
    cohort_source: str | None = None,
) -> dict:
    cfg.USE_LAYER2_MEMORY = condition == "B"

    scenario = load_scenario(scenario_dir)
    scenario["start_location"] = _get_start_location(scenario)
    scenario["rules"] = _load_rules(scenario_dir)
    scenario["seed"] = seed

    profiles, cohort_meta = load_cohort_profiles(
        cohort_file=cohort_file,
        cohort_source=cohort_source,
    )
    agent_count = scenario.get("agents", {}).get("count", 10)
    role_assignments = assign_roles(
        profiles,
        seed=seed,
        count=agent_count,
    )
    provider = create_provider()

    agents = []
    for profile, role in role_assignments:
        persona = generate_persona_prompt(profile, scenario, role)
        agents.append(
            Agent(
                profile=profile,
                persona_prompt=persona,
                scenario=scenario,
                role=role,
                llm_provider=provider,
                seed_context={"seed": seed, "condition": condition},
            )
        )

    env = Environment(agents, scenario)
    logger = Logger()
    orch = Orchestrator(
        agents=agents,
        environment=env,
        logger=logger,
        llm_provider=provider,
        scenario=scenario,
        condition=condition,
        seed=seed,
    )
    await orch.run_simulation(num_rounds)

    metrics = orch.get_metrics_summary()
    metrics["condition"] = condition
    metrics["seed"] = seed
    metrics["provider"] = provider.settings.provider
    metrics["model"] = provider.settings.model
    metrics["cohort_label"] = cohort_meta["cohort_label"]
    metrics["cohort_type"] = cohort_meta["cohort_type"]
    return metrics


async def main(
    num_runs: int,
    num_rounds: int,
    scenario_dir: str,
    tag: str = "",
    cohort_file: str | None = None,
    cohort_source: str | None = None,
):
    print(f"\n{'=' * 60}")
    print("  ABLATION STUDY")
    print(f"  Runs per condition: {num_runs}")
    print(f"  Rounds per run:     {num_rounds}")
    print(f"  Scenario:           {scenario_dir}")
    print(f"{'=' * 60}\n")

    get_embed_model()

    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    suffix = f"_{tag}" if tag else ""
    path_a = results_dir / f"ablation_A{suffix}.jsonl"
    path_b = results_dir / f"ablation_B{suffix}.jsonl"
    seeds = list(range(42, 42 + num_runs))

    with open(path_a, "w", encoding="utf-8") as handle:
        for idx, seed in enumerate(seeds, start=1):
            print(f"\n  --- Run A-{idx}/{num_runs} (seed={seed}) ---")
            metrics = await run_single(
                seed,
                "A",
                num_rounds,
                scenario_dir,
                cohort_file=cohort_file,
                cohort_source=cohort_source,
            )
            handle.write(json.dumps(metrics) + "\n")
            handle.flush()

    with open(path_b, "w", encoding="utf-8") as handle:
        for idx, seed in enumerate(seeds, start=1):
            print(f"\n  --- Run B-{idx}/{num_runs} (seed={seed}) ---")
            metrics = await run_single(
                seed,
                "B",
                num_rounds,
                scenario_dir,
                cohort_file=cohort_file,
                cohort_source=cohort_source,
            )
            handle.write(json.dumps(metrics) + "\n")
            handle.flush()

    print(f"\nResults written to:\n  {path_a}\n  {path_b}\n")
    cfg.USE_LAYER2_MEMORY = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ablation study: memory OFF vs ON")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=cfg.NUM_ROUNDS)
    parser.add_argument("--scenario", type=str, default="simulations/tragedy_of_commons")
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument("--cohort-file", type=str, default=None)
    parser.add_argument("--cohort-source", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(
        main(
            args.runs,
            args.rounds,
            args.scenario,
            args.tag,
            args.cohort_file,
            args.cohort_source,
        )
    )
