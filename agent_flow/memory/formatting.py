"""
formatting.py — Compact memory prompt formatting for belief retrieval.
"""

from __future__ import annotations


class FormattingMixin:
    def format_memory_block(
        self,
        current_round: int,
        current_reflection: str = "",
        max_facts: int = 8,
        max_episodes: int = 3,
        nearby_agents: set[str] | None = None,
    ) -> tuple[str, list[str]]:
        if self.episode_counter == 0:
            return "", []

        if current_reflection:
            ranked = self.retrieve_relevant(
                current_reflection=current_reflection,
                current_round=current_round,
                nearby_agents=nearby_agents,
            )
            if ranked:
                fact_data_list = [data for _, data, _ in ranked if data.get("type") == "fact"]
                episode_data_list = [data for _, data, _ in ranked if data.get("type") == "episode"]
                return self._format_beliefs(fact_data_list, episode_data_list)

        retrieved = self.retrieve_memories(
            current_round=current_round,
            max_facts=max_facts,
            max_episodes=max_episodes,
            nearby_agents=nearby_agents,
        )
        fact_data_list = [data for _, data in retrieved["facts"]]
        episode_data_list = [data for _, data in retrieved["episodes"]]
        return self._format_beliefs(fact_data_list, episode_data_list)

    def _format_beliefs(
        self,
        fact_data_list: list[dict],
        episode_data_list: list[dict],
    ) -> tuple[str, list[str]]:
        lines = ["RELEVANT BELIEFS:"]
        labels = []

        for data in fact_data_list:
            content = data.get("content", "")
            category = data.get("category", "belief")
            lines.append(f"  [{category}] {content}")
            labels.append(f"[Belief] {content[:60]}")

        if len(lines) > 1:
            return "\n".join(lines), labels

        if episode_data_list:
            episode = episode_data_list[0]
            summary = self._episode_summary(episode)
            return (
                f"RELEVANT BELIEFS:\n  [Round {episode.get('round', '?')}] {summary}",
                [f"[Episode R{episode.get('round', '?')}] {summary[:60]}"],
            )
        return "", []

    @staticmethod
    def _episode_summary(episode_data: dict) -> str:
        round_num = episode_data.get("round", "?")
        outcomes = episode_data.get("outcomes", [])
        if outcomes:
            return "; ".join(
                f"{item.get('agent', '?')} {item.get('action', '?')}: {item.get('detail', '')[:45]}"
                for item in outcomes[:3]
            )
        content = episode_data.get("content", "")
        if content:
            return content[:120]
        return f"Round {round_num} context"
