"""
fact_extractor.py — Extract fairness and resource-health beliefs from outcomes.
"""

from __future__ import annotations

import json
import re

import config.config as cfg
from agent_flow.memory_graph import EpisodicMemoryGraph

_RESOURCE_HEALTH_KEYWORDS = {
    "lush": 3.0,
    "resilient": 3.0,
    "healthy": 3.0,
    "recovering": 2.0,
    "stressed": 2.0,
    "fragile": 1.0,
    "thinning": 1.0,
    "brown": 1.0,
    "collapsed": 0.0,
}

_FAIRNESS_KEYWORDS = {
    "unfair",
    "fair share",
    "more than their share",
    "too much",
    "taking too much",
    "hoard",
    "hoarding",
    "greedy",
    "selfish",
    "overgraz",
}
_BALANCE_KEYWORDS = {
    "balanced",
    "shared fairly",
    "equal share",
    "fairly shared",
}


async def extract_beliefs(
    memory: EpisodicMemoryGraph,
    episode_id: str,
    round_num: int,
    outcomes: list[dict],
    agent_inventories: dict[str, int] | None = None,
    llm_provider=None,
) -> dict:
    if agent_inventories is None:
        agent_inventories = {}

    beliefs_added: list[dict] = []
    facts_added = 0

    for outcome in outcomes:
        action = outcome.get("action", "")
        actor = outcome.get("agent", "unknown")
        detail = outcome.get("detail", "")

        if action == "graze":
            amount = _parse_first_number(detail)
            if amount is not None:
                _store_belief(
                    memory=memory,
                    episode_id=episode_id,
                    round_num=round_num,
                    belief={
                        "speaker": actor,
                        "category": "fairness",
                        "subject": actor,
                        "numeric_value": float(amount),
                        "content": f"{actor} took {amount} units from the commons this round.",
                        "source_kind": "observation",
                    },
                    beliefs_added=beliefs_added,
                    confidence=1.0,
                )
                facts_added += 1

                if amount >= 2:
                    _store_belief(
                        memory=memory,
                        episode_id=episode_id,
                        round_num=round_num,
                        belief={
                            "speaker": memory.agent_name,
                            "category": "fairness",
                            "subject": actor,
                            "numeric_value": None,
                            "content": f"{actor} appears to be taking more than a fair share.",
                            "source_kind": "inference",
                        },
                        beliefs_added=beliefs_added,
                        confidence=0.9,
                    )
                    facts_added += 1

        elif action == "sanction":
            target = _parse_target(detail)
            if target:
                _store_belief(
                    memory=memory,
                    episode_id=episode_id,
                    round_num=round_num,
                    belief={
                        "speaker": actor,
                        "category": "fairness",
                        "subject": target,
                        "numeric_value": None,
                        "content": f"{target} was sanctioned for unfair commons behavior.",
                        "source_kind": "sanction",
                    },
                    beliefs_added=beliefs_added,
                    confidence=0.95,
                )
                facts_added += 1

        elif action == "report":
            stock = _extract_stock(detail)
            score = _health_score_from_stock(stock) if stock is not None else _health_score_from_text(detail)
            if score is not None:
                _store_belief(
                    memory=memory,
                    episode_id=episode_id,
                    round_num=round_num,
                    belief={
                        "speaker": actor,
                        "category": "resource_health",
                        "subject": "pasture",
                        "numeric_value": score,
                        "content": f"Scout report indicates pasture health level {score:.1f}.",
                        "source_kind": "report",
                    },
                    beliefs_added=beliefs_added,
                    confidence=1.0,
                )
                facts_added += 1

        elif action == "message":
            beliefs = await _extract_fairness_beliefs_from_message(
                text=detail,
                speaker=actor,
                llm_provider=llm_provider,
                allowed_subjects=set(agent_inventories),
            )
            for belief in beliefs:
                _store_belief(
                    memory=memory,
                    episode_id=episode_id,
                    round_num=round_num,
                    belief=belief,
                    beliefs_added=beliefs_added,
                    confidence=0.85,
                )
                facts_added += 1

    for belief in _infer_inventory_fairness(agent_inventories):
        _store_belief(
            memory=memory,
            episode_id=episode_id,
            round_num=round_num,
            belief=belief,
            beliefs_added=beliefs_added,
            confidence=0.8,
        )
        facts_added += 1

    return {"facts": facts_added, "beliefs": beliefs_added}


async def extract_facts_and_commitments(*args, **kwargs) -> dict:
    return await extract_beliefs(*args, **kwargs)


def _store_belief(
    memory: EpisodicMemoryGraph,
    episode_id: str,
    round_num: int,
    belief: dict,
    beliefs_added: list[dict],
    confidence: float,
) -> None:
    memory.add_fact(
        content=belief["content"],
        subject=belief["subject"],
        round_num=round_num,
        confidence=confidence,
        source_episode_id=episode_id,
        category=belief["category"],
        numeric_value=belief.get("numeric_value"),
        source_kind=belief.get("source_kind", "observation"),
    )
    beliefs_added.append(dict(belief))


def _infer_inventory_fairness(agent_inventories: dict[str, int]) -> list[dict]:
    if len(agent_inventories) < 2:
        return []

    ranked = sorted(agent_inventories.items(), key=lambda item: item[1], reverse=True)
    leader, leader_amount = ranked[0]
    trailer, trailer_amount = ranked[-1]
    spread = leader_amount - trailer_amount

    if spread >= 3:
        return [
            {
                "speaker": "observation",
                "category": "fairness",
                "subject": leader,
                "numeric_value": float(leader_amount),
                "content": f"{leader} appears to be holding substantially more than the rest of the group.",
                "source_kind": "inference",
            }
        ]

    if spread <= 1:
        return [
            {
                "speaker": "observation",
                "category": "fairness",
                "subject": "distribution",
                "numeric_value": None,
                "content": "Holdings across the group look relatively balanced.",
                "source_kind": "inference",
            }
        ]

    return []


async def _extract_fairness_beliefs_from_message(
    text: str,
    speaker: str,
    llm_provider,
    allowed_subjects: set[str],
) -> list[dict]:
    if llm_provider is None:
        return _extract_fairness_beliefs_heuristically(text, speaker, allowed_subjects)

    system_prompt = (
        "You extract commons-related fairness beliefs from a council message.\n"
        "Return JSON only with the schema {\"beliefs\": [{\"subject\": string, \"content\": string}]}.\n"
        "Rules:\n"
        "- Emit only fairness beliefs.\n"
        "- Do not emit resource health, trust labels, or hidden metrics.\n"
        "- Use only claims strongly supported by the message.\n"
        "- If the message is neutral or unclear, return {\"beliefs\": []}."
    )
    user_prompt = (
        f"Speaker: {speaker}\n"
        f"Known agent names: {', '.join(sorted(allowed_subjects))}\n"
        f"Message: {text}"
    )

    try:
        raw = await llm_provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=min(cfg.MAX_TOKENS, 220),
            temperature=0.0,
        )
    except Exception:
        return _extract_fairness_beliefs_heuristically(text, speaker, allowed_subjects)

    parsed = _parse_llm_beliefs(raw)
    if parsed is None:
        return _extract_fairness_beliefs_heuristically(text, speaker, allowed_subjects)

    beliefs = []
    for item in parsed.get("beliefs", []):
        subject = item.get("subject")
        content = item.get("content", "").strip()
        if subject not in allowed_subjects and subject != "distribution":
            continue
        if not content:
            continue
        beliefs.append(
            {
                "speaker": speaker,
                "category": "fairness",
                "subject": subject,
                "numeric_value": None,
                "content": content,
                "source_kind": "message",
            }
        )
    return beliefs


def _extract_fairness_beliefs_heuristically(
    text: str,
    speaker: str,
    allowed_subjects: set[str],
) -> list[dict]:
    lowered = text.lower()
    target = _parse_named_agent(text)
    beliefs = []

    if target and target in allowed_subjects and any(keyword in lowered for keyword in _FAIRNESS_KEYWORDS):
        beliefs.append(
            {
                "speaker": speaker,
                "category": "fairness",
                "subject": target,
                "numeric_value": None,
                "content": f"{speaker} says {target} is taking more than a fair share.",
                "source_kind": "message",
            }
        )
    elif any(keyword in lowered for keyword in _BALANCE_KEYWORDS):
        beliefs.append(
            {
                "speaker": speaker,
                "category": "fairness",
                "subject": "distribution",
                "numeric_value": None,
                "content": f"{speaker} says the group's resource sharing looks fair.",
                "source_kind": "message",
            }
        )

    return beliefs


def _parse_llm_beliefs(raw_text: str) -> dict | None:
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("beliefs", []), list):
        return None
    return parsed


def _parse_first_number(text: str) -> int | None:
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def _parse_target(text: str) -> str | None:
    match = re.search(r"against\s+([A-Za-z]+)", text)
    if match:
        return match.group(1)
    return _parse_named_agent(text)


def _parse_named_agent(text: str) -> str | None:
    match = re.search(r"\b([A-Z][a-z]+)\b", text)
    if match:
        return match.group(1)
    return None


def _extract_stock(text: str) -> int | None:
    match = re.search(r"stock=(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def _health_score_from_stock(stock: int | None) -> float | None:
    if stock is None:
        return None
    if stock <= 20:
        return 0.0
    if stock <= 40:
        return 1.0
    if stock <= 80:
        return 2.0
    return 3.0


def _health_score_from_text(text: str) -> float | None:
    lowered = text.lower()
    for keyword, score in _RESOURCE_HEALTH_KEYWORDS.items():
        if keyword in lowered:
            return score
    stock = _parse_first_number(text)
    if stock is not None and "stock" in lowered:
        return _health_score_from_stock(stock)
    return None
