"""
fact_extractor.py — Phase 2: Semantic Fact Extraction

Rule-based extraction of facts and commitments from resolved action outcomes.
Uses structured action data already produced by action_parser.py — no extra
LLM call required.

Step 7:  Rule-based fact extraction (CLAIM, SHARE, SPEAK, MOVE, POST)
Step 10: Commitment detection from SPEAK actions (promise-like patterns)
"""

import re
from agent_flow.memory_graph import EpisodicMemoryGraph


# ── Commitment detection patterns (Step 10) ──────────────────

COMMITMENT_PATTERNS = [
    re.compile(r"\bI will\b", re.IGNORECASE),
    re.compile(r"\bI promise\b", re.IGNORECASE),
    re.compile(r"\bI'll make sure\b", re.IGNORECASE),
    # "I'll" alone is too broad (matches "I'll think about it").
    # Require a resource-action verb after it.
    re.compile(r"\bI'll\s+(?:share|give|distribute|help|send|bring|split)\b", re.IGNORECASE),
    re.compile(r"\bwe should all\b", re.IGNORECASE),
    re.compile(r"\blet'?s agree to\b", re.IGNORECASE),
    re.compile(r"\blet'?s all\b", re.IGNORECASE),
    re.compile(r"\bfair\b", re.IGNORECASE),
    re.compile(r"\bequal\b", re.IGNORECASE),
    re.compile(r"\bdistribute\b", re.IGNORECASE),
]


def extract_facts_and_commitments(
    memory: EpisodicMemoryGraph,
    episode_id: str,
    round_num: int,
    outcomes: list[dict],
    agent_inventories: dict[str, int] | None = None,
    extraction_verb: str = "claimed",
) -> dict:
    """
    Extract fact and commitment nodes from a round's resolved outcomes
    and add them to the agent's memory graph.

    Args:
        memory:              the agent's EpisodicMemoryGraph
        episode_id:          node ID of the episode these facts come from
        round_num:           current simulation round
        outcomes:            list of resolved outcome dicts from environment.resolve_actions()
        agent_inventories:   optional dict mapping agent_name -> current resource total

    Returns:
        Summary dict with counts: {"facts": int, "commitments": int}
    """
    if agent_inventories is None:
        agent_inventories = {}

    facts_added = 0
    commitments_added = 0

    for outcome in outcomes:
        action = outcome.get("action", "")
        agent = outcome.get("agent", "unknown")
        detail = outcome.get("detail", "")

        # ── CLAIM action → two facts ─────────────────────────
        if action == "claim":
            # Parse amount from detail like "Claimed 3 units (requested 5)"
            amount = _parse_amount_from_detail(detail)
            if amount is not None and amount > 0:
                memory.add_fact(
                    content=f"{agent} {extraction_verb} {amount} units in Round {round_num}",
                    subject=agent,
                    round_num=round_num,
                    confidence=1.0,
                    source_episode_id=episode_id,
                )
                facts_added += 1

                # Total holdings fact
                total = agent_inventories.get(agent)
                if total is not None:
                    memory.add_fact(
                        content=f"{agent} now holds {total} units",
                        subject=agent,
                        round_num=round_num,
                        confidence=1.0,
                        source_episode_id=episode_id,
                    )
                    facts_added += 1

        # ── SHARE action → two facts ─────────────────────────
        elif action == "share":
            # Parse from detail like "Shared 2 units with Jordan"
            amount = _parse_amount_from_detail(detail)
            target = _parse_target_from_share_detail(detail)

            if amount is not None and amount > 0 and target:
                memory.add_fact(
                    content=f"{agent} shared {amount} units with {target}",
                    subject=agent,
                    round_num=round_num,
                    confidence=1.0,
                    source_episode_id=episode_id,
                )
                facts_added += 1

                # Target's new total
                target_total = agent_inventories.get(target)
                if target_total is not None:
                    memory.add_fact(
                        content=f"{target} now holds {target_total} units",
                        subject=target,
                        round_num=round_num,
                        confidence=1.0,
                        source_episode_id=episode_id,
                    )
                    facts_added += 1
            elif "failed" in detail.lower():
                # Record failed share as a fact too
                memory.add_fact(
                    content=f"{agent} attempted to share but failed",
                    subject=agent,
                    round_num=round_num,
                    confidence=0.9,
                    source_episode_id=episode_id,
                )
                facts_added += 1

        # ── SPEAK action → fact + possible commitment ─────────
        elif action == "speak":
            # Truncate to key content (max 120 chars)
            speech = detail[:120].strip()
            if speech:
                memory.add_fact(
                    content=f"{agent} said: '{speech}'",
                    subject=agent,
                    round_num=round_num,
                    confidence=0.9,
                    source_episode_id=episode_id,
                )
                facts_added += 1

                # Step 10: Check for commitment patterns
                if _contains_commitment(detail):
                    memory.add_commitment(
                        agent=agent,
                        content=detail[:200].strip(),
                        round_made=round_num,
                        source_episode_id=episode_id,
                        status="pending",
                    )
                    commitments_added += 1

        # ── MOVE action → fact ────────────────────────────────
        elif action == "move":
            # Parse destination from detail like "Moved from Village Square to Common Pasture"
            location = _parse_move_destination(detail)
            if location:
                memory.add_fact(
                    content=f"{agent} moved to {location}",
                    subject=agent,
                    round_num=round_num,
                    confidence=1.0,
                    source_episode_id=episode_id,
                )
                facts_added += 1

        # ── POST action → fact (spec Step 7; not yet produced by action_parser) ──
        elif action == "post":
            post_content = detail[:120].strip()
            if post_content:
                memory.add_fact(
                    content=f"{agent} posted: '{post_content}' on info board",
                    subject=agent,
                    round_num=round_num,
                    confidence=0.9,
                    source_episode_id=episode_id,
                )
                facts_added += 1

    return {"facts": facts_added, "commitments": commitments_added}


# ── Commitment detection (Step 10) ───────────────────────────

def _contains_commitment(text: str) -> bool:
    """Check if speech text contains promise-like patterns."""
    for pattern in COMMITMENT_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ── Detail parsing helpers ───────────────────────────────────

def _parse_amount_from_detail(detail: str) -> int | None:
    """
    Extract the first integer from an outcome detail string.
    E.g. "Claimed 3 units (requested 5)" → 3
         "Shared 2 units with Jordan" → 2
    """
    match = re.search(r"(\d+)", detail)
    if match:
        return int(match.group(1))
    return None


def _parse_target_from_share_detail(detail: str) -> str | None:
    """
    Extract the target agent name from a share detail.
    E.g. "Shared 2 units with Jordan" → "Jordan"
         "Shared 3 units with Dr. Johnson" → "Dr. Johnson"
         "Share failed ..." → None
    """
    match = re.search(r"with\s+(.+?)(?:\s*[\(\)]|$)", detail)
    if match:
        return match.group(1).strip()
    return None


def _parse_move_destination(detail: str) -> str | None:
    """
    Extract the destination from a move detail.
    E.g. "Moved from Village Square to Common Pasture" → "Common Pasture"
    """
    match = re.search(r"to\s+(.+)$", detail)
    if match:
        return match.group(1).strip()
    return None


# ── Quick self-test ──────────────────────────────────────────

if __name__ == "__main__":
    print("Fact Extractor — Self-Test")
    print("=" * 50)

    mem = EpisodicMemoryGraph(agent_name="TestAgent")

    # Create a fake episode
    ep_id = mem.add_episode(
        round_num=1,
        perception_text="Round 1 perception...",
        outcomes=[],
    )

    # Simulate resolved outcomes
    test_outcomes = [
        {"agent": "Alice", "action": "claim", "detail": "Claimed 3 units (requested 5)"},
        {"agent": "Bob", "action": "share", "detail": "Shared 2 units with Alice"},
        {"agent": "Alice", "action": "speak", "detail": "I promise to share equally with everyone"},
        {"agent": "Charlie", "action": "move", "detail": "Moved from Village Square to Grazing Pasture"},
        {"agent": "Dave", "action": "speak", "detail": "We need more resources"},
        {"agent": "Eve", "action": "share", "detail": "Share failed (invalid target or insufficient resource)"},
    ]

    inventories = {"Alice": 5, "Bob": 3, "Charlie": 0, "Dave": 2, "Eve": 1}

    result = extract_facts_and_commitments(
        memory=mem,
        episode_id=ep_id,
        round_num=1,
        outcomes=test_outcomes,
        agent_inventories=inventories,
    )

    print(f"\nExtraction result: {result}")
    print(f"\nFact nodes ({mem.fact_count}):")
    for fid, fdata in mem.get_all_facts():
        print(f"  {fid}: [{fdata['subject']}] {fdata['content']} (conf={fdata['confidence']})")

    print(f"\nCommitment nodes ({mem.commitment_count}):")
    for cid, cdata in mem.get_all_commitments():
        print(f"  {cid}: [{cdata['agent']}] {cdata['content']} (status={cdata['status']})")

    # Verify EXTRACTED_FROM edges
    print(f"\nEXTRACTED_FROM edges:")
    for u, v, edata in mem.graph.edges(data=True):
        if edata.get("rel") == "EXTRACTED_FROM":
            print(f"  {u} → {v}")

    # Summary
    print(f"\nGraph summary: {mem.graph.number_of_nodes()} nodes, {mem.graph.number_of_edges()} edges")
    node_types = {}
    for _, d in mem.graph.nodes(data=True):
        t = d.get("type", "unknown")
        node_types[t] = node_types.get(t, 0) + 1
    print(f"  Node types: {node_types}")

    edge_types = {}
    for _, _, d in mem.graph.edges(data=True):
        r = d.get("rel", "unknown")
        edge_types[r] = edge_types.get(r, 0) + 1
    print(f"  Edge types: {edge_types}")
