"""
environment.py — The commons environment for the heterogeneous MASTOC run.
"""

from __future__ import annotations

from typing import Optional

import networkx as nx

from config.config import NUM_ROUNDS, SPEECH_HISTORY_ROUNDS

LOCATED_AT = "LOCATED_AT"
CONTAINS = "CONTAINS"


def _get_act(round_number: int, config: dict | None = None) -> tuple[str, str]:
    acts_config = config.get("acts") if config else None
    if acts_config:
        for act in acts_config:
            if act.get("start_round", 0) <= round_number <= act.get("end_round", 0):
                return act.get("label", "?"), act.get("name", "Unknown")
    return "?", "Unknown"


class Environment:
    def __init__(self, agents, config: dict):
        self.config = config
        self.graph = nx.DiGraph()
        self.agents = {a.name: a for a in agents}
        self.round_number = 0
        self.max_rounds = config.get("simulation", {}).get("max_rounds", NUM_ROUNDS)
        self.round_messages: list[str] = []
        self.locations = [loc["name"] for loc in config.get("locations", [])]
        self.resource = config.get("resource", {})
        self.resource_name = self.resource.get("name", "resource")
        self.resource_unit = self.resource.get("unit", "units")
        self.resource_location = self.resource.get("location", "Pasture")
        self.resource_supply = int(self.resource.get("initial_supply", 0))
        self.start_location = _get_start_location(config)
        self.commons_config = config.get("commons", {})
        self.current_regeneration_rate = int(
            self.commons_config.get("regeneration_per_round", 12)
        )
        self.collapse_threshold = int(self.commons_config.get("collapse_threshold", 20))
        self.max_stock = int(self.commons_config.get("max_stock", self.resource_supply))

        self.graph.add_node("resource_depot", type="object", amount=self.resource_supply)
        for loc in self.locations:
            self.graph.add_node(loc, type="location")

        for agent in agents:
            self.graph.add_node(agent.name, type="agent", resource=0, role=agent.role)
            self.graph.add_edge(agent.name, self.start_location, relation=LOCATED_AT)
            self.graph.add_edge(self.start_location, agent.name, relation=CONTAINS)
            agent.location = self.start_location

        self.speech_log: dict[str, list[tuple[int, str, str]]] = {loc: [] for loc in self.locations}
        self.round_harvest_actions: list[dict] = []
        self.cumulative_harvest: dict[str, int] = {a.name: 0 for a in agents}
        self._last_round_total_grazed = 0
        self._pending_sanctions: list[dict] = []
        self._last_report_data: dict | None = None

    def _get_location(self, agent_name: str) -> Optional[str]:
        for neighbor in self.graph.successors(agent_name):
            if self.graph.edges[agent_name, neighbor].get("relation") == LOCATED_AT:
                return neighbor
        return None

    def _set_location(self, agent_name: str, new_location: str):
        old_location = self._get_location(agent_name)
        if old_location:
            self.graph.remove_edge(agent_name, old_location)
            self.graph.remove_edge(old_location, agent_name)
        self.graph.add_edge(agent_name, new_location, relation=LOCATED_AT)
        self.graph.add_edge(new_location, agent_name, relation=CONTAINS)
        self.agents[agent_name].location = new_location

    def _get_resource(self, agent_name: str) -> int:
        return self.graph.nodes[agent_name].get("resource", 0)

    def _set_resource(self, agent_name: str, amount: int):
        self.graph.nodes[agent_name]["resource"] = amount
        self.agents[agent_name].resource = amount

    def _get_depot_resource(self) -> int:
        return self.graph.nodes["resource_depot"].get("amount", 0)

    def _set_depot_resource(self, amount: int):
        self.graph.nodes["resource_depot"]["amount"] = max(0, amount)

    def _agents_at_location(self, location: str) -> list[str]:
        agents = []
        for node in self.graph.successors(location):
            if self.graph.edges[location, node].get("relation") == CONTAINS:
                agents.append(node)
        return agents

    def calculate_gini(self) -> float:
        values = sorted(
            self._get_resource(name)
            for name, data in self.graph.nodes(data=True)
            if data.get("type") == "agent"
        )
        n = len(values)
        if n == 0 or sum(values) == 0:
            return 0.0
        cumulative = 0.0
        for idx, value in enumerate(values, start=1):
            cumulative += (2 * idx - n - 1) * value
        return cumulative / (n * sum(values))

    def apply_pending_sanctions(self) -> list[str]:
        if not self._pending_sanctions:
            return []
        messages = []
        remaining = []
        for sanction in self._pending_sanctions:
            if sanction["round_due"] != self.round_number:
                remaining.append(sanction)
                continue
            target = sanction["target"]
            current = self._get_resource(target)
            penalty = min(2, current)
            self._set_resource(target, current - penalty)
            messages.append(
                f"Sanction enforced: {target} loses {penalty} units due to prior regulatory action."
            )
        self._pending_sanctions = remaining
        return messages

    def generate_perception(self, agent) -> str:
        parts = []
        act_label, act_desc = _get_act(self.round_number, self.config)
        parts.append(f"=== ROUND {self.round_number} of {self.max_rounds} (Act {act_label}: {act_desc}) ===")

        if self.round_number == 1 and self.config.get("scenario_text"):
            parts.append(self.config["scenario_text"])

        if self.round_messages:
            parts.extend(self.round_messages)

        current_stock = self._get_depot_resource()
        parts.append("")
        parts.append(f"ROLE: {agent.role}")
        parts.append("COMMONS STATUS:")
        if agent.role == "Scout":
            parts.append(f"  Exact stock: {current_stock} {self.resource_unit}")
            parts.append(f"  Exact regeneration rate: {self.current_regeneration_rate} per round")
            parts.append(f"  Last round total grazed: {self._last_round_total_grazed} units")
        else:
            parts.append(f"  Pasture condition: {self._qualitative_health(current_stock)}")
            parts.append(f"  Grazing pressure last round: {self._qualitative_pressure(self._last_round_total_grazed)}")
            parts.append("  You do not know the exact stock or regeneration numbers.")

        if self._last_report_data and agent.role != "Scout":
            parts.append(
                "  Scout report remembered by the council: "
                f"{self._last_report_data['message']}"
            )

        others = self._others_at_location(agent)
        parts.append(f"\nLocation: {agent.location}")
        if others:
            parts.append(f"Others here: {', '.join(others)}")
        else:
            parts.append("You are alone here.")

        recent_speech = self._recent_speech("Village Council")
        if recent_speech:
            parts.append("\nRECENT COUNCIL MESSAGES:")
            for round_num, speaker, content in recent_speech:
                parts.append(f"  [Round {round_num}] {speaker}: \"{content}\"")

        parts.append("\nYOUR STATUS:")
        parts.append(f"  Units you hold: {agent.resource}")
        parts.append(f"  Total personally grazed: {self.cumulative_harvest.get(agent.name, 0)}")
        parts.append(f"  Allowed action family: {self._allowed_action_hint(agent.role)}")
        return "\n".join(parts)

    def resolve_actions(self, actions: list[dict]) -> list[dict]:
        self.round_harvest_actions = []
        outcomes: list[dict] = []
        start_locations = {name: agent.location for name, agent in self.agents.items()}

        for action in actions:
            if action["type"] != "move":
                continue
            target = action.get("target_location")
            if not target or target == self.agents[action["agent"]].location:
                continue
            old_location = self.agents[action["agent"]].location
            self._set_location(action["agent"], target)
            outcomes.append(
                {
                    "agent": action["agent"],
                    "role": action["role"],
                    "action": "move",
                    "detail": f"Moved from {old_location} to {target}",
                }
            )

        for action in actions:
            if action["type"] != "graze":
                continue
            if action["role"] != "Herder":
                outcomes.append(
                    {
                        "agent": action["agent"],
                        "role": action["role"],
                        "action": "wait",
                        "detail": "Only herders may graze.",
                    }
                )
                continue
            if self.agents[action["agent"]].location != self.resource_location:
                outcomes.append(
                    {
                        "agent": action["agent"],
                        "role": action["role"],
                        "action": "wait",
                        "detail": "Cannot graze here — move to Pasture first.",
                    }
                )
                continue
            requested = max(0, min(2, action.get("amount") or 0))
            depot = self._get_depot_resource()
            given = min(requested, depot)
            self._set_depot_resource(depot - given)
            self._set_resource(action["agent"], self._get_resource(action["agent"]) + given)
            self.round_harvest_actions.append({"agent": action["agent"], "amount": given})
            self.cumulative_harvest[action["agent"]] = self.cumulative_harvest.get(action["agent"], 0) + given
            mode = "sustainable" if requested <= 1 else "aggressive"
            outcomes.append(
                {
                    "agent": action["agent"],
                    "role": action["role"],
                    "action": "graze",
                    "detail": f"Grazed {given} units via {mode} harvest",
                }
            )

        for action in actions:
            if action["type"] != "sanction":
                continue
            if action["role"] != "Regulator":
                outcomes.append(
                    {
                        "agent": action["agent"],
                        "role": action["role"],
                        "action": "wait",
                        "detail": "Only regulators may sanction.",
                    }
                )
                continue
            target = action.get("target_agent")
            if not target or self.agents[target].role != "Herder":
                outcomes.append(
                    {
                        "agent": action["agent"],
                        "role": action["role"],
                        "action": "wait",
                        "detail": "Sanction failed — target must be a herder.",
                    }
                )
                continue
            self._pending_sanctions.append(
                {"target": target, "round_due": self.round_number + 1, "issued_by": action["agent"]}
            )
            outcomes.append(
                {
                    "agent": action["agent"],
                    "role": action["role"],
                    "action": "sanction",
                    "detail": f"Queued sanction against {target} for next round.",
                }
            )

        for action in actions:
            if action["type"] != "report":
                continue
            stock = self._get_depot_resource()
            report_message = (
                f"Scout ecological report: stock={stock} units, "
                f"regeneration={self.current_regeneration_rate}, "
                f"last_round_grazed={self._last_round_total_grazed}"
            )
            self._last_report_data = {
                "round": self.round_number,
                "stock": stock,
                "regeneration_rate": self.current_regeneration_rate,
                "message": report_message,
            }
            self.speech_log["Village Council"].append(
                (self.round_number, action["agent"], report_message)
            )
            outcomes.append(
                {
                    "agent": action["agent"],
                    "role": action["role"],
                    "action": "report",
                    "detail": report_message,
                }
            )

        for action in actions:
            message = (action.get("message") or "").strip()
            if not message or message.upper() == "NONE":
                continue
            if start_locations.get(action["agent"]) != "Village Council":
                continue
            self.speech_log["Village Council"].append(
                (self.round_number, action["agent"], message)
            )
            outcomes.append(
                {
                    "agent": action["agent"],
                    "role": action["role"],
                    "action": "message",
                    "detail": message[:200],
                }
            )

        self._last_round_total_grazed = sum(item["amount"] for item in self.round_harvest_actions)
        return outcomes

    def set_round_messages(self, messages: list[str]) -> None:
        self.round_messages = messages

    def add_resource(self, amount: int):
        self._set_depot_resource(self._get_depot_resource() + amount)

    def get_world_state(self) -> dict:
        locations = {}
        for loc in self.locations:
            locations[loc] = self._agents_at_location(loc)
        return {
            "round": self.round_number,
            "resource_depot": self._get_depot_resource(),
            "regeneration_rate": self.current_regeneration_rate,
            "locations": locations,
            "inventories": {a.name: self._get_resource(a.name) for a in self.agents.values()},
            "roles": {a.name: a.role for a in self.agents.values()},
            "gini": self.calculate_gini(),
        }

    def _others_at_location(self, agent) -> list[str]:
        location = self._get_location(agent.name)
        if not location:
            return []
        return [name for name in self._agents_at_location(location) if name != agent.name]

    def _recent_speech(self, location: str) -> list[tuple[int, str, str]]:
        cutoff = self.round_number - SPEECH_HISTORY_ROUNDS
        return [
            (round_num, speaker, content)
            for round_num, speaker, content in self.speech_log[location]
            if round_num > cutoff
        ]

    @property
    def resource_depot(self) -> int:
        return self._get_depot_resource()

    def get_agents_at_location(self, location: str, exclude: str | None = None) -> set[str]:
        return {
            name for name, agent in self.agents.items()
            if agent.location == location and name != exclude
        }

    @staticmethod
    def _qualitative_health(stock: int) -> str:
        if stock <= 20:
            return "collapsed and brown"
        if stock <= 40:
            return "fragile and thinning"
        if stock <= 80:
            return "stressed but still recovering"
        return "lush and resilient"

    @staticmethod
    def _qualitative_pressure(total_grazed: int) -> str:
        if total_grazed >= 12:
            return "heavy"
        if total_grazed >= 6:
            return "moderate"
        if total_grazed > 0:
            return "light"
        return "minimal"

    @staticmethod
    def _allowed_action_hint(role: str) -> str:
        if role == "Herder":
            return "move, message, graze, wait"
        if role == "Regulator":
            return "move, message, sanction, wait"
        return "move, message, report_data, wait"


def _get_start_location(config: dict) -> str:
    for loc in config.get("locations", []):
        if loc.get("starting_location"):
            return loc.get("name")
    locations = config.get("locations", [])
    if locations:
        return locations[0].get("name")
    return "Village Council"
