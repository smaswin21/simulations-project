"""
retrieval.py — Memory retrieval strategies.

Phase 3: Embedding-based retrieval with cosine similarity + recency + importance.
Phase 4: One-hop graph expansion and contradiction-aware score multipliers.
Phase 5+: Status-aware commitment retrieval with proximity scoring.
Heuristic fallback when embeddings are unavailable.
"""

from __future__ import annotations

from agent_flow.embedding import embed_text, cosine_similarity, recency_score
from config.config import (
    RETRIEVAL_TOP_K,
    CONTRADICTION_BONUS,
    BROKEN_COMMIT_BONUS,
    EXPANSION_BONUS,
)

# ── Status weights for commitment scoring ────────────────────
# Broken promises are MOST important to surface; fulfilled are
# context but low urgency.
STATUS_WEIGHT: dict[str, float] = {
    "broken": 2.0,
    "pending": 1.5,
    "kept": 0.5,
    "fulfilled": 0.5,  # alias used in some code paths
}

# Boost for commitments involving agents physically nearby right now
PROXIMITY_BOOST = 1.8


class RetrievalMixin:
    """Mixin providing memory retrieval methods for EpisodicMemoryGraph."""

    # ── Phase 3 + Phase 4: Embedding-based memory retrieval ───

    def retrieve_relevant(
        self,
        current_perception: str,
        current_round: int,
        k: int = RETRIEVAL_TOP_K,
        nearby_agents: set[str] | None = None,
    ) -> list[tuple[str, dict, float]]:
        """
        Retrieve the k most relevant memory nodes using embedding similarity,
        recency decay, importance scoring, one-hop graph expansion, and
        contradiction-aware score multipliers.

        Pipeline:
          1. Score all nodes: relevance * recency * importance
          2. Apply proximity boost to commitments involving nearby agents
          3. Take initial top-k candidates
          4. One-hop expansion: for each candidate, follow CONTRADICTS and
             EXTRACTED_FROM edges to pull in related nodes
          5. Apply score multipliers:
             - CONTRADICTS edge to another retrieved node -> x CONTRADICTION_BONUS
             - Commitment with status "broken" -> x BROKEN_COMMIT_BONUS
             - Nodes pulled in via expansion -> x EXPANSION_BONUS
          6. Re-rank and truncate to k

        Falls back to heuristic if embeddings are unavailable.

        Args:
            current_perception: text of what the agent currently observes
            current_round:      the round about to be played
            k:                  max nodes to return
            nearby_agents:      set of agent names at the same location

        Returns:
            List of (node_id, node_data, score) triples, best-first.
            node_data includes "_expanded_via" key if pulled in via expansion.
        """
        if nearby_agents is None:
            nearby_agents = set()
        query_vec = embed_text(current_perception)

        # If embedding model is unavailable, fall back to heuristic
        if query_vec is None:
            return self._retrieve_heuristic_as_ranked(current_round, k)

        # ── Step 1: Score every node ────────────────────────
        all_scores: dict[str, float] = {}

        for nid, data in self.graph.nodes(data=True):
            node_type = data.get("type")
            if node_type not in ("episode", "fact", "commitment"):
                continue

            node_vec = data.get("embedding")
            if node_vec is None:
                continue

            relevance = cosine_similarity(query_vec, node_vec)
            rnd = data.get("round")
            node_round = rnd if rnd is not None else data.get("round_made", 0)
            rec = recency_score(current_round, node_round)

            if node_type == "episode":
                imp = data.get("importance", 0.3)
            else:
                # Broken commitments get their overridden importance
                imp = data.get("importance") if data.get("importance") is not None else self._source_episode_importance(nid)

            all_scores[nid] = relevance * rec * imp

        # ── Step 1b: Proximity boost for commitments involving nearby agents
        for nid in list(all_scores):
            data = self.graph.nodes.get(nid, {})
            if (
                data.get("type") == "commitment"
                and data.get("agent") in nearby_agents
            ):
                all_scores[nid] *= PROXIMITY_BOOST

        # ── Step 2: Initial top-k candidates ────────────────
        sorted_ids = sorted(all_scores, key=lambda x: all_scores[x], reverse=True)
        initial_ids = set(sorted_ids[:k])

        # ── Step 3: One-hop expansion ───────────────────────
        expanded_ids: set[str] = set()  # nodes pulled in via expansion
        expansion_reason: dict[str, str] = {}  # nid -> "contradiction" | "provenance"

        for nid in list(initial_ids):
            # Outgoing edges: fact→episode (EXTRACTED_FROM), fact→fact (CONTRADICTS)
            for _, succ, edata in self.graph.out_edges(nid, data=True):
                rel = edata.get("rel")
                if rel == "CONTRADICTS" and succ not in initial_ids:
                    expanded_ids.add(succ)
                    expansion_reason[succ] = "contradiction"
                elif rel == "EXTRACTED_FROM" and succ not in initial_ids:
                    expanded_ids.add(succ)
                    expansion_reason.setdefault(succ, "provenance")
            # Incoming edges: pull in facts extracted from a retrieved episode,
            # or the other side of a CONTRADICTS edge if bidirectional was missed
            for pred, _, edata in self.graph.in_edges(nid, data=True):
                rel = edata.get("rel")
                if rel == "CONTRADICTS" and pred not in initial_ids:
                    expanded_ids.add(pred)
                    expansion_reason.setdefault(pred, "contradiction")
                elif rel == "EXTRACTED_FROM" and pred not in initial_ids:
                    expanded_ids.add(pred)
                    expansion_reason.setdefault(pred, "provenance")

        # Merge: all candidate IDs
        candidate_ids = initial_ids | expanded_ids

        # Assign base scores to expanded nodes that weren't scored
        for nid in expanded_ids:
            if nid not in all_scores:
                # Give expansion nodes a modest base score
                data = self.graph.nodes.get(nid, {})
                rnd = data.get("round")
                node_round = rnd if rnd is not None else data.get("round_made", 0)
                rec = recency_score(current_round, node_round)
                imp = data.get("importance", 0.3)
                all_scores[nid] = 0.5 * rec * imp  # 0.5 as default relevance

        # ── Step 4: Apply score multipliers ─────────────────
        # Pre-compute which candidates have CONTRADICTS edges to other candidates
        for nid in candidate_ids:
            for _, succ, edata in self.graph.out_edges(nid, data=True):
                if edata.get("rel") == "CONTRADICTS" and succ in candidate_ids:
                    all_scores[nid] *= CONTRADICTION_BONUS
                    break  # apply once per node

        # Broken commitment bonus
        for nid in candidate_ids:
            data = self.graph.nodes.get(nid, {})
            if data.get("type") == "commitment" and data.get("status") == "broken":
                all_scores[nid] *= BROKEN_COMMIT_BONUS

        # Expansion bonus for nodes pulled in via graph walk
        for nid in expanded_ids:
            all_scores[nid] *= EXPANSION_BONUS

        # ── Step 5: Re-rank and truncate to k ───────────────
        final_ranked = sorted(candidate_ids, key=lambda x: all_scores.get(x, 0), reverse=True)[:k]

        result: list[tuple[str, dict, float]] = []
        for nid in final_ranked:
            data = dict(self.graph.nodes[nid])
            # Tag nodes that were pulled in via graph expansion
            if nid in expanded_ids:
                data["_expanded_via"] = expansion_reason.get(nid, "expansion")
            result.append((nid, data, all_scores.get(nid, 0)))

        return result

    # ── Status-aware commitment retrieval ───────────────────

    def retrieve_commitments(
        self,
        current_round: int,
        k: int = 5,
        nearby_agents: set[str] | None = None,
    ) -> list[dict]:
        """
        Retrieve commitments with status-aware scoring.

        Scoring formula per commitment:
            score = recency * status_weight * agent_proximity_boost

        Broken promises score highest, then pending, then kept/fulfilled.
        Commitments involving agents physically nearby get a proximity boost.

        Args:
            current_round:  the round about to be played
            k:              max commitments to return
            nearby_agents:  set of agent names at the same location

        Returns:
            List of commitment data dicts, best-first.  Each dict includes
            the original node attributes plus a ``_score`` key.
        """
        if nearby_agents is None:
            nearby_agents = set()

        commitments = [
            (node_id, data)
            for node_id, data in self.graph.nodes(data=True)
            if data.get("type") == "commitment"
        ]

        if not commitments:
            return []

        scored: list[tuple[float, str, dict]] = []
        for node_id, data in commitments:
            # Recency: exponential decay (consistent with retrieve_relevant)
            recency = recency_score(current_round, data.get("round_made", 0))

            # Status multiplier — broken > pending > kept
            status = data.get("status", "pending")
            weight = STATUS_WEIGHT.get(status, 1.0)

            # Agent proximity — commitments involving nearby agents get boosted
            agent_proximity = 1.0
            if data.get("agent") in nearby_agents:
                agent_proximity = PROXIMITY_BOOST

            score = recency * weight * agent_proximity

            # Build result dict with score attached
            result = dict(data)
            result["_node_id"] = node_id
            result["_score"] = score
            scored.append((score, node_id, result))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [result for _, _, result in scored[:k]]

    # ── Heuristic fallback (flattened to ranked format) ──────

    def _retrieve_heuristic_as_ranked(
        self, current_round: int, k: int,
    ) -> list[tuple[str, dict, float]]:
        """
        Fallback: use the old heuristic retrieve_memories() and flatten
        into the same (node_id, node_data, score) format.
        """
        retrieved = self.retrieve_memories(current_round)
        flat: list[tuple[str, dict, float]] = []
        # Assign a synthetic score so the caller can still rank
        for fid, fdata in retrieved["facts"]:
            flat.append((fid, fdata, 0.5))
        for eid, edata in retrieved["episodes"]:
            flat.append((eid, edata, 0.5))
        for cid, cdata in retrieved["commitments"]:
            flat.append((cid, cdata, 0.5))
        return flat[:k]

    # ── Heuristic retrieval (no embeddings) ──────────────────

    def retrieve_memories(
        self,
        current_round: int,
        max_facts: int = 8,
        max_episodes: int = 3,
        max_commitments: int = 4,
        nearby_agents: set[str] | None = None,
    ) -> dict:
        """
        Retrieve the most relevant memories for prompt injection.

        Ranking strategy (no embeddings — uses importance + recency):
          - Facts: scored by  confidence * 0.4 + recency * 0.3 + importance_of_source_ep * 0.3
          - Episodes: scored by  importance * 0.6 + recency * 0.4
          - Commitments: scored by recency * status_weight * proximity (via retrieve_commitments)

        Args:
            current_round:    the round about to be played
            max_facts:        max fact nodes to return
            max_episodes:     max episode summaries to return
            max_commitments:  max commitment nodes to return
            nearby_agents:    set of agent names at the same location

        Returns:
            dict with keys "facts", "episodes", "commitments", each a list of
            (node_id, attributes) tuples, ranked best-first.
        """
        # ── Helper: get importance of the episode a fact was extracted from ──
        def _source_ep_importance(node_id: str) -> float:
            for succ in self.graph.successors(node_id):
                edge = self.graph.edges[node_id, succ]
                if edge.get("rel") == "EXTRACTED_FROM":
                    return self.graph.nodes[succ].get("importance", 0.3)
            return 0.3

        # ── Rank facts ───────────────────────────────────────
        facts = self.get_all_facts()
        scored_facts = []
        for fid, fdata in facts:
            r = fdata.get("round", 0)
            conf = fdata.get("confidence", 0.5)
            rec = recency_score(current_round, r)
            imp = _source_ep_importance(fid)
            score = conf * 0.4 + rec * 0.3 + imp * 0.3
            scored_facts.append((score, fid, fdata))
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        top_facts = [(fid, fdata) for _, fid, fdata in scored_facts[:max_facts]]

        # ── Rank episodes (summarized, not full perception) ──
        episodes = self.get_all_episodes()
        scored_eps = []
        for eid, edata in episodes:
            r = edata.get("round", 0)
            imp = edata.get("importance", 0.3)
            rec = recency_score(current_round, r)
            score = imp * 0.6 + rec * 0.4
            scored_eps.append((score, eid, edata))
        scored_eps.sort(key=lambda x: x[0], reverse=True)
        top_episodes = [(eid, edata) for _, eid, edata in scored_eps[:max_episodes]]

        # ── Commitments: scored retrieval (status-aware + proximity) ──
        scored_commits = self.retrieve_commitments(
            current_round, k=max_commitments, nearby_agents=nearby_agents,
        )
        # Convert back to (node_id, data) tuple format for compatibility
        top_commits = []
        for cdata in scored_commits:
            nid = cdata.pop("_node_id", "commit_?")
            cdata.pop("_score", None)
            top_commits.append((nid, cdata))

        return {
            "facts": top_facts,
            "episodes": top_episodes,
            "commitments": top_commits,
        }
