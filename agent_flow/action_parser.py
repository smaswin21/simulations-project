"""

action_parser.py — Extracts a structured action from the LLM's response.

"""

from config.scenario_loader import build_location_aliases


def parse_action(
    raw_response: str,
    agent_name: str,
    agent_location: str,
    agents_at_location: list[str],
    scenario: dict,
) -> dict:
    """Parse an LLM response into a structured action dict."""

    result = {
        "agent": agent_name,
        "type": "wait",
        "content": "",
        "target_location": None,
        "amount": None,
        "target_agent": None,
        "reasoning": raw_response.strip(),
        "raw_response": raw_response,
    }

    # ── Find the last line that starts with "action:" ────────
    action_line = None
    for line in raw_response.strip().splitlines():
        if line.strip().lower().startswith("action:"):
            action_line = line.strip()

    if not action_line:
        return result  # no action found → WAIT

    # Strip off the "ACTION:" prefix
    after_prefix = action_line.split(":", 1)[1].strip()

    # Split on "|" → left side is the command, right side is content
    if "|" in after_prefix:
        command, content = after_prefix.split("|", 1)
        command = command.strip().upper()
        content = content.strip()
    else:
        command = after_prefix.strip().upper()
        content = ""

    # ── Route by command type ────────────────────────────────

    if command.startswith("SPEAK"):
        result["type"] = "speak"
        result["content"] = content or "..."

    elif command.startswith("MOVE"):
        destination = _match_location(content, scenario)
        if destination and destination != agent_location:
            result["type"] = "move"
            result["target_location"] = destination

    elif command.startswith(
        scenario.get("resource", {}).get("resource_extraction_action", "CLAIM").upper()
    ):
        resource_location = scenario.get("resource", {}).get("location")
        if agent_location != resource_location:
            return result  # can't extract unless at resource location
        amount = _find_number(command + " " + content)
        if amount is None:
            amount = 1  # default to 1 if no number given
        amount = max(0, min(2, amount))  # clamp to {0, 1, 2}
        result["type"] = "graze"
        result["amount"] = amount
        result["content"] = content

    elif command.startswith("SHARE"):
        amount = _find_number(command)
        target = _find_agent_name(command + " " + content, agents_at_location)
        if amount and amount > 0 and target:
            result["type"] = "share"
            result["amount"] = amount
            result["target_agent"] = target
            result["content"] = content

    return result


# ── Helpers ──────────────────────────────────────────────────

def _find_number(text: str) -> int | None:
    """Find the first integer in a string."""
    for word in text.split():
        try:
            return int(word)
        except ValueError:
            continue
    return None


def _match_location(text: str, scenario: dict) -> str | None:
    """Match text to one of the known locations."""
    text_lower = text.lower()
    locations = scenario.get("locations", [])
    alias_map = build_location_aliases(locations)
    for alias, loc in alias_map.items():
        if alias in text_lower:
            return loc
    return None


def _find_agent_name(text: str, agents_at_location: list[str]) -> str | None:
    """Find which agent name appears in the text."""
    text_lower = text.lower()
    for name in agents_at_location:
        if name.lower() in text_lower:
            return name
    return None


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("Thinking...\n\nACTION: SPEAK | We should split equally.", "Alex", "Village Square", ["Jordan"]),
        ("ACTION: MOVE | Grazing Pasture", "Jordan", "Village Square", []),
        ("ACTION: GRAZE 3 | For my herd.", "Sam", "Grazing Pasture", []),
        ("ACTION: SHARE 2 Jordan | Here.", "Alex", "Village Square", ["Jordan"]),
        ("ACTION: SPEAK | Proposal: 2 each.", "Pat", "Info Board", []),
        ("No action line at all.", "Quinn", "Village Square", []),
        ("ACTION: GRAZE 5 | Nope.", "Drew", "Village Square", []),  # wrong location → WAIT
    ]
    print("Action Parser Tests:")
    for resp, name, loc, others in tests:
        scenario = {
            "resource": {"location": "Grazing Pasture"},
            "locations": [
                {"name": "Village Square", "aliases": ["village", "square"]},
                {"name": "Grazing Pasture", "aliases": ["pasture", "grazing"]},
                {"name": "Residential Area", "aliases": ["residential", "home"]},
                {"name": "Info Board", "aliases": ["info", "board"]},
            ],
        }
        r = parse_action(resp, name, loc, others, scenario)
        print(f"  {name:8s} @ {loc:16s} → {r['type']:6s}  {r.get('content','')[:40]}")
