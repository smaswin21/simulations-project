"""
run_simulation.py — Entry point.
"""

import argparse
import asyncio
from pathlib import Path

from agent_flow.embedding import get_embed_model
from config.config import DEFAULT_SEED, NUM_ROUNDS
from config.llms import add_selection_args, build_settings, resolve_model_selection
from config.orchestrator import Orchestrator
from config.simulation_setup import build_simulation_setup


def _auto_save_memory_plot(logger, scenario: dict, num_rounds: int) -> Path | None:
    simulation_id = logger.simulation_id
    if not simulation_id:
        return None

    from scripts import plot_memory_only

    sim_name = scenario.get("simulation", {}).get("name", "Simulation")
    title = f"{sim_name} — Memory ON ({num_rounds} rounds)"
    try:
        destination = plot_memory_only.save_simulation_plot(
            simulation_id=simulation_id,
            title=title,
        )
    except Exception as exc:
        print(f"Warning: failed to save memory plot for simulation {simulation_id}: {exc}")
        return None

    print(f"Memory plot saved to: {destination}")
    return destination


async def main(
    num_rounds: int,
    scenario_dir: str,
    seed: int,
    llm_settings=None,
    cohort_file: str | None = None,
    cohort_source: str | None = None,
):
    get_embed_model()

    llm_settings = llm_settings or build_settings()
    setup = build_simulation_setup(
        seed=seed,
        scenario_dir=scenario_dir,
        llm_settings=llm_settings,
        num_rounds=num_rounds,
        cohort_file=cohort_file,
        cohort_source=cohort_source,
    )
    scenario = setup.scenario
    provider = setup.provider
    agents = setup.agents
    env = setup.environment
    logger = setup.logger
    role_assignments = setup.role_assignments
    cohort_meta = setup.cohort_meta

    logger.log_config(
        profiles=[{**profile, "role": role} for profile, role in role_assignments],
        settings={
            "num_rounds": num_rounds,
            "num_agents": len(agents),
            "seed": seed,
            "llm_provider": provider.settings.provider,
            "llm_model": provider.settings.model,
            "cohort_label": cohort_meta["cohort_label"],
            "cohort_type": cohort_meta["cohort_type"],
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
    _auto_save_memory_plot(logger, scenario, num_rounds)


def build_parser() -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--cohort-file",
        type=str,
        default=None,
        help="Path to a JSON cohort file for similar-trait runs",
    )
    parser.add_argument(
        "--cohort-source",
        type=str,
        default=None,
        help="Profile source to use when not providing a cohort file (use 'mongo')",
    )
    add_selection_args(parser)
    return parser


def resolve_llm_settings(args, *, input_func=input, is_interactive: bool | None = None):
    choice = resolve_model_selection(
        args,
        input_func=input_func,
        is_interactive=is_interactive,
    )
    return build_settings(provider=choice.provider, model=choice.model)


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    try:
        llm_settings = resolve_llm_settings(args)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Using LLM provider: {llm_settings.provider}")
    print(f"Using LLM model:    {llm_settings.model}")
    asyncio.run(
        main(
            args.rounds,
            args.scenario,
            args.seed,
            llm_settings,
            args.cohort_file,
            args.cohort_source,
        )
    )
