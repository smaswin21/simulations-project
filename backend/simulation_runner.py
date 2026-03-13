"""
backend/simulation_runner.py — Shared async simulation runner for the API.

Runs the Tragedy-of-the-Commons simulation round-by-round, sets USE_LAYER2_MEMORY
and optional seed, and calls on_round_complete(round_payload) after each round.
Expects to be run from project root (or with project root on PYTHONPATH).
"""

import importlib.util
import random
from pathlib import Path
from typing import Any, Callable

# Project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Location name -> (col, row) for the first agent at that location; more agents
# get adjacent cells. Matches sim-engine mockData layout.
LOCATION_GRID_ANCHORS = {
    "Village Square": (1, 1),
    "Common Pasture": (8, 1),
    "Notice Board": (4, 5),
}
# Max agents per location in grid (2 columns x 3 rows = 6)
AGENTS_PER_LOCATION_SLOTS = 6


def _get_start_location(scenario: dict) -> str:
    for loc in scenario.get("locations", []):
        if loc.get("starting_location"):
            return loc.get("name")
    locs = scenario.get("locations", [])
    if locs:
        return locs[0].get("name", "Village Square")
    return "Village Square"


def _load_rules(scenario_dir: str):
    base = Path(scenario_dir)
    rules_path = base / "rules.py"
    if not rules_path.exists():
        return None
    name = f"scenario_rules_{rules_path.stem}"
    spec = importlib.util.spec_from_file_location(name, rules_path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _location_name_to_id(name: str) -> str:
    """'Village Square' -> 'village-square' for frontend."""
    return name.lower().replace(" ", "-")


def _assign_grid_positions(agents: list, world_state: dict) -> list[dict]:
    """
    Build agent list with gridPos from world_state locations.
    world_state["locations"] = { "Village Square": ["Alice", "Bob"], ... }
    """
    locations = world_state.get("locations", {})
    inventories = world_state.get("inventories", {})
    result = []
    agent_index = 0
    for loc_name, names_at_loc in locations.items():
        anchor = LOCATION_GRID_ANCHORS.get(loc_name, (0, 0))
        for i, name in enumerate(names_at_loc):
            row_offset = i // 2
            col_offset = i % 2
            grid_pos = [anchor[0] + col_offset, anchor[1] + row_offset]
            resource = inventories.get(name, 0)
            # Status from resource (simple thresholds; tune to match your config)
            if resource >= 7:
                status = "thriving"
            elif resource >= 4:
                status = "strained"
            elif resource >= 1:
                status = "struggling"
            else:
                status = "depleted"
            result.append({
                "id": agent_index + 1,
                "name": name,
                "location": _location_name_to_id(loc_name),
                "gridPos": grid_pos,
                "status": status,
                "grazingUnits": resource,
                "action": None,
            })
            agent_index += 1
    # If any agent not in locations (shouldn't happen), append with default pos
    all_names = set()
    for names in locations.values():
        all_names.update(names)
    for a in getattr(agents, "__iter__", lambda: []) if callable(agents) else agents:
        aname = a.name if hasattr(a, "name") else a.get("name")
        if aname not in all_names:
            result.append({
                "id": agent_index + 1,
                "name": aname,
                "location": "village-square",
                "gridPos": [0, 0],
                "status": "strained",
                "grazingUnits": inventories.get(aname, 0),
                "action": None,
            })
            agent_index += 1
    return result


def build_round_payload(
    env,
    agents,
    orch,
    scenario: dict,
) -> dict[str, Any]:
    """Build one round payload for the frontend / SSE."""
    world_state = env.get_world_state()
    rnd = world_state["round"]
    max_rounds = scenario.get("simulation", {}).get("max_rounds", env.max_rounds)

    agents_payload = _assign_grid_positions(agents, world_state)

    gini = orch.metrics.gini_over_time
    coop = orch.metrics.cooperation_rate_over_time
    stock = orch.metrics.resource_stock_over_time

    return {
        "round": rnd,
        "max_rounds": max_rounds,
        "world_state": world_state,
        "agents": agents_payload,
        "metrics_so_far": {
            "gini": list(gini),
            "cooperation_rate": list(coop),
            "resource_stock": list(stock),
        },
    }


def build_payload_from_db_round(
    db_round: dict,
    max_rounds: int,
    all_db_rounds: list[dict],
) -> dict[str, Any]:
    """
    Translate a stored MongoDB round document into the SSE frontend payload shape.

    The stored format (from orchestrator.log_round) is:
        { round, world_state, agent_actions: [{agent, action_type, ...}], outcomes }

    The frontend SSE format (same as build_round_payload) is:
        { round, max_rounds, world_state, agents: [{..., action}], metrics_so_far }

    Args:
        db_round: single entry from simulation["rounds"] list
        max_rounds: total rounds in this simulation run
        all_db_rounds: all rounds in the run (for cumulative metrics arrays)
    """
    world_state = db_round.get("world_state", {})
    rnd = db_round.get("round", 0)

    # Build action lookup: agent_name -> action_type from stored agent_actions
    action_lookup: dict[str, str] = {}
    for entry in db_round.get("agent_actions", []):
        agent_name = entry.get("agent", "")
        action_type = entry.get("action_type", "wait")
        if agent_name:
            action_lookup[agent_name] = action_type

    # Use existing helper to build gridPos/status/grazingUnits; pass empty list
    # for live agents since we reconstruct from world_state only
    agents_payload = _assign_grid_positions([], world_state)
    # Inject real action from stored agent_actions
    for agent in agents_payload:
        agent["action"] = action_lookup.get(agent["name"], "wait")

    # Build cumulative metrics arrays from all rounds up to and including this one
    rounds_so_far = sorted(
        (r for r in all_db_rounds if r.get("round", 0) <= rnd),
        key=lambda r: r.get("round", 0),
    )
    gini_series: list[float] = []
    stock_series: list[float] = []
    for r in rounds_so_far:
        ws = r.get("world_state", {})
        gini_series.append(float(ws.get("gini", 0.0)))
        stock_series.append(float(ws.get("resource_depot", 0)))

    return {
        "round": rnd,
        "max_rounds": max_rounds,
        "world_state": world_state,
        "agents": agents_payload,
        "metrics_so_far": {
            "gini": gini_series,
            "cooperation_rate": [],  # not stored per-round in DB
            "resource_stock": stock_series,
        },
    }


async def run_simulation(
    memory_on: bool,
    num_rounds: int,
    scenario_dir: str,
    seed: int | None = None,
    on_round_complete: Callable[[dict], None] | None = None,
):
    """
    Run the simulation and optionally call on_round_complete after each round.

    Args:
        memory_on: Sets config.USE_LAYER2_MEMORY.
        num_rounds: Number of rounds to run.
        scenario_dir: Path to scenario directory (e.g. "simulations/tragedy_of_commons").
        seed: If set, random.seed(seed) for reproducibility.
        on_round_complete: Called with round_payload dict after each round.

    Returns:
        Dict with "summary" (metrics) and "rounds" (list of round payloads).
    """
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    import config.config as cfg
    from config.scenario_loader import load_scenario
    from agent_flow.agent import Agent
    from agent_flow.persona_generator import generate_persona_prompt
    from agent_flow.environment import Environment
    from config.orchestrator import Orchestrator
    from config.logger import Logger
    from agent_flow.embedding import get_embed_model
    import config.db as db

    if seed is not None:
        random.seed(seed)
    cfg.USE_LAYER2_MEMORY = memory_on

    base_dir = PROJECT_ROOT / scenario_dir
    scenario = load_scenario(str(base_dir))
    scenario["start_location"] = _get_start_location(scenario)
    scenario["rules"] = _load_rules(str(base_dir))

    get_embed_model()
    profiles = db.load_profiles()
    agent_count = scenario.get("agents", {}).get("count")
    if agent_count and len(profiles) > agent_count:
        profiles = profiles[:agent_count]

    agents = []
    for profile in profiles:
        persona = generate_persona_prompt(profile, scenario)
        agent = Agent(profile, persona, scenario)
        agents.append(agent)

    env = Environment(agents, scenario)
    logger = Logger()
    if cfg.USE_OLLAMA:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=cfg.API_BASE, api_key=cfg.API_KEY)
    else:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)

    orch = Orchestrator(agents, env, logger, client, scenario, condition="", seed=0)
    rounds_payloads = []

    for _ in range(num_rounds):
        await orch.run_round()
        payload = build_round_payload(env, agents, orch, scenario)
        rounds_payloads.append(payload)
        if on_round_complete:
            on_round_complete(payload)

    summary = orch.get_metrics_summary()
    return {"summary": summary, "rounds": rounds_payloads}