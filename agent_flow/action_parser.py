"""
action_parser.py — Parse discrete action tokens into structured actions.
"""


def parse_action(
    action_text: str,
    agent_name: str,
    agent_role: str,
    agent_location: str,
    agents_at_location: list[str],
) -> dict:
    result = {
        "agent": agent_name,
        "role": agent_role,
        "type": "wait",
        "content": "",
        "target_location": None,
        "amount": None,
        "target_agent": None,
        "invalid_reason": "",
        "raw_action": action_text,
    }

    action = (action_text or "WAIT").strip()
    action_upper = action.upper()

    if action_upper == "MOVE_COUNCIL":
        result["type"] = "move"
        result["target_location"] = "Village Council"
        return result

    if action_upper == "MOVE_PASTURE":
        result["type"] = "move"
        result["target_location"] = "Pasture"
        return result

    if action_upper == "GRAZE_SUSTAINABLE":
        if agent_role != "Herder":
            result["invalid_reason"] = "Only herders may graze."
            return result
        result["type"] = "graze"
        result["amount"] = 1
        return result

    if action_upper == "GRAZE_AGGRESSIVE":
        if agent_role != "Herder":
            result["invalid_reason"] = "Only herders may graze."
            return result
        result["type"] = "graze"
        result["amount"] = 2
        return result

    if action_upper.startswith("SANCTION"):
        if agent_role != "Regulator":
            result["invalid_reason"] = "Only regulators may sanction."
            return result
        target = _find_target(action, agents_at_location)
        if not target:
            result["invalid_reason"] = "No valid sanction target found."
            return result
        result["type"] = "sanction"
        result["target_agent"] = target
        return result

    if action_upper == "REPORT_DATA":
        if agent_role != "Scout":
            result["invalid_reason"] = "Only the scout may report ecological data."
            return result
        result["type"] = "report"
        return result

    if action_upper == "WAIT":
        return result

    result["invalid_reason"] = "Unrecognized action token."
    return result


def _find_target(action_text: str, candidates: list[str]) -> str | None:
    lowered = action_text.lower()
    for candidate in candidates:
        if candidate.lower() in lowered:
            return candidate
    return None
