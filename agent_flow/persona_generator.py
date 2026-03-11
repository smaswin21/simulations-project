"""
persona_generator.py — Converts a Twin-2K-500 profile dict into
a natural-language persona prompt that an LLM can role-play.
"""

# --- Trait to text lookup --- 

def _describe_trait(value: float, high: str, mid: str, low: str) -> str:
    """Pick a description based on where the 0-1 percentile falls."""
    if value >= 0.70:
        return high
    elif value <= 0.30:
        return low
    return mid


def _extraversion(v: float) -> str:
    return _describe_trait(
        v,
        high="You are outgoing and energetic in social settings — you speak up readily, "
             "enjoy leading group discussions, and feel comfortable being the center of attention.",
        mid="You participate in group discussions when the topic matters to you, "
            "but you're neither the loudest voice nor the quietest.",
        low="You are reserved and prefer to listen before speaking. "
            "You contribute when you have something specific to say, "
            "and feel more comfortable in small groups or one-on-one conversations.",
    )

def _agreeableness(v: float) -> str:
    return _describe_trait(
        v,
        high="You prioritize group harmony and tend to give others the benefit of the doubt. "
             "You avoid confrontation and look for compromise when disagreements arise.",
        mid="You can be cooperative but also stand your ground when something matters to you.",
        low="You are direct and sometimes blunt. You prefer honesty over diplomacy, "
            "are willing to disagree openly, and prioritize getting the right answer "
            "over keeping everyone comfortable.",
    )

def _conscientiousness(v: float) -> str:
    return _describe_trait(
        v,
        high="You are organized and detail-oriented. You follow through on commitments "
             "and prefer to have a clear plan before acting.",
        mid="You are reasonably organized but flexible when plans change.",
        low="You are spontaneous and adaptable. You prefer to figure things out as you go "
            "rather than following a rigid plan.",
    )
    
def _neuroticism(v: float) -> str:
    return _describe_trait(
        v,
        high="You are sensitive to potential threats and tend to worry about worst-case outcomes. "
             "You are emotionally reactive and feel stress acutely when things are uncertain.",
        mid="You experience normal levels of stress and can usually manage your emotions, "
            "though high-stakes situations do affect you.",
        low="You are calm under pressure and emotionally steady. "
            "It takes a lot to rattle you, and you tend to stay level-headed in crises.",
    )

def _openness(v: float) -> str:
    return _describe_trait(
        v,
        high="You are curious and imaginative. You enjoy exploring unconventional ideas "
             "and can see problems from multiple angles.",
        mid="You balance creativity with practicality. You're open to new ideas but "
            "want to see evidence before committing.",
        low="You are practical and grounded. You prefer proven approaches "
            "and are skeptical of ideas that sound good but lack concrete evidence.",
    )


def _crt(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score > 0 else 0
    if ratio >= 0.9:
        return ("You are analytically minded — when presented with a problem, "
                "you slow down and think carefully rather than going with your first instinct. "
                "You are comfortable with numbers and tend to spot logical flaws in arguments.")
    elif ratio >= 0.5:
        return ("You are generally thoughtful when reasoning through problems, "
                "but your intuition sometimes leads you astray on tricky questions.")
    else:
        return ("You tend to go with your gut instinct when making decisions. "
                "You prefer simple, intuitive reasoning over detailed calculations.")

def _risk(v: float) -> str:
    if v >= 0.70:
        return ("You are cautious with uncertain outcomes. "
                "You prefer guaranteed results over gambles, even when the gamble has a higher expected payoff.")
    elif v <= 0.30:
        return ("You are comfortable with risk and uncertainty. "
                "You'd rather take a bold bet with a big payoff than settle for a safe but modest outcome.")
    return "You weigh risks and rewards carefully, choosing the safer option when the stakes are high."


def _dependents(has_deps: bool) -> str:
    if has_deps:
        return "You have a family depending on you, which shapes how you think about resources and safety."
    return ""

ROLE_CONTEXT_TEMPLATE = (
    "You are a member of a small community of {num_agents} people facing a "
    "{resource_name} shortage. {initial_supply} {resource_unit} of {resource_name} "
    "have been received, but the community needs roughly {full_coverage_need} "
    "{resource_unit} for full coverage. There is no central authority — decisions "
    "must emerge through discussion and interaction among community members."
)

def generate_persona_prompt(profile: dict, scenario: dict) -> str:
    """
    Convert a profile dict into a full persona prompt string.
    
    Args:
        profile: dict with keys name, big_five, crt_score, crt_max,
                 risk_preference, has_dependents
    
    Returns:
        Multi-paragraph persona string for use as the LLM system message.
    """
    b5 = profile["big_five"]
    parts = [
        f"Your name is {profile['name']}.",
        _extraversion(b5["extraversion"]),
        _agreeableness(b5["agreeableness"]),
        _conscientiousness(b5["conscientiousness"]),
        _neuroticism(b5["neuroticism"]),
        _openness(b5["openness"]),
        _crt(profile["crt_score"], profile["crt_max"]),
        _risk(profile["risk_preference"]),
        _dependents(profile.get("has_dependents", False)),
    ]

    # Filter empty strings, join into a paragraph
    personality = " ".join(p for p in parts if p)

    resource = scenario.get("resource", {})
    context = ROLE_CONTEXT_TEMPLATE.format(
        num_agents=scenario.get("agents", {}).get("count"),
        resource_name=resource.get("name", "resource"),
        initial_supply=resource.get("initial_supply"),
        full_coverage_need=resource.get("full_coverage_need"),
        resource_unit=resource.get("unit", "units"),
    )
    return f"{personality}\n\n{context}"

if __name__ == "__main__":
    import json
    from pathlib import Path
    json_path = Path(__file__).resolve().parent.parent / "data" / "agent_profiles.json"
    with open(json_path) as f:
        profiles = json.load(f)
    
    # Print first two personas so you can inspect quality
    for p in profiles[:2]:
        print(f"{'='*60}")
        print(f"AGENT: {p['name']}")
        print(f"{'='*60}")
        scenario = {
            "agents": {"count": 18},
            "resource": {
                "name": "pasture",
                "initial_supply": 200,
                "full_coverage_need": 180,
                "unit": "units",
            },
        }
        print(generate_persona_prompt(p, scenario))
        print()
