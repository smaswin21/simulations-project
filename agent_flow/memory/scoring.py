"""
scoring.py — Importance scoring for memory nodes.

Rule-based importance scoring used when storing episodes.
"""

import re


class ScoringMixin:
    """Mixin providing importance scoring methods for EpisodicMemoryGraph."""

    def _score_importance(self, round_num: int, outcomes: list[dict]) -> float:
        """
        Rule-based importance scoring.

        Scoring rules (highest applicable score wins):
            1.0  — Event schedule round (scripted events like supply drops, crises)
            0.9  — Agent received resources via share from another agent
            0.8  — Resources changed hands (claim or share actions in outcomes)
            0.6  — Multiple agents spoke this round (social interaction)
            0.3  — Movement or idle only (low-signal round)
        """
        # Rule 1: Event rounds always max importance
        if round_num in self.event_rounds:
            return 1.0

        action_types = [o.get("action", "") for o in outcomes]

        # Rule 2: This agent received resources from someone
        # Use word-boundary regex to avoid substring false positives
        name_pattern = re.compile(r"\b" + re.escape(self.agent_name) + r"\b", re.IGNORECASE)
        for outcome in outcomes:
            if (
                outcome.get("action") == "share"
                and outcome.get("agent") != self.agent_name
                and name_pattern.search(outcome.get("detail", ""))
            ):
                return 0.9

        # Rule 3: Resources changed hands (claim or share)
        has_resource_transfer = any(
            a in ("claim", "share") for a in action_types
        )
        if has_resource_transfer:
            return 0.8

        # Rule 4: Multiple agents spoke (social coordination signal)
        speak_count = sum(1 for a in action_types if a == "speak")
        if speak_count >= 2:
            return 0.6

        # Rule 5: Low-signal round
        return 0.3

    def _source_episode_importance(self, node_id: str) -> float:
        """Get importance of the episode a fact/commitment was extracted from."""
        for succ in self.graph.successors(node_id):
            edge = self.graph.edges[node_id, succ]
            if edge.get("rel") == "EXTRACTED_FROM":
                imp = self.graph.nodes[succ].get("importance", 0.3)
                return max(0.0, min(1.0, imp))
        return 0.3
