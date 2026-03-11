"""
formatting.py — Memory block formatting for prompt injection.

Formats retrieved memories into text blocks that get inserted into
the agent's LLM prompt between perception and action instruction.

Two output modes:
  1. Ranked (Phase 3/4): embedding-based retrieval, mixed node types
  2. Heuristic (fallback): bucketed by type, scored by recency/importance

Both modes produce a (memory_text, labels) tuple consumed by agent.py.
"""

from __future__ import annotations


def format_commitment(commitment: dict, current_round: int) -> str:
    """Format a single commitment for prompt injection.

    Args:
        commitment: commitment node data dict
        current_round: the round about to be played (for 'X rounds ago')

    Returns:
        Formatted string matching spec Step 15:
            [Promise] Alice committed to: "I will share resources" (Round 3) — status: BROKEN
    """
    status = commitment.get("status", "pending").upper()
    who = commitment.get("agent", "someone")
    content = commitment.get("content", "")[:120]
    round_made = commitment.get("round_made", 0)

    return (
        f"[Promise] {who} committed to: "
        f"\"{content}\" "
        f"(Round {round_made}) — status: {status}"
    )


class FormattingMixin:
    """Mixin providing memory formatting methods for EpisodicMemoryGraph."""

    def format_memory_block(
        self,
        current_round: int,
        current_perception: str = "",
        max_facts: int = 8,
        max_episodes: int = 3,
        max_commitments: int = 4,
        nearby_agents: set[str] | None = None,
    ) -> tuple[str, list[str]]:
        """
        Retrieve and format memories into a text block for prompt injection.

        Phase 3 path (embedding available):
            Uses retrieve_relevant() — cosine similarity + recency + importance.
            Formats each node type with a distinctive prefix.

        Fallback (no embedding):
            Uses the old heuristic retrieve_memories() bucketed by type.

        Args:
            current_round:      round about to be played
            current_perception: the agent's current perception (query for
                                embedding retrieval). Empty string triggers
                                heuristic fallback.
            max_facts:          (used only for heuristic fallback)
            max_episodes:       (used only for heuristic fallback)
            max_commitments:    (used only for heuristic fallback)
            nearby_agents:      set of agent names at same location

        Returns:
            (memory_block_text, list_of_retrieved_labels)
        """
        if self.episode_counter == 0:
            return "", []

        # ── Phase 3: embedding-based retrieval ───────────────
        if current_perception:
            ranked = self.retrieve_relevant(
                current_perception, current_round,
                nearby_agents=nearby_agents,
            )
            if ranked:
                return self._format_ranked_memories(ranked, current_round)

        # ── Fallback: heuristic retrieval (no embeddings) ────
        retrieved = self.retrieve_memories(
            current_round, max_facts, max_episodes, max_commitments,
            nearby_agents=nearby_agents,
        )
        return self._format_heuristic_memories(retrieved, current_round)

    # ── Formatters ───────────────────────────────────────────

    def _format_ranked_memories(
        self,
        ranked: list[tuple[str, dict, float]],
        current_round: int = 0,
    ) -> tuple[str, list[str]]:
        """Format the output of retrieve_relevant() for prompt injection.

        Phase 4: nodes with _expanded_via="contradiction" get annotated.
        """
        lines = ["YOUR RELEVANT MEMORIES:"]
        labels = []

        for nid, data, score in ranked:
            node_type = data.get("type")
            # Phase 4: annotation for expansion-sourced nodes
            contradiction_tag = ""
            expanded_via = data.get("_expanded_via")
            if expanded_via == "contradiction":
                contradiction_tag = " (contradicts another memory)"
            elif expanded_via == "provenance":
                contradiction_tag = " (linked context)"

            if node_type == "episode":
                rnd = data.get("round", "?")
                outcomes = data.get("outcomes", [])
                if outcomes:
                    parts = []
                    for o in outcomes[:4]:
                        agent = o.get("agent", "?")
                        action = o.get("action", "?")
                        detail = o.get("detail", "")[:60]
                        parts.append(f"{agent} {action}: {detail}")
                    summary = "; ".join(parts)
                else:
                    # Fall back to raw perception content when outcomes are empty
                    raw = data.get("content", "")
                    summary = raw[:120] if raw else "No notable actions"
                lines.append(f"  [Round {rnd}] You observed: {summary}{contradiction_tag}")
                labels.append(f"[Episode R{rnd}] {summary[:60]}")

            elif node_type == "fact":
                content = data.get("content", "")
                lines.append(f"  [Fact] {content}{contradiction_tag}")
                labels.append(f"[Fact] {content[:60]}")

            elif node_type == "commitment":
                formatted = format_commitment(data, current_round)
                status = data.get("status", "pending")
                who = data.get("agent", "someone")
                what = data.get("content", "")[:60]

                if status == "broken":
                    lines.append(
                        f"  ** WARNING: {formatted}{contradiction_tag} — DO NOT TRUST **"
                    )
                else:
                    lines.append(f"  {formatted}{contradiction_tag}")
                labels.append(f"[Promise] {who}: {what}")

        if len(lines) == 1:
            # Only the header, nothing retrieved
            return "", []

        return "\n".join(lines), labels

    def _format_heuristic_memories(
        self,
        retrieved: dict,
        current_round: int = 0,
    ) -> tuple[str, list[str]]:
        """Format the output of the old retrieve_memories() dict."""
        lines = []
        labels = []

        # ── Key facts ────────────────────────────────────────
        if retrieved["facts"]:
            lines.append("YOUR MEMORIES — KEY FACTS:")
            for fid, fdata in retrieved["facts"]:
                content = fdata.get("content", "")
                rnd = fdata.get("round", "?")
                lines.append(f"  - [Round {rnd}] {content}")
                labels.append(f"[Fact] {content}")

        # ── Commitments grouped by status ────────────────────
        if retrieved["commitments"]:
            broken = [
                (cid, cdata) for cid, cdata in retrieved["commitments"]
                if cdata.get("status") == "broken"
            ]
            pending = [
                (cid, cdata) for cid, cdata in retrieved["commitments"]
                if cdata.get("status") == "pending"
            ]
            kept = [
                (cid, cdata) for cid, cdata in retrieved["commitments"]
                if cdata.get("status") in ("kept", "fulfilled")
            ]

            if broken:
                lines.append("")
                lines.append("BROKEN PROMISES (someone lied!):")
                for cid, cdata in broken:
                    formatted = format_commitment(cdata, current_round)
                    lines.append(f"  ** WARNING: {formatted} **")
                    who = cdata.get("agent", "someone")
                    what = cdata.get("content", "")[:60]
                    labels.append(f"[BROKEN] {who}: {what}")

            if pending:
                lines.append("")
                lines.append("PENDING PROMISES (still waiting):")
                for cid, cdata in pending:
                    formatted = format_commitment(cdata, current_round)
                    lines.append(f"  {formatted}")
                    who = cdata.get("agent", "someone")
                    what = cdata.get("content", "")[:60]
                    labels.append(f"[Pending] {who}: {what}")

            if kept:
                lines.append("")
                lines.append("KEPT PROMISES (trustworthy):")
                for cid, cdata in kept:
                    formatted = format_commitment(cdata, current_round)
                    lines.append(f"  {formatted}")
                    who = cdata.get("agent", "someone")
                    what = cdata.get("content", "")[:60]
                    labels.append(f"[Kept] {who}: {what}")

        # ── High-importance episode summaries ─────────────────
        if retrieved["episodes"]:
            lines.append("")
            lines.append("NOTABLE PAST OBSERVATIONS:")
            for eid, edata in retrieved["episodes"]:
                rnd = edata.get("round", "?")
                importance = edata.get("importance", 0)
                outcomes = edata.get("outcomes", [])
                if outcomes:
                    summary_parts = []
                    for o in outcomes[:4]:
                        agent = o.get("agent", "?")
                        action = o.get("action", "?")
                        detail = o.get("detail", "")[:60]
                        summary_parts.append(f"{agent} {action}: {detail}")
                    summary = "; ".join(summary_parts)
                else:
                    raw = edata.get("content", "")
                    summary = raw[:120] if raw else "No notable actions"
                lines.append(f"  - [Round {rnd}] (importance={importance:.1f}) {summary}")
                labels.append(f"[Episode R{rnd}] {summary[:60]}")

        if not lines:
            return "", []

        memory_text = "\n".join(lines)
        return memory_text, labels
