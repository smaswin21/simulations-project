"""
run_simulation.py — Entry point.

Usage:
    python run_simulation.py - entire simulation is run              
    python run_simulation.py --rounds 5 
"""

import asyncio
import argparse
import importlib.util
from pathlib import Path

import anthropic
from openai import AsyncOpenAI

from config.config import NUM_ROUNDS, USE_OLLAMA, API_KEY, API_BASE, MODEL_NAME, ANTHROPIC_API_KEY
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


def _resolve_rules_path(scenario_dir: str):
    base = Path(scenario_dir)
    rules_path = base / "rules.py"
    if rules_path.exists():
        return rules_path
    return None


def _load_rules(scenario_dir: str):
    rules_path = _resolve_rules_path(scenario_dir)
    if not rules_path:
        return None
    module_name = f"scenario_rules_{rules_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, rules_path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def main(num_rounds: int, scenario_dir: str):
    scenario = load_scenario(scenario_dir)
    scenario["start_location"] = _get_start_location(scenario)
    scenario["rules"] = _load_rules(scenario_dir)

    # --- 0. Initialize embedding model once (shared across all agents) ---
    get_embed_model()

    # --- 1. Load agent profiles --- 
    profiles = db.load_profiles()

    agent_count = scenario.get("agents", {}).get("count")
    if agent_count and len(profiles) > agent_count:
        profiles = profiles[:agent_count]

    print(f"Loaded {len(profiles)} agent profiles.")

    # --- 2. Generate persona prompts --- 
    agents = []
    for profile in profiles:
        persona = generate_persona_prompt(profile, scenario)
        agent = Agent(profile, persona, scenario)
        agents.append(agent)
        # Uncomment to inspect a persona:
        # print(f"\n--- {agent.name} ---\n{persona}\n")

    # --- 3. Build the world --- 
    env = Environment(agents, scenario)
    logger = Logger()

    if USE_OLLAMA:
        client = AsyncOpenAI(base_url=API_BASE, api_key=API_KEY)
    else:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # Log config
    logger.log_config(profiles, {
        "num_rounds": num_rounds,
        "num_agents": len(agents),
        "model": "claude-sonnet-4-20250514",
        "scenario": scenario.get("simulation", {}).get("name"),
    })

    # --- 4. Run --- 
    orch = Orchestrator(agents, env, logger, client, scenario)
    await orch.run_simulation(num_rounds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=NUM_ROUNDS,
                        help="Number of simulation rounds (default: 25)")
    parser.add_argument(
        "--scenario",
        type=str,
        default="simulations/tragedy_of_commons",
        help="Path to scenario directory",
    )
    args = parser.parse_args()
    asyncio.run(main(args.rounds, args.scenario))
