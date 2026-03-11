"""
environment.py — The simulation world.

Manages locations, resources, speech logs,
and generates what each agent can perceive each round.

Uses a NetworkX DiGraph to represent the world:
- Nodes: locations, agents, objects (resource depot)
- Edges: LOCATED_AT, CONTAINS
- Node attributes: agent state (resource), location state
"""

from typing import Optional

import networkx as nx

from config.config import SPEECH_HISTORY_ROUNDS, NUM_ROUNDS

LOCATED_AT = "LOCATED_AT"
CONTAINS = "CONTAINS"
HAS_STATE = "HAS_STATE"


def _get_act(round_number: int, config: dict | None = None) -> tuple[str, str]:
    """Return (act_label, act_description) for the given round."""
    acts_config = None
    if config:
        acts_config = config.get("acts")

    if acts_config:
        for act in acts_config:
            start = act.get("start_round", 0)
            end = act.get("end_round", 0)
            label = act.get("label", "?")
            name = act.get("name", "Unknown")
            if start <= round_number <= end:
                return label, name
    return "?", "Unknown"


class Environment:
    def __init__(self, agents, config: dict):
        """
        Args:
            agents: list of Agent objects
            config: scenario configuration dict
        """
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
        self.resource_location = self.resource.get("location")
        self.resource_supply = int(self.resource.get("initial_supply", 0))
        self.start_location = _get_start_location(config)

        # ── Build graph ──────────────────────────────────────
        self.graph.add_node("resource_depot", type="object", amount=self.resource_supply)
        for loc in self.locations:
            self.graph.add_node(loc, type="location")

        for a in agents:
            self.graph.add_node(
                a.name,
                type="agent",
                resource=0,
            )
            self.graph.add_edge(a.name, self.start_location, relation=LOCATED_AT)
            self.graph.add_edge(self.start_location, a.name, relation=CONTAINS)
            a.location = self.start_location

        self.speech_log: dict[str, list] = {loc: [] for loc in self.locations}
        self.info_board: list = []

        # ── Harvest tracking (for cooperation metrics) ───────
        self.round_harvest_actions: list[dict] = []
        self.cumulative_harvest: dict[str, int] = {a.name: 0 for a in agents}

    # ── Graph accessors ──────────────────────────────────────

    def _get_location(self, agent_name: str) -> Optional[str]:
        """Get agent's current location via graph traversal."""
        for neighbor in self.graph.successors(agent_name):
            if self.graph.edges[agent_name, neighbor].get("relation") == LOCATED_AT:
                return neighbor
        return None

    def _set_location(self, agent_name: str, new_location: str):
        """Update agent's location via graph edge changes."""
        old_location = self._get_location(agent_name)
        if old_location:
            self.graph.remove_edge(agent_name, old_location)
            self.graph.remove_edge(old_location, agent_name)

        self.graph.add_edge(agent_name, new_location, relation=LOCATED_AT)
        self.graph.add_edge(new_location, agent_name, relation=CONTAINS)
        self.agents[agent_name].location = new_location

    def _get_resource(self, agent_name: str) -> int:
        """Get agent's resource count from node attribute."""
        return self.graph.nodes[agent_name].get("resource", 0)

    def _set_resource(self, agent_name: str, amount: int):
        """Set agent's resource count via node attribute."""
        self.graph.nodes[agent_name]["resource"] = amount
        self.agents[agent_name].resource = amount

    def _get_depot_resource(self) -> int:
        """Get depot resource count."""
        return self.graph.nodes["resource_depot"].get("amount", 0)

    def _set_depot_resource(self, amount: int):
        """Set depot resource count."""
        self.graph.nodes["resource_depot"]["amount"] = amount

    # ── Commons pool resource methods ────────────────────────

    def get_resource(self, resource_name: str) -> dict:
        """Get stock for a named resource (commons pool).

        For now, all resources map to the single resource_depot node.
        """
        return {"stock": self._get_depot_resource()}

    def deduct_resource(self, resource_name: str, amount: int):
        """Deduct from a named resource pool."""
        current = self._get_depot_resource()
        self._set_depot_resource(max(0, current - amount))

    def set_resource_stock(self, resource_name: str, amount: int):
        """Set the stock level for a named resource."""
        self._set_depot_resource(amount)

    def _agents_at_location(self, location: str) -> list[str]:
        """Get list of agent names at a location via graph traversal."""
        agents = []
        for node in self.graph.successors(location):
            if self.graph.edges[location, node].get("relation") == CONTAINS:
                agents.append(node)
        return agents

    def calculate_gini(self) -> float:
        """Calculate Gini coefficient of resource distribution among agents."""
        resources = sorted(
            self._get_resource(name)
            for name, data in self.graph.nodes(data=True)
            if data.get("type") == "agent"
        )
        n = len(resources)
        if n == 0 or sum(resources) == 0:
            return 0.0
        cumulative = 0.0
        for i, x in enumerate(resources):
            cumulative += (2 * (i + 1) - n - 1) * x
        return cumulative / (n * sum(resources))

    # ── Condensed reminder (shown rounds 2+) ─────────────────

    def _build_condensed_reminder(self) -> str:
        """Short reminder of key mechanics for rounds after the first."""
        loc_list = " / ".join(self.locations)
        extraction_action = self.config.get("resource", {}).get(
            "resource_extraction_action", "CLAIM"
        ).upper()
        return (
            f"REMINDER: {self.resource_name.title()} is at the {self.resource_location}. "
            f"You must MOVE there first, then {extraction_action} to take it.\n"
            f"Locations: {loc_list}\n"
            f"Actions: SPEAK | MOVE | {extraction_action} (at {self.resource_location} only) | SHARE (to someone at your location)"
        )

    # ── Perception ───────────────────────────────────────────

    def generate_perception(self, agent) -> str:
        """Build the text describing what this agent can currently observe."""
        parts = []

        # Round + Act context
        act_label, act_desc = _get_act(self.round_number, self.config)
        parts.append(
            f"=== ROUND {self.round_number} of {self.max_rounds} "
            f"(Act {act_label}: {act_desc}) ==="
        )

        # Scenario text (full on round 1, condensed after)
        if self.round_number == 1 and self.config.get("scenario_text"):
            parts.append(self.config["scenario_text"])
        elif self.round_number > 1:
            parts.append(self._build_condensed_reminder())

        # Event messages for this round
        if self.round_messages:
            parts.extend(self.round_messages)

        # Commons status
        commons_config = self.config.get("commons", {})
        current_stock = self._get_depot_resource()
        initial_stock = self.resource_supply
        sustainable_quota = commons_config.get("default_sustainable_quota", 1)
        regen_rate = getattr(self, "_commons_regeneration_override", None)
        if regen_rate is None:
            regen_rate = commons_config.get("regeneration_per_round", 12)
        last_round_total = sum(h["amount"] for h in self.round_harvest_actions)
        sustainable_limit = regen_rate
        collapse_threshold = commons_config.get("collapse_threshold", 20)

        parts.append("")
        parts.append("COMMONS STATUS:")
        parts.append(f"  Pasture stock: {current_stock} units remaining (started: {initial_stock})")
        parts.append(f"  Regeneration rate: {regen_rate} units/round")
        parts.append(f"  Sustainable quota: {sustainable_quota} unit per herder per round")
        if current_stock < collapse_threshold:
            parts.append(f"  !! ECOSYSTEM COLLAPSED — regeneration has stopped !!")
        elif current_stock < collapse_threshold * 2:
            parts.append(f"  WARNING: Pasture dangerously low (collapse below {collapse_threshold})")
        if self.round_number > 1:
            if last_round_total > sustainable_limit:
                parts.append(
                    f"  Last round total grazing: {last_round_total} units "
                    f"(EXCEEDED sustainable limit of {sustainable_limit})"
                )
            else:
                parts.append(
                    f"  Last round total grazing: {last_round_total} units "
                    f"(within sustainable limit of {sustainable_limit})"
                )

        # Location + others
        others = self._others_at_location(agent)
        parts.append(f"\nLocation: {agent.location}")
        if others:
            parts.append(f"Others here: {', '.join(others)}")
        else:
            parts.append("You are alone here.")

        # Recent speech at this location
        recent_speech = self._recent_speech(agent.location)
        if recent_speech:
            parts.append("\nRECENT CONVERSATION:")
            for round_num, speaker, content in recent_speech:
                parts.append(f"  [Round {round_num}] {speaker}: \"{content}\"")

        # Depot stock (if at depot)
        if agent.location == self.resource_location:
            parts.append(
                f"\n{self.resource_name.title()} available at depot: "
                f"{self._get_depot_resource()} {self.resource_unit}"
            )

        # Agent's own status
        parts.append("\nYOUR STATUS:")
        parts.append(
            f"  {self.resource_name.title()} you hold: "
            f"{agent.resource} {self.resource_unit}"
        )
        agent_harvest = self.cumulative_harvest.get(agent.name, 0)
        parts.append(f"  Total grazed so far: {agent_harvest} {self.resource_unit}")
        parts.append(
            f"  Pasture stock: {self._get_depot_resource()} {self.resource_unit}"
        )

        if self.info_board:
            parts.append(f"\nINFO BOARD ({len(self.info_board)} posts):")
            for round_num, author, message in self.info_board[-3:]:
                parts.append(f"  [Round {round_num}] {author}: \"{message}\"")

        return "\n".join(parts)

    # ── Action resolution ────────────────────────────────────

    def resolve_actions(self, actions: list[dict]) -> list[dict]:
        """
        Process all agent actions for one round.

        Order: MOVE → CLAIM → SHARE → SPEAK → WAIT
        Returns list of outcome dicts.
        """
        self.round_harvest_actions = []
        outcomes = []

        for a in actions:
            if a["type"] == "move":
                agent = self.agents[a["agent"]]
                old_loc = agent.location
                self._set_location(a["agent"], a["target_location"])
                outcomes.append({
                    "agent": a["agent"],
                    "action": "move",
                    "detail": f"Moved from {old_loc} to {a['target_location']}",
                })

        for a in actions:
            if a["type"] == "claim":
                agent = self.agents[a["agent"]]
                requested = a["amount"]
                depot = self._get_depot_resource()
                given = min(requested, depot)
                if given > 0:
                    self._set_depot_resource(depot - given)
                    current = self._get_resource(a["agent"])
                    self._set_resource(a["agent"], current + given)
                    # Track for cooperation metrics
                    self.round_harvest_actions.append({
                        "agent": a["agent"],
                        "amount": given,
                    })
                    self.cumulative_harvest[a["agent"]] = (
                        self.cumulative_harvest.get(a["agent"], 0) + given
                    )
                outcomes.append({
                    "agent": a["agent"],
                    "action": "claim",
                    "detail": (
                        f"Claimed {given} {self.resource_unit} "
                        f"(requested {requested})"
                    ),
                })

        for a in actions:
            if a["type"] == "share":
                giver = self.agents[a["agent"]]
                target_name = a["target_agent"]
                amount = a["amount"]
                giver_location = self._get_location(a["agent"])
                target_location = self._get_location(target_name)
                giver_resource = self._get_resource(a["agent"])

                if (target_name in self.agents
                        and giver_location == target_location
                        and amount <= giver_resource):
                    self._set_resource(a["agent"], giver_resource - amount)
                    target_resource = self._get_resource(target_name)
                    self._set_resource(target_name, target_resource + amount)
                    detail = (
                        f"Shared {amount} {self.resource_unit} with {target_name}"
                    )
                else:
                    detail = (
                        f"Share failed (invalid target or insufficient {self.resource_name})"
                    )
                outcomes.append({
                    "agent": a["agent"],
                    "action": "share",
                    "detail": detail,
                })

        for a in actions:
            if a["type"] == "speak":
                agent = self.agents[a["agent"]]
                self.speech_log[agent.location].append(
                    (self.round_number, a["agent"], a["content"])
                )
                outcomes.append({
                    "agent": a["agent"],
                    "action": "speak",
                    "detail": a["content"][:200],
                })

        return outcomes

    # ── State mutators (used by events/rules) ────────────────

    def set_round_messages(self, messages: list[str]) -> None:
        self.round_messages = messages

    def add_resource(self, amount: int):
        """Add resource to the depot (used by events)."""
        current = self._get_depot_resource()
        self._set_depot_resource(current + amount)

    def get_world_state(self) -> dict:
        """Full world snapshot for logging."""
        locations = {}
        for loc in self.locations:
            agents_here = self._agents_at_location(loc)
            locations[loc] = agents_here

        return {
            "round": self.round_number,
            "resource_depot": self._get_depot_resource(),
            "locations": locations,
            "inventories": {a.name: self._get_resource(a.name) for a in self.agents.values()},
            "gini": self.calculate_gini(),
            "info_board_count": len(self.info_board),
        }

    def __others_at_location(self, agent) -> list[str]:
        """Names of other agents at the same location."""
        location = self._get_location(agent.name)
        if not location:
            return []
        others = self._agents_at_location(location)
        return [a for a in others if a != agent.name]

    def _others_at_location(self, agent) -> list[str]:
        """Names of other agents at the same location."""
        return self.__others_at_location(agent)

    def _recent_speech(self, location: str) -> list:
        """Get speech at this location from the last N rounds."""
        cutoff = self.round_number - SPEECH_HISTORY_ROUNDS
        return [
            (r, speaker, content)
            for r, speaker, content in self.speech_log[location]
            if r > cutoff
        ]

    @property
    def resource_depot(self) -> int:
        """Generic resource depot count."""
        return self._get_depot_resource()

    def get_agents_at_location(self, location: str, exclude: str | None = None) -> set[str]:
        """Return the set of agent names currently at the given location.

        Args:
            location: location name to query
            exclude: optional agent name to exclude (typically the querying agent)

        Returns:
            Set of agent names at that location (excluding *exclude* if given).
        """
        result = {
            name for name, agent in self.agents.items()
            if agent.location == location and name != exclude
        }
        return result


def _get_start_location(config: dict) -> str:
    for loc in config.get("locations", []):
        if loc.get("starting_location"):
            return loc.get("name")
    locations = config.get("locations", [])
    if locations:
        return locations[0].get("name")
    return "Village Square"
