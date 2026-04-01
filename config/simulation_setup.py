"""
simulation_setup.py — Shared helpers for simulation runtime construction.
"""

from __future__ import annotations

import importlib.util
import random
from dataclasses import dataclass
from pathlib import Path

from agent_flow.agent import Agent
from agent_flow.environment import Environment
from agent_flow.persona_generator import generate_persona_prompt
from config.cohorts import load_cohort_profiles
from config.llms import LLMProvider, LLMSettings, create_provider
from config.logger import Logger
from config.scenario_loader import load_scenario

ROLE_POOL = ["Herder"] * 7 + ["Regulator"] * 2 + ["Scout"]


@dataclass(slots=True)
class SimulationSetup:
    scenario: dict
    provider: LLMProvider
    agents: list[Agent]
    environment: Environment
    logger: Logger
    role_assignments: list[tuple[dict, str]]
    cohort_meta: dict[str, str]


def prepare_scenario(
    scenario_dir: str,
    seed: int,
    num_rounds: int | None = None,
) -> dict:
    scenario = load_scenario(scenario_dir)
    scenario["start_location"] = get_start_location(scenario)
    scenario["rules"] = load_rules(scenario_dir)
    scenario["seed"] = seed
    if num_rounds is not None:
        simulation_cfg = scenario.setdefault("simulation", {})
        simulation_cfg["max_rounds"] = num_rounds
    return scenario


def build_simulation_setup(
    *,
    seed: int,
    scenario_dir: str,
    llm_settings: LLMSettings,
    num_rounds: int | None = None,
    cohort_file: str | None = None,
    cohort_source: str | None = None,
    seed_context: dict | None = None,
) -> SimulationSetup:
    scenario = prepare_scenario(
        scenario_dir,
        seed,
        num_rounds=num_rounds,
    )

    profiles, cohort_meta = load_cohort_profiles(
        cohort_file=cohort_file,
        cohort_source=cohort_source,
    )
    agent_count = scenario.get("agents", {}).get("count", len(ROLE_POOL))
    role_assignments = assign_roles(
        profiles,
        seed=seed,
        count=agent_count,
    )
    provider = create_provider(llm_settings)

    agents = []
    base_seed_context = {"seed": seed}
    if seed_context:
        base_seed_context.update(seed_context)

    for profile, role in role_assignments:
        persona = generate_persona_prompt(profile, scenario, role)
        agents.append(
            Agent(
                profile=profile,
                persona_prompt=persona,
                scenario=scenario,
                role=role,
                llm_provider=provider,
                seed_context=dict(base_seed_context),
            )
        )

    environment = Environment(agents, scenario)
    logger = Logger()
    return SimulationSetup(
        scenario=scenario,
        provider=provider,
        agents=agents,
        environment=environment,
        logger=logger,
        role_assignments=role_assignments,
        cohort_meta=cohort_meta,
    )


def get_start_location(scenario: dict) -> str:
    for loc in scenario.get("locations", []):
        if loc.get("starting_location"):
            return loc.get("name")
    locations = scenario.get("locations", [])
    if locations:
        return locations[0].get("name")
    return "Village Council"


def load_rules(scenario_dir: str):
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


def assign_roles(
    profiles: list[dict],
    seed: int,
    count: int,
) -> list[tuple[dict, str]]:
    selected = profiles[:count]
    roles = ROLE_POOL[:count]
    rng = random.Random(seed)
    rng.shuffle(roles)
    return list(zip(selected, roles))
