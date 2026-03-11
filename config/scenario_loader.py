from pathlib import Path
from typing import Any

import yaml


def load_scenario(scenario_dir: str | Path) -> dict[str, Any]:
    base_path = Path(scenario_dir)
    config_path = base_path / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    config["events"] = []

    description_file = config.get("simulation", {}).get("description_file")
    if description_file:
        scenario_path = base_path / description_file
        if scenario_path.exists():
            with open(scenario_path, "r", encoding="utf-8") as handle:
                scenario_text = handle.read()
            config["scenario_text"] = _render_scenario_text(config, scenario_text)

    _normalize_scenario(config)
    return config


class _DefaultFormatDict(dict):
    """Dict subclass that returns '{key}' for missing keys in str.format_map()."""
    def __missing__(self, key):
        return f"{{{key}}}"


def _render_scenario_text(config: dict[str, Any], scenario_text: str) -> str:
    resource = config.get("resource", {})
    agents_config = config.get("agents", {})

    template_vars = _DefaultFormatDict({
        "num_agents": agents_config.get("count", "?"),
        "initial_supply": resource.get("initial_supply", "?"),
        "initial_stock": resource.get("initial_supply", "?"),
        "resource_name": resource.get("name", "resource"),
        "resource_unit": resource.get("unit", "units"),
        "resource_location": resource.get("location", "depot"),
    })

    return scenario_text.format_map(template_vars)


def _normalize_scenario(config: dict[str, Any]) -> None:
    locations = config.get("world", {}).get("locations", [])
    config["locations"] = locations

    resource = config.get("resource", {})
    if not resource:
        resources = config.get("resources", {})
        if resources:
            resource = next(iter(resources.values()))
            config["resource"] = resource

    if not config.get("scenario_text"):
        config["scenario_text"] = ""


def build_location_aliases(locations: list[dict[str, Any]]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for loc in locations:
        name = loc.get("name")
        if not name:
            continue
        alias_map[name.lower()] = name
        for alias in loc.get("aliases", []):
            alias_map[str(alias).lower()] = name
    return alias_map
