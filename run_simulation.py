"""
run_simulation.py — Entry point.
"""

import argparse
import asyncio
import importlib.util
import random
from pathlib import Path

import config.db as db
from agent_flow.agent import Agent
from agent_flow.embedding import get_embed_model
from agent_flow.environment import Environment
from agent_flow.persona_generator import generate_persona_prompt
from config.config import DEFAULT_SEED, NUM_ROUNDS
from config.llms import create_provider
from config.logger import Logger
from config.orchestrator import Orchestrator
from config.scenario_loader import load_scenario

ROLE_POOL = ["Herder"] * 7 + ["Regulator"] * 2 + ["Scout"]


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


def assign_roles(profiles: list[dict], seed: int, count: int) -> list[tuple[dict, str]]:
    selected = profiles[:count]
    roles = ROLE_POOL[:count]
    rng = random.Random(seed)
    rng.shuffle(roles)
    return list(zip(selected, roles))


async def main(num_rounds: int, scenario_dir: str, seed: int):
    scenario = load_scenario(scenario_dir)
    scenario["start_location"] = _get_start_location(scenario)
    scenario["rules"] = _load_rules(scenario_dir)
    scenario["seed"] = seed

    get_embed_model()

    profiles = db.load_profiles()
    agent_count = scenario.get("agents", {}).get("count", len(ROLE_POOL))
    role_assignments = assign_roles(profiles, seed=seed, count=agent_count)
    provider = create_provider()

    agents = []
    for profile, role in role_assignments:
        persona = generate_persona_prompt(profile, scenario, role)
        agent = Agent(
            profile=profile,
            persona_prompt=persona,
            scenario=scenario,
            role=role,
            llm_provider=provider,
            seed_context={"seed": seed},
        )
        agents.append(agent)

    env = Environment(agents, scenario)
    logger = Logger()

    logger.log_config(
        profiles=[{**profile, "role": role} for profile, role in role_assignments],
        settings={
            "num_rounds": num_rounds,
            "num_agents": len(agents),
            "seed": seed,
            "llm_provider": provider.settings.provider,
            "llm_model": provider.settings.model,
            "scenario": scenario.get("simulation", {}).get("name"),
        },
    )

    orch = Orchestrator(
        agents=agents,
        environment=env,
        logger=logger,
        llm_provider=provider,
        scenario=scenario,
        seed=seed,
    )
    await orch.run_simulation(num_rounds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rounds",
        type=int,
        default=NUM_ROUNDS,
        help="Number of simulation rounds",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="simulations/tragedy_of_commons",
        help="Path to scenario directory",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed used for reproducible role assignment",
    )
    args = parser.parse_args()
    asyncio.run(main(args.rounds, args.scenario, args.seed))
