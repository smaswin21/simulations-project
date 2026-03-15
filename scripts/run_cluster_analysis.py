"""
run_cluster_analysis.py — Compare similar vs diverse 10-agent cohorts with memory on.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import math
import os
import sys
import tempfile
from datetime import date, datetime, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

import config.config as cfg
import config.db as db
from agent_flow.agent import Agent
from agent_flow.embedding import get_embed_model
from agent_flow.environment import Environment
from agent_flow.persona_generator import generate_persona_prompt
from config.llms import create_provider
from config.logger import Logger
from config.orchestrator import Orchestrator
from config.scenario_loader import load_scenario
from run_simulation import assign_roles

TRAIT_NAMES = [
    "extraversion",
    "agreeableness",
    "conscientiousness",
    "neuroticism",
    "openness",
]
SIMILAR_COHORT_PATH = PROJECT_ROOT / "EDA" / "cohort_similar_extraversion.json"


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


def load_cohort_file(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def index_profiles_by_pid(profiles: list[dict]) -> dict[str, dict]:
    return {str(profile["pid"]): profile for profile in profiles}


def merge_profiles_by_pid(cohort_profiles: list[dict], profile_pool: list[dict]) -> list[dict]:
    indexed = index_profiles_by_pid(profile_pool)
    merged = []
    for item in cohort_profiles:
        pid = str(item["pid"])
        profile = dict(indexed.get(pid, item))
        profile["pid"] = pid
        profile.setdefault("name", f"Agent {pid}")
        for key, value in item.items():
            profile.setdefault(key, value)
        merged.append(profile)
    return merged


def trait_vector(profile: dict) -> np.ndarray:
    big_five = profile["big_five"]
    return np.asarray([float(big_five[name]) for name in TRAIT_NAMES], dtype=np.float64)


def standardize_vectors(profiles: list[dict]) -> np.ndarray:
    matrix = np.vstack([trait_vector(profile) for profile in profiles])
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std[std == 0.0] = 1.0
    return (matrix - mean) / std


def average_pairwise_distance(vectors: np.ndarray) -> float:
    count = len(vectors)
    if count < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for idx in range(count):
        for jdx in range(idx + 1, count):
            total += float(np.linalg.norm(vectors[idx] - vectors[jdx]))
            pairs += 1
    return total / pairs if pairs else 0.0


def build_diverse_cohort(
    profile_pool: list[dict],
    exclude_pids: set[str],
    size: int = 10,
) -> list[dict]:
    candidates = [
        dict(profile)
        for profile in profile_pool
        if str(profile["pid"]) not in exclude_pids
    ]
    candidates.sort(key=lambda item: str(item["pid"]))
    if len(candidates) < size:
        raise ValueError(f"Not enough candidate profiles to build a diverse cohort of size {size}.")

    standardized = standardize_vectors(candidates)
    selected_indices: list[int] = []

    start_index = 0
    best_norm = -1.0
    best_pid = ""
    for idx, profile in enumerate(candidates):
        norm = float(np.linalg.norm(standardized[idx]))
        pid = str(profile["pid"])
        if norm > best_norm or (math.isclose(norm, best_norm) and pid < best_pid):
            best_norm = norm
            best_pid = pid
            start_index = idx
    selected_indices.append(start_index)

    while len(selected_indices) < size:
        best_index = None
        best_score = (-1.0, -1.0)
        best_pid = ""
        for idx, profile in enumerate(candidates):
            if idx in selected_indices:
                continue
            distances = [
                float(np.linalg.norm(standardized[idx] - standardized[selected_idx]))
                for selected_idx in selected_indices
            ]
            min_distance = min(distances)
            mean_distance = sum(distances) / len(distances)
            pid = str(profile["pid"])
            score = (min_distance, mean_distance)
            if (
                best_index is None
                or score[0] > best_score[0]
                or (math.isclose(score[0], best_score[0]) and score[1] > best_score[1])
                or (
                    math.isclose(score[0], best_score[0])
                    and math.isclose(score[1], best_score[1])
                    and pid < best_pid
                )
            ):
                best_index = idx
                best_score = score
                best_pid = pid

        if best_index is None:
            break
        selected_indices.append(best_index)

    selected = [dict(candidates[idx]) for idx in selected_indices]
    for profile in selected:
        profile["pid"] = str(profile["pid"])
        profile.setdefault("name", f"Agent {profile['pid']}")
        profile["cohort_type"] = "diverse"
    return selected


def cohort_trait_summary(profiles: list[dict]) -> dict:
    matrix = np.vstack([trait_vector(profile) for profile in profiles])
    standardized = standardize_vectors(profiles)
    trait_mean = {}
    trait_std = {}
    for idx, trait in enumerate(TRAIT_NAMES):
        trait_mean[trait] = float(matrix[:, idx].mean())
        trait_std[trait] = float(matrix[:, idx].std())
    return {
        "size": len(profiles),
        "pids": [str(profile["pid"]) for profile in profiles],
        "mean_big_five": trait_mean,
        "std_big_five": trait_std,
        "average_pairwise_distance": average_pairwise_distance(standardized),
    }


async def run_single(
    seed: int,
    cohort_label: str,
    profiles: list[dict],
    num_rounds: int,
    scenario_dir: str,
) -> dict:
    cfg.USE_LAYER2_MEMORY = True

    scenario = load_scenario(scenario_dir)
    scenario["start_location"] = _get_start_location(scenario)
    scenario["rules"] = _load_rules(scenario_dir)
    scenario["seed"] = seed

    provider = create_provider()
    role_assignments = assign_roles(profiles, seed=seed, count=len(profiles))

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
                seed_context={"seed": seed, "cohort": cohort_label},
            )
        )

    env = Environment(agents, scenario)
    logger = Logger()
    logger.log_config(
        profiles=[{**profile, "role": role} for profile, role in role_assignments],
        settings={
            "analysis": "cluster_memory_on",
            "cohort": cohort_label,
            "num_rounds": num_rounds,
            "num_agents": len(agents),
            "seed": seed,
            "scenario": scenario_dir,
            "llm_provider": provider.settings.provider,
            "llm_model": provider.settings.model,
            "memory_on": True,
        },
    )
    orch = Orchestrator(
        agents=agents,
        environment=env,
        logger=logger,
        llm_provider=provider,
        scenario=scenario,
        condition=cohort_label,
        seed=seed,
    )
    await orch.run_simulation(num_rounds)

    metrics = orch.get_metrics_summary()
    metrics["seed"] = seed
    metrics["cohort"] = cohort_label
    metrics["cohort_pids"] = [str(profile["pid"]) for profile in profiles]
    metrics["assigned_roles"] = {profile["pid"]: role for profile, role in role_assignments}
    return metrics


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        rows = []
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSONL in {path} at line {line_number}: {exc.msg}"
                ) from exc
        return rows


def summarize_runs(runs: list[dict]) -> dict:
    metric_names = [
        "resource_stock_final",
        "gini_final",
        "cooperation_rate_final",
        "accountability_rate",
        "speech_diversity_final",
        "numeric_grounding_final",
    ]
    summary = {"num_runs": len(runs)}
    for metric in metric_names:
        values = [float(run.get(metric, 0.0)) for run in runs]
        summary[metric] = {
            "mean": float(np.mean(values)) if values else 0.0,
            "std": float(np.std(values)) if values else 0.0,
        }
    return summary


def compare_cohorts(similar_runs: list[dict], diverse_runs: list[dict]) -> dict:
    similar_summary = summarize_runs(similar_runs)
    diverse_summary = summarize_runs(diverse_runs)
    stock_delta = (
        diverse_summary["resource_stock_final"]["mean"]
        - similar_summary["resource_stock_final"]["mean"]
    )
    gini_delta = (
        diverse_summary["gini_final"]["mean"]
        - similar_summary["gini_final"]["mean"]
    )

    if stock_delta > 0 and gini_delta < 0:
        winner = "diverse_bigfive"
    elif stock_delta < 0 and gini_delta > 0:
        winner = "similar_extraversion"
    else:
        winner = "tradeoff"

    return {
        "winner": winner,
        "stock_mean_delta_diverse_minus_similar": stock_delta,
        "gini_mean_delta_diverse_minus_similar": gini_delta,
    }


def _to_json_safe(value):
    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def exportable_profile(profile: dict) -> dict:
    export_keys = [
        "pid",
        "name",
        "big_five",
        "crt_score",
        "crt_max",
        "risk_preference",
        "has_dependents",
        "cohort_type",
    ]
    trimmed = {key: profile[key] for key in export_keys if key in profile}
    trimmed["pid"] = str(trimmed["pid"])
    trimmed.setdefault("name", f"Agent {trimmed['pid']}")
    return _to_json_safe(trimmed)


def save_json(path: Path, payload: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(_to_json_safe(payload), handle, indent=2)


def jsonl_line(payload: dict) -> str:
    return json.dumps(_to_json_safe(payload)) + "\n"


def open_temp_jsonl(path: Path):
    return tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}.",
        suffix=".jsonl.tmp",
        delete=False,
    )


def promote_temp_jsonl(temp_path: str | Path, final_path: Path) -> None:
    Path(temp_path).replace(final_path)


async def main(num_runs: int, num_rounds: int, scenario_dir: str, tag: str = ""):
    print(f"\n{'=' * 64}")
    print("  CLUSTER-SPECIFIC MEMORY-ON ANALYSIS")
    print(f"  Runs per cohort: {num_runs}")
    print(f"  Rounds per run:  {num_rounds}")
    print(f"  Scenario:        {scenario_dir}")
    print(f"{'=' * 64}\n")

    get_embed_model()

    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    suffix = f"_{tag}" if tag else ""
    if not tag:
        print("  Note: use --tag when running multiple analyses in parallel to keep separate artifact paths.\n")

    all_profiles = db.load_profiles()
    similar_seed_profiles = load_cohort_file(SIMILAR_COHORT_PATH)
    similar_profiles = merge_profiles_by_pid(similar_seed_profiles, all_profiles)
    similar_pids = {str(profile["pid"]) for profile in similar_profiles}
    diverse_profiles = build_diverse_cohort(all_profiles, exclude_pids=similar_pids, size=10)

    diverse_cohort_path = results_dir / f"cohort_diverse_bigfive{suffix}.json"
    similar_results_path = results_dir / f"cluster_similar_extraversion{suffix}.jsonl"
    diverse_results_path = results_dir / f"cluster_diverse_bigfive{suffix}.jsonl"
    summary_path = results_dir / f"cluster_analysis_summary{suffix}.json"

    save_json(diverse_cohort_path, [exportable_profile(profile) for profile in diverse_profiles])

    seeds = list(range(42, 42 + num_runs))
    similar_runs: list[dict] = []
    diverse_runs: list[dict] = []
    similar_temp = open_temp_jsonl(similar_results_path)
    diverse_temp = open_temp_jsonl(diverse_results_path)

    try:
        for idx, seed in enumerate(seeds, start=1):
            print(f"\n  --- Similar cohort {idx}/{num_runs} (seed={seed}) ---")
            metrics = _to_json_safe(
                await run_single(seed, "similar_extraversion", similar_profiles, num_rounds, scenario_dir)
            )
            similar_runs.append(metrics)
            similar_temp.write(jsonl_line(metrics))
            similar_temp.flush()

        for idx, seed in enumerate(seeds, start=1):
            print(f"\n  --- Diverse cohort {idx}/{num_runs} (seed={seed}) ---")
            metrics = _to_json_safe(
                await run_single(seed, "diverse_bigfive", diverse_profiles, num_rounds, scenario_dir)
            )
            diverse_runs.append(metrics)
            diverse_temp.write(jsonl_line(metrics))
            diverse_temp.flush()
    except Exception:
        similar_temp.close()
        diverse_temp.close()
        for temp_file in (similar_temp.name, diverse_temp.name):
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        raise
    else:
        similar_temp.close()
        diverse_temp.close()
        promote_temp_jsonl(similar_temp.name, similar_results_path)
        promote_temp_jsonl(diverse_temp.name, diverse_results_path)

    summary = {
        "analysis": "cluster_memory_on",
        "scenario": scenario_dir,
        "runs": num_runs,
        "rounds": num_rounds,
        "seeds": seeds,
        "artifacts": {
            "similar_results": str(similar_results_path),
            "diverse_results": str(diverse_results_path),
            "diverse_cohort": str(diverse_cohort_path),
        },
        "cohorts": {
            "similar_extraversion": {
                "trait_summary": cohort_trait_summary(similar_profiles),
                "run_summary": summarize_runs(similar_runs),
            },
            "diverse_bigfive": {
                "trait_summary": cohort_trait_summary(diverse_profiles),
                "run_summary": summarize_runs(diverse_runs),
            },
        },
        "comparison": compare_cohorts(similar_runs, diverse_runs),
        "overlap_check": sorted(
            set(str(profile["pid"]) for profile in similar_profiles)
            & set(str(profile["pid"]) for profile in diverse_profiles)
        ),
    }
    save_json(summary_path, summary)

    print("\nArtifacts written:")
    print(f"  {similar_results_path}")
    print(f"  {diverse_results_path}")
    print(f"  {diverse_cohort_path}")
    print(f"  {summary_path}")
    print("\nComparison summary:")
    print(f"  Winner: {summary['comparison']['winner']}")
    print(
        "  Diverse minus similar final stock mean: "
        f"{summary['comparison']['stock_mean_delta_diverse_minus_similar']:.3f}"
    )
    print(
        "  Diverse minus similar final gini mean: "
        f"{summary['comparison']['gini_mean_delta_diverse_minus_similar']:.3f}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run cluster-specific memory-on cohort analysis")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=cfg.NUM_ROUNDS)
    parser.add_argument("--scenario", type=str, default="simulations/tragedy_of_commons")
    parser.add_argument("--tag", type=str, default="")
    args = parser.parse_args()
    asyncio.run(main(args.runs, args.rounds, args.scenario, args.tag))
