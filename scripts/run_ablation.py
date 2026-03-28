"""
run_ablation.py — Run memory OFF vs memory ON ablations.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config.config as cfg
from agent_flow.embedding import get_embed_model
from config.llms import add_selection_args, build_settings, resolve_model_selection
from config.orchestrator import Orchestrator
from config.simulation_setup import build_simulation_setup


async def run_single(
    seed: int,
    condition: str,
    num_rounds: int,
    scenario_dir: str,
    llm_settings,
    cohort_file: str | None = None,
    cohort_source: str | None = None,
) -> dict:
    cfg.USE_LAYER2_MEMORY = condition == "B"

    setup = build_simulation_setup(
        seed=seed,
        scenario_dir=scenario_dir,
        llm_settings=llm_settings,
        num_rounds=num_rounds,
        cohort_file=cohort_file,
        cohort_source=cohort_source,
        seed_context={"condition": condition},
    )
    scenario = setup.scenario
    provider = setup.provider
    agents = setup.agents
    env = setup.environment
    logger = setup.logger
    cohort_meta = setup.cohort_meta
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
    llm_settings=None,
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
    llm_settings = llm_settings or build_settings()

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
                llm_settings,
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
                llm_settings,
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
    add_selection_args(parser)
    args = parser.parse_args()
    try:
        choice = resolve_model_selection(args)
        llm_settings = build_settings(provider=choice.provider, model=choice.model)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Using LLM provider: {llm_settings.provider}")
    print(f"Using LLM model:    {llm_settings.model}")
    asyncio.run(
        main(
            args.runs,
            args.rounds,
            args.scenario,
            llm_settings,
            args.tag,
            args.cohort_file,
            args.cohort_source,
        )
    )
