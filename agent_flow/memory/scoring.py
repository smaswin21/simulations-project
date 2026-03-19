"""
scoring.py — Rule-based episode importance scoring.
"""

import re


class ScoringMixin:
    def _score_importance(self, round_num: int, outcomes: list[dict]) -> float:
        if round_num in self.event_rounds:
            return 1.0

        action_types = [outcome.get("action", "") for outcome in outcomes]
        if "report" in action_types:
            return 0.95
        if "sanction" in action_types:
            return 0.9
        if "graze" in action_types:
            return 0.8
        if action_types.count("message") >= 2:
            return 0.6
        return 0.3

    def _source_episode_importance(self, node_id: str) -> float:
        for successor in self.graph.successors(node_id):
            edge = self.graph.edges[node_id, successor]
            if edge.get("rel") == "EXTRACTED_FROM":
                importance = self.graph.nodes[successor].get("importance", 0.3)
                return max(0.0, min(1.0, importance))
        return 0.3

    def _subject_matches_agent(self, detail: str) -> bool:
        pattern = re.compile(r"\b" + re.escape(self.agent_name) + r"\b", re.IGNORECASE)
        return bool(pattern.search(detail))
