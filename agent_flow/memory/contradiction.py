"""
contradiction.py — Phase 4: Contradiction detection and commitment updates.

Detects when new facts contradict existing ones via keyword rules,
numeric-share shortcuts, and embedding dissimilarity. Also handles
updating commitment statuses based on contradiction edges.
"""

import re

import numpy as np

from agent_flow.embedding import cosine_similarity
from config.config import (
    COSINE_CONTRADICT_THRESHOLD,
    COMMITMENT_KEPT_ROUNDS,
    USE_LLM_CONTRADICTION,
)

# ── Phase 4: Contradiction detection keyword sets ────────
_COOPERATIVE_KEYWORDS = {"share", "fair", "equal", "distribute", "split", "cooperate"}
_SELFISH_KEYWORDS = {"claim", "take", "hoard", "kept all", "monopolize", "refuse"}


class ContradictionMixin:
    """Mixin providing contradiction detection and commitment updates."""

    def _detect_contradictions(
        self,
        new_fact_id: str,
        new_content: str,
        subject: str,
        new_vec: "np.ndarray | None",
    ) -> list[str]:
        """
        Compare a newly added fact against all prior facts with the same
        subject.  If a contradiction is detected, add bidirectional
        CONTRADICTS edges.

        Detection rules (evaluated in order, first match wins):
          1. Keyword rule: prior content has cooperative keywords AND new
             content has selfish keywords (or vice-versa).
          2. Numeric-share shortcut: prior mentions "fair"/"equal" AND new
             contains "claimed <number>".
          3. Embedding dissimilarity: cosine_similarity < COSINE_CONTRADICT_THRESHOLD.

        Returns:
            List of prior fact IDs that contradict the new fact.
        """
        new_lower = new_content.lower()
        contradicted: list[str] = []

        for nid, data in self.graph.nodes(data=True):
            if data.get("type") != "fact":
                continue
            if nid == new_fact_id:
                continue
            if data.get("subject", "").lower() != subject.lower():
                continue

            existing_lower = data.get("content", "").lower()
            is_contradiction = False

            # Rule 1: Keyword opposition
            existing_has_coop = any(kw in existing_lower for kw in _COOPERATIVE_KEYWORDS)
            existing_has_self = any(kw in existing_lower for kw in _SELFISH_KEYWORDS)
            new_has_coop = any(kw in new_lower for kw in _COOPERATIVE_KEYWORDS)
            new_has_self = any(kw in new_lower for kw in _SELFISH_KEYWORDS)

            if (existing_has_coop and new_has_self) or (existing_has_self and new_has_coop):
                is_contradiction = True

            # Rule 2: Numeric-share shortcut
            # Flag when one fact mentions fair/equal and the other shows a
            # claim of >= 3 units (heuristic for above-average in a 20-agent sim
            # where per-round supply is typically 10-20 units).
            if not is_contradiction:
                fair_words = {"fair", "equal"}
                claim_match_new = re.search(r"claimed\s+(\d+)", new_lower)
                claim_match_existing = re.search(r"claimed\s+(\d+)", existing_lower)

                if any(w in existing_lower for w in fair_words) and claim_match_new:
                    if int(claim_match_new.group(1)) >= 3:
                        is_contradiction = True
                elif any(w in new_lower for w in fair_words) and claim_match_existing:
                    if int(claim_match_existing.group(1)) >= 3:
                        is_contradiction = True

            # Rule 3: Embedding dissimilarity
            if not is_contradiction:
                existing_vec = data.get("embedding")
                if new_vec is not None and existing_vec is not None:
                    sim = cosine_similarity(new_vec, existing_vec)
                    if sim < COSINE_CONTRADICT_THRESHOLD:
                        is_contradiction = True

            # Rule 4: LLM-based contradiction check (Step 17, most expensive)
            # Only used when enabled via config and rules 1-3 didn't trigger.
            if not is_contradiction and USE_LLM_CONTRADICTION:
                is_contradiction = self._llm_contradiction_check(
                    new_content, data.get("content", ""), subject
                )

            if is_contradiction:
                # Bidirectional CONTRADICTS edges
                self.graph.add_edge(new_fact_id, nid, rel="CONTRADICTS")
                self.graph.add_edge(nid, new_fact_id, rel="CONTRADICTS")
                contradicted.append(nid)

        return contradicted

    # ── Phase 4: Commitment status updater (Step 19) ─────────

    def update_commitments(self, round_num: int) -> dict[str, str]:
        """
        Scan all pending commitments and update their status based on
        contradiction edges touching the committing agent's facts.

        Rules:
          - "broken": a fact about the same agent has a CONTRADICTS edge
            to another fact, AND the contradicting pair is relevant to the
            commitment's content (keyword overlap or embedding similarity).
          - "kept": (round_num - round_made) >= COMMITMENT_KEPT_ROUNDS and
            no relevant contradictions -> mark as kept.

        Called once per round from the orchestrator, after fact extraction.

        Args:
            round_num: the current simulation round

        Returns:
            Dict of {commitment_id: new_status} for each status that changed.
        """
        changes: dict[str, str] = {}

        # Pre-compute: for each agent, collect (fact_content, contradicting_fact_content)
        # pairs where a CONTRADICTS edge exists.
        agent_contradiction_pairs: dict[str, list[tuple[str, str]]] = {}
        for nid, data in self.graph.nodes(data=True):
            if data.get("type") != "fact":
                continue
            subj = data.get("subject", "").lower()
            if not subj:
                continue
            fact_content = data.get("content", "")
            for _, succ, edata in self.graph.out_edges(nid, data=True):
                if edata.get("rel") == "CONTRADICTS":
                    succ_data = self.graph.nodes.get(succ, {})
                    succ_content = succ_data.get("content", "")
                    agent_contradiction_pairs.setdefault(subj, []).append(
                        (fact_content, succ_content)
                    )

        for nid, data in self.graph.nodes(data=True):
            if data.get("type") != "commitment":
                continue
            if data.get("status") != "pending":
                continue

            agent = data.get("agent", "").lower()
            round_made = data.get("round_made", 0)
            commit_content = data.get("content", "").lower()

            # Check if any contradiction pair for this agent is relevant
            # to this specific commitment.
            is_broken = False
            pairs = agent_contradiction_pairs.get(agent, [])
            for fact_a, fact_b in pairs:
                if self._contradiction_relevant_to_commitment(
                    commit_content, fact_a.lower(), fact_b.lower()
                ):
                    is_broken = True
                    break

            if is_broken:
                # Mark as broken, boost importance
                self.graph.nodes[nid]["status"] = "broken"
                self.graph.nodes[nid]["importance"] = 1.0
                changes[nid] = "broken"
            elif (round_num - round_made) >= COMMITMENT_KEPT_ROUNDS:
                # Survived long enough without relevant contradiction -> kept
                self.graph.nodes[nid]["status"] = "kept"
                changes[nid] = "kept"

        return changes

    @staticmethod
    def _contradiction_relevant_to_commitment(
        commit_content: str,
        fact_a: str,
        fact_b: str,
    ) -> bool:
        """
        Determine if a pair of contradicting facts is relevant to a commitment.

        Uses keyword overlap: the commitment and at least one of the two facts
        must share meaningful keywords (resource actions, cooperation terms, or
        agent names embedded in the text).

        Args:
            commit_content: lowercased commitment text
            fact_a:         lowercased content of one fact in the contradiction
            fact_b:         lowercased content of the other fact

        Returns:
            True if the contradiction is relevant to this commitment.
        """
        # Meaningful keywords that link a commitment to resource actions
        _RELEVANCE_KEYWORDS = {
            "share", "fair", "equal", "distribute", "split", "cooperate",
            "claim", "take", "hoard", "give", "promise", "help",
            "graze", "pasture", "unit", "units", "resource",
        }

        # Extract meaningful words from the commitment
        commit_words = set(commit_content.split()) & _RELEVANCE_KEYWORDS
        if not commit_words:
            # If the commitment has no recognizable keywords, fall back to
            # assuming any contradiction about this agent is relevant
            # (preserves old behavior for vague commitments).
            return True

        # Check if either contradicting fact shares keywords with the commitment
        fact_a_words = set(fact_a.split()) & _RELEVANCE_KEYWORDS
        fact_b_words = set(fact_b.split()) & _RELEVANCE_KEYWORDS

        overlap_a = commit_words & fact_a_words
        overlap_b = commit_words & fact_b_words

        return bool(overlap_a or overlap_b)

    @staticmethod
    def _llm_contradiction_check(
        fact_a: str, fact_b: str, subject: str,
    ) -> bool:
        """
        LLM-based contradiction detection (Step 17, Rule 4).

        Asks a local Ollama model whether two facts about the same subject
        contradict each other. This is the most accurate method but also the
        most expensive — only used when USE_LLM_CONTRADICTION is True.

        Args:
            fact_a: content of the new fact
            fact_b: content of the existing fact
            subject: the agent/entity both facts are about

        Returns:
            True if the LLM judges the facts contradict each other.
        """
        try:
            import requests  # noqa: F811
        except ImportError:
            return False

        prompt = (
            f"Do these two facts about {subject} contradict each other?\n"
            f'Fact A: "{fact_a}"\n'
            f'Fact B: "{fact_b}"\n\n'
            f"Answer with EXACTLY one word: YES or NO"
        )

        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:1b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 5},
                },
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip().upper()
            return "YES" in text
        except Exception:
            # If the LLM call fails, don't block — fall through as no contradiction
            return False
