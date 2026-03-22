"""
retrieval.py — Belief-oriented memory retrieval strategies.
"""

from __future__ import annotations

from agent_flow.embedding import cosine_similarity, embed_text, recency_score
from config.config import BELIEF_ALIGNMENT_BOOST, RETRIEVAL_TOP_K

EPISODE_FALLBACK_LIMIT = 1
NEARBY_SUBJECT_BOOST = 1.25


class RetrievalMixin:
    def retrieve_relevant(
        self,
        current_reflection: str,
        current_round: int,
        k: int = RETRIEVAL_TOP_K,
        nearby_agents: set[str] | None = None,
    ) -> list[tuple[str, dict, float]]:
        if nearby_agents is None:
            nearby_agents = set()

        query_vec = embed_text(current_reflection)
        if query_vec is None:
            return self._retrieve_heuristic_as_ranked(current_round, k)

        ranked_facts = self._score_nodes(
            query_vec=query_vec,
            current_round=current_round,
            node_type="fact",
            nearby_agents=nearby_agents,
        )
        ranked_episodes = self._score_nodes(
            query_vec=query_vec,
            current_round=current_round,
            node_type="episode",
            nearby_agents=nearby_agents,
        )

        result = ranked_facts[:k]
        remaining = k - len(result)
        if remaining > 0:
            result.extend(ranked_episodes[: min(remaining, EPISODE_FALLBACK_LIMIT)])
        return result

    def _retrieve_heuristic_as_ranked(
        self,
        current_round: int,
        k: int,
    ) -> list[tuple[str, dict, float]]:
        retrieved = self.retrieve_memories(current_round)
        flat: list[tuple[str, dict, float]] = []
        for fact_id, fact_data in retrieved["facts"]:
            flat.append((fact_id, fact_data, 0.5))
        for episode_id, episode_data in retrieved["episodes"][:EPISODE_FALLBACK_LIMIT]:
            flat.append((episode_id, episode_data, 0.5))
        return flat[:k]

    def _score_nodes(
        self,
        query_vec,
        current_round: int,
        node_type: str,
        nearby_agents: set[str] | None = None,
    ) -> list[tuple[str, dict, float]]:
        if nearby_agents is None:
            nearby_agents = set()

        ranked = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") != node_type:
                continue

            node_vec = data.get("embedding")
            if node_vec is None:
                continue

            relevance = cosine_similarity(query_vec, node_vec)
            recency = recency_score(current_round, data.get("round", 0))
            importance = data.get("importance")
            if importance is None:
                importance = self._source_episode_importance(node_id)
            score = relevance * recency * importance

            if relevance >= 0.55:
                score *= BELIEF_ALIGNMENT_BOOST
            score *= self._nearby_subject_boost(data, nearby_agents)

            ranked.append((node_id, {**dict(data), "_reflection_similarity": relevance}, score))

        ranked.sort(key=lambda item: item[2], reverse=True)
        return ranked

    def retrieve_memories(
        self,
        current_round: int,
        max_facts: int = 8,
        max_episodes: int = 3,
        nearby_agents: set[str] | None = None,
    ) -> dict:
        if nearby_agents is None:
            nearby_agents = set()

        facts = self.get_all_facts()
        scored_facts = []
        for fact_id, fact_data in facts:
            recency = recency_score(current_round, fact_data.get("round", 0))
            confidence = fact_data.get("confidence", 0.5)
            importance = self._source_episode_importance(fact_id)
            score = confidence * 0.4 + recency * 0.3 + importance * 0.3
            score *= self._nearby_subject_boost(fact_data, nearby_agents)
            scored_facts.append((score, fact_id, fact_data))
        scored_facts.sort(key=lambda item: item[0], reverse=True)
        top_facts = [(fact_id, fact_data) for _, fact_id, fact_data in scored_facts[:max_facts]]

        episodes = self.get_all_episodes()
        scored_episodes = []
        for episode_id, episode_data in episodes:
            recency = recency_score(current_round, episode_data.get("round", 0))
            importance = episode_data.get("importance", 0.3)
            scored_episodes.append((importance * 0.6 + recency * 0.4, episode_id, episode_data))
        scored_episodes.sort(key=lambda item: item[0], reverse=True)
        top_episodes = [
            (episode_id, episode_data)
            for _, episode_id, episode_data in scored_episodes[: min(max_episodes, EPISODE_FALLBACK_LIMIT)]
        ]

        return {"facts": top_facts, "episodes": top_episodes}

    @staticmethod
    def _nearby_subject_boost(data: dict, nearby_agents: set[str]) -> float:
        subject = data.get("subject")
        if data.get("type") != "fact" or subject not in nearby_agents:
            return 1.0
        return NEARBY_SUBJECT_BOOST
