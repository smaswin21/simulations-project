"""
collector.py — Metrics for heterogeneous MASTOC runs.
"""

from __future__ import annotations

import re

_ACCOUNTABILITY_VERBS = {
    "promised",
    "said",
    "took",
    "refused",
    "shared",
    "lied",
    "stole",
    "gave",
    "grazed",
    "hoarded",
    "broke",
    "failed",
    "sanctioned",
}


def calculate_gini(values: list[int | float]) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumulative = 0.0
    for index, value in enumerate(sorted_vals, start=1):
        cumulative += (2 * index - n - 1) * value
    return cumulative / (n * total)


class MetricsCollector:
    def __init__(self, agent_names: list[str]):
        self.agent_names = agent_names
        self.gini_over_time: list[float] = []
        self.accountability_over_time: list[int] = []
        self.total_graze_over_time: list[int] = []
        self.cooperation_rate_over_time: list[float] = []
        self.resource_stock_over_time: list[int] = []
        self.speech_diversity_over_time: list[float] = []
        self.numeric_grounding_over_time: list[float] = []

        self.accountability_events = 0
        self.total_speech_acts = 0

    def update_round(self, round_num: int, outcomes: list[dict], inventories: dict[str, int]) -> None:
        del round_num
        self.gini_over_time.append(calculate_gini(list(inventories.values())))

        round_accountability = 0
        round_speeches = []
        for outcome in outcomes:
            if outcome.get("action") not in {"message", "report"}:
                continue
            detail = outcome.get("detail", "")
            lowered = detail.lower()
            round_speeches.append(detail)

            other_agent_referenced = any(
                name.lower() in lowered
                for name in self.agent_names
                if name.lower() != outcome.get("agent", "").lower()
            )
            has_accountability_verb = any(verb in lowered for verb in _ACCOUNTABILITY_VERBS)
            if other_agent_referenced and has_accountability_verb:
                round_accountability += 1

        self.accountability_events += round_accountability
        self.total_speech_acts += len(round_speeches)
        self.accountability_over_time.append(round_accountability)

        if round_speeches:
            self.speech_diversity_over_time.append(len(set(round_speeches)) / len(round_speeches))
            with_number = sum(1 for item in round_speeches if re.search(r"\d", item))
            self.numeric_grounding_over_time.append(with_number / len(round_speeches))
        else:
            self.speech_diversity_over_time.append(1.0)
            self.numeric_grounding_over_time.append(0.0)

    def update_cooperation_rate(self, harvest_actions: list[dict], sustainable_quota: int) -> None:
        total_graze = sum(action.get("amount", 0) for action in harvest_actions)
        self.total_graze_over_time.append(total_graze)
        if not harvest_actions:
            self.cooperation_rate_over_time.append(1.0)
            return
        cooperators = sum(1 for action in harvest_actions if action["amount"] <= sustainable_quota)
        self.cooperation_rate_over_time.append(cooperators / len(harvest_actions))

    def update_resource_stock(self, stock: int) -> None:
        self.resource_stock_over_time.append(stock)

    def finalize(self) -> dict:
        accountability_rate = (
            self.accountability_events / self.total_speech_acts
            if self.total_speech_acts > 0
            else 0.0
        )

        return {
            "gini_over_time": self.gini_over_time,
            "accountability_over_time": self.accountability_over_time,
            "total_graze_over_time": self.total_graze_over_time,
            "cooperation_rate_over_time": self.cooperation_rate_over_time,
            "resource_stock_over_time": self.resource_stock_over_time,
            "speech_diversity_over_time": self.speech_diversity_over_time,
            "numeric_grounding_over_time": self.numeric_grounding_over_time,
            "gini_final": self.gini_over_time[-1] if self.gini_over_time else 0.0,
            "accountability_events": self.accountability_events,
            "total_speech_acts": self.total_speech_acts,
            "accountability_rate": accountability_rate,
            "total_graze_final": self.total_graze_over_time[-1] if self.total_graze_over_time else 0,
            "cooperation_rate_final": self.cooperation_rate_over_time[-1] if self.cooperation_rate_over_time else 0.0,
            "resource_stock_final": self.resource_stock_over_time[-1] if self.resource_stock_over_time else 0,
            "speech_diversity_final": self.speech_diversity_over_time[-1] if self.speech_diversity_over_time else 1.0,
            "numeric_grounding_final": self.numeric_grounding_over_time[-1] if self.numeric_grounding_over_time else 0.0,
        }
