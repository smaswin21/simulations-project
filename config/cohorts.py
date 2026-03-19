"""
cohorts.py — Helpers for loading experiment cohorts.
"""

from __future__ import annotations

from pathlib import Path

import config.db as db

REQUIRED_PROFILE_FIELDS = {
    "pid",
    "name",
    "big_five",
    "crt_score",
    "crt_max",
    "risk_preference",
    "has_dependents",
}


def load_cohort_profiles(
    cohort_file: str | None = None,
    cohort_source: str | None = None,
) -> tuple[list[dict], dict[str, str]]:
    """
    Load either a local JSON cohort or the default MongoDB profile pool.
    """
    if cohort_file and cohort_source:
        raise ValueError("Use only one of --cohort-file or --cohort-source.")
    if cohort_source not in {None, "mongo"}:
        raise ValueError("Unsupported cohort source. Use 'mongo' or provide --cohort-file.")

    if cohort_file:
        raw_profiles = db.load_profiles_from_json(cohort_file)
        mongo_profiles = {profile["pid"]: profile for profile in db.load_profiles()}
        profiles = []
        for row in raw_profiles:
            pid = str(row.get("pid", ""))
            hydrated = {**mongo_profiles.get(pid, {}), **row}
            hydrated["pid"] = pid
            missing = sorted(REQUIRED_PROFILE_FIELDS - hydrated.keys())
            if missing:
                raise ValueError(
                    f"Cohort file {cohort_file} is missing required fields for pid={pid}: {', '.join(missing)}"
                )
            profiles.append(hydrated)

        label = Path(cohort_file).stem.removeprefix("cohort_")
        return profiles, {
            "cohort_type": "similar",
            "cohort_label": label,
        }

    profiles = db.load_profiles()
    return profiles, {
        "cohort_type": "diverse",
        "cohort_label": "diverse_traits",
    }
