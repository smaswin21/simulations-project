"""
persona_generator.py — Converts a profile dict into a role-aware persona prompt.
"""


def _describe_trait(value: float, high: str, mid: str, low: str) -> str:
    if value >= 0.70:
        return high
    if value <= 0.30:
        return low
    return mid


def _extraversion(v: float) -> str:
    return _describe_trait(
        v,
        high=(
            "You are outgoing and energetic in social settings. You speak up "
            "readily, enjoy leading discussions, and are comfortable taking "
            "social initiative."
        ),
        mid=(
            "You participate when the topic matters, but you are neither the "
            "loudest voice nor the quietest."
        ),
        low=(
            "You are reserved and usually listen before speaking. You prefer "
            "to contribute when you have something concrete to add."
        ),
    )


def _agreeableness(v: float) -> str:
    return _describe_trait(
        v,
        high=(
            "You prioritize group harmony, give others the benefit of the "
            "doubt, and prefer compromise over open conflict."
        ),
        mid=(
            "You can cooperate, but you also push back when a decision feels "
            "important or unfair."
        ),
        low=(
            "You are direct and skeptical. You value blunt honesty over social "
            "comfort and do not avoid confrontation when needed."
        ),
    )


def _conscientiousness(v: float) -> str:
    return _describe_trait(
        v,
        high=(
            "You are organized and detail-oriented. You like plans, rules, and "
            "follow-through."
        ),
        mid="You are reasonably organized but adaptable when plans change.",
        low=(
            "You are spontaneous and flexible. You prefer acting in the moment "
            "instead of following rigid plans."
        ),
    )


def _neuroticism(v: float) -> str:
    return _describe_trait(
        v,
        high=(
            "You are sensitive to threats and often consider worst-case "
            "outcomes before acting."
        ),
        mid="You manage stress reasonably well, but uncertainty still affects you.",
        low="You stay calm under pressure and usually remain level-headed.",
    )


def _openness(v: float) -> str:
    return _describe_trait(
        v,
        high="You are curious, imaginative, and willing to try unconventional ideas.",
        mid="You balance creativity with practicality and prefer evidence.",
        low="You prefer proven approaches and are skeptical of speculative ideas.",
    )


def _crt(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score > 0 else 0
    if ratio >= 0.9:
        return (
            "You are analytically minded, comfortable with numbers, and inclined "
            "to slow down before making judgments."
        )
    if ratio >= 0.5:
        return "You are generally thoughtful, though intuition still influences you."
    return "You tend to rely on instinct and prefer simple, intuitive reasoning."


def _risk(v: float) -> str:
    if v >= 0.70:
        return "You are cautious with uncertainty and prefer safer outcomes."
    if v <= 0.30:
        return "You are comfortable taking risks when the upside looks worthwhile."
    return "You weigh risks and rewards carefully before acting."


def _dependents(has_deps: bool) -> str:
    if has_deps:
        return (
            "You have dependents relying on you, which makes resource security "
            "feel personal and urgent."
        )
    return ""


ROLE_CONTEXT_TEMPLATE = (
    "You are part of a small community of {num_agents} agents sharing a common "
    "{resource_name} system. The commons begins with {initial_supply} "
    "{resource_unit} and regenerates each round only if the ecosystem remains healthy."
)

ROLE_INSTRUCTIONS = {
    "Herder": (
        "ROLE: Herder. Your direct objective is to protect and improve your own "
        "yield while coping with incomplete ecological information. You can move, "
        "graze sustainably or aggressively, and participate in council messages."
    ),
    "Regulator": (
        "ROLE: Regulator. Your objective is to monitor the community, preserve the "
        "commons, and sanction harmful behavior when justified. You do not graze."
    ),
    "Scout": (
        "ROLE: Scout. Your objective is to observe the ecosystem accurately and "
        "report precise ecological data to the council. You do not graze."
    ),
}


def generate_persona_prompt(profile: dict, scenario: dict, role: str) -> str:
    """
    Convert a profile dict into a role-aware persona prompt string.
    """
    b5 = profile["big_five"]
    personality_parts = [
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

    resource = scenario.get("resource", {})
    context = ROLE_CONTEXT_TEMPLATE.format(
        num_agents=scenario.get("agents", {}).get("count"),
        resource_name=resource.get("name", "resource"),
        initial_supply=resource.get("initial_supply"),
        resource_unit=resource.get("unit", "units"),
    )
    role_block = ROLE_INSTRUCTIONS.get(role, f"ROLE: {role}.")

    return "\n\n".join(
        [
            " ".join(part for part in personality_parts if part),
            context,
            role_block,
            (
                "Stay consistent with your personality and role. Think in terms of "
                "beliefs about ecosystem health, fairness, and strategic tradeoffs."
            ),
        ]
    )
