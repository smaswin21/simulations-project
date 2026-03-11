"""
collector.py — Phase 5: Gini + Accountability metrics for ablation study.

Two metrics tracked per round:
   1. Gini coefficient of resource distribution across agents
  2. Accountability events: speech acts referencing another agent's
     past actions/promises (e.g., "you promised", "Alice took", etc.)

Usage:
    collector = MetricsCollector(agent_names=["Alice", "Bob", ...])
    # After each round:
    collector.update_round(round_num, outcomes, inventories)
    # After simulation:
    summary = collector.finalize()
"""

import re


# Verbs that indicate an agent is referencing another's past behaviour
_ACCOUNTABILITY_VERBS = {
    "promised", "said", "took", "refused", "shared",
    "lied", "stole", "gave", "claimed", "hoarded",
    "broke", "kept", "agreed", "failed",
}


def calculate_gini(values: list[int | float]) -> float:
    """
    Calculate the Gini coefficient from a list of non-negative values.

    Returns 0.0 if all values are zero or the list is empty.
    Uses the standard formula: G = sum_i sum_j |x_i - x_j| / (2 * n * sum(x))
    Equivalent formulation using sorted values for O(n log n).
    """
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumulative = 0.0
    for i, x in enumerate(sorted_vals):
        cumulative += (2 * (i + 1) - n - 1) * x
    return cumulative / (n * total)


class MetricsCollector:
    """Collects per-round Gini and accountability metrics."""

    def __init__(self, agent_names: list[str]):
        """
        Args:
            agent_names: list of all agent names in the simulation.
        """
        self.agent_names = agent_names
        self._agent_names_lower = {name.lower() for name in agent_names}

        # Per-round tracking
        self.gini_over_time: list[float] = []
        self.accountability_over_time: list[int] = []

        # Cumulative counters
        self.accountability_events: int = 0
        self.total_speech_acts: int = 0

        # Cooperation rate tracking
        self.cooperation_rate_over_time: list[float] = []
        self.resource_stock_over_time: list[int] = []

    def update_round(
        self,
        round_num: int,
        outcomes: list[dict],
        inventories: dict[str, int],
    ) -> None:
        """
        Record metrics for one completed round.

        Args:
            round_num:   current round number (for logging)
            outcomes:    list of resolved outcome dicts from environment
            inventories: dict mapping agent_name -> current resource holdings
        """
        # ── Gini ─────────────────────────────────────────────
        holdings = list(inventories.values())
        gini = calculate_gini(holdings)
        self.gini_over_time.append(gini)

        # ── Accountability ───────────────────────────────────
        round_accountability = 0
        round_speech = 0

        for outcome in outcomes:
            if outcome.get("action") != "speak":
                continue

            speaker = outcome.get("agent", "")
            detail = outcome.get("detail", "")
            detail_lower = detail.lower()
            round_speech += 1

            # Check if the speech references another agent AND contains
            # an accountability verb
            has_other_agent = any(
                name.lower() in detail_lower
                for name in self.agent_names
                if name.lower() != speaker.lower()
            )
            has_accountability_verb = any(
                verb in detail_lower for verb in _ACCOUNTABILITY_VERBS
            )

            if has_other_agent and has_accountability_verb:
                round_accountability += 1

        self.accountability_events += round_accountability
        self.total_speech_acts += round_speech
        self.accountability_over_time.append(round_accountability)

    def update_cooperation_rate(
        self,
        round_num: int,
        harvest_actions: list[dict],
        sustainable_quota: int,
    ) -> None:
        """
        Record cooperation rate for one round.

        Cooperation rate = fraction of harvesting agents who stayed at or below
        the sustainable_quota.
        """
        if not harvest_actions:
            self.cooperation_rate_over_time.append(1.0)
            return
        cooperators = sum(1 for a in harvest_actions if a["amount"] <= sustainable_quota)
        rate = cooperators / len(harvest_actions)
        self.cooperation_rate_over_time.append(rate)

    def update_resource_stock(self, stock: int) -> None:
        """Record the commons pool stock level after this round."""
        self.resource_stock_over_time.append(stock)

    def finalize(self) -> dict:
        """
        Compute final summary metrics.

        Returns:
            Dict with all metrics for JSONL logging:
            {
                "gini_over_time": [...],
                "accountability_over_time": [...],
                "gini_final": float,
                "accountability_events": int,
                "total_speech_acts": int,
                "accountability_rate": float,
            }
        """
        gini_final = self.gini_over_time[-1] if self.gini_over_time else 0.0
        accountability_rate = (
            self.accountability_events / self.total_speech_acts
            if self.total_speech_acts > 0
            else 0.0
        )

        return {
            "gini_over_time": self.gini_over_time,
            "accountability_over_time": self.accountability_over_time,
            "cooperation_rate_over_time": self.cooperation_rate_over_time,
            "resource_stock_over_time": self.resource_stock_over_time,
            "gini_final": gini_final,
            "accountability_events": self.accountability_events,
            "total_speech_acts": self.total_speech_acts,
            "accountability_rate": accountability_rate,
            "cooperation_rate_final": (
                self.cooperation_rate_over_time[-1]
                if self.cooperation_rate_over_time else 0.0
            ),
            "resource_stock_final": (
                self.resource_stock_over_time[-1]
                if self.resource_stock_over_time else 0
            ),
        }
