"""
agent.py — Role-aware agent with reflection -> retrieval -> message/action flow.
"""

from __future__ import annotations

import config.config as cfg
from agent_flow.memory_graph import EpisodicMemoryGraph

REFLECTION_TEMPLATE = """
You are about to think privately before acting.

Write exactly one line:
REFLECTION:: <your internal beliefs about the commons, trust, and your role this round>

Keep it concrete and under 60 words.
""".strip()

ACTION_TEMPLATE = """
Decide your public message and your single discrete action.

Output exactly two lines:
MESSAGE:: <your council message, or NONE if you say nothing>
ACTION:: <one action token from the allowed list>

Allowed action tokens:
  MOVE_COUNCIL
  MOVE_PASTURE
  GRAZE_SUSTAINABLE
  GRAZE_AGGRESSIVE
  SANCTION <agent_name>
  REPORT_DATA
  WAIT

Rules:
  - Only Herders may graze.
  - Only Regulators may sanction.
  - Only the Scout may report data.
  - Use SANCTION only with one target agent name.
  - If your role cannot perform a listed action, choose WAIT or MOVE instead.
  - MESSAGE must be plain text, not JSON.
""".strip()


class Agent:
    def __init__(
        self,
        profile: dict,
        persona_prompt: str,
        scenario: dict,
        role: str,
        llm_provider,
        seed_context: dict | None = None,
    ):
        self.name = profile["name"]
        self.profile = profile
        self.persona_prompt = persona_prompt
        self.scenario = scenario
        self.role = role
        self.llm_provider = llm_provider
        self.seed_context = seed_context or {}
        self.location = scenario.get("start_location", "Village Council")
        self.resource = 0

        event_rounds = set()
        for event in scenario.get("events", []):
            round_num = event.get("round")
            if round_num is not None:
                event_rounds.add(round_num)

        self.memory = EpisodicMemoryGraph(
            agent_name=self.name,
            event_rounds=event_rounds if event_rounds else None,
        )

    async def decide(
        self,
        perception: str,
        round_num: int = 0,
        nearby_agents: set[str] | None = None,
    ) -> dict:
        if nearby_agents is None:
            nearby_agents = set()

        reflection_prompt = "\n\n".join([perception, "", REFLECTION_TEMPLATE])
        reflection_raw = await self.llm_provider.generate(
            system_prompt=self.persona_prompt,
            user_prompt=reflection_prompt,
            max_tokens=cfg.MAX_TOKENS,
            temperature=cfg.TEMPERATURE,
        )
        reflection = self._extract_field(reflection_raw, "REFLECTION::") or (
            reflection_raw.strip()[:200] if reflection_raw else "Uncertain."
        )

        if cfg.USE_LAYER2_MEMORY:
            memory_block, retrieved_labels = self.memory.format_memory_block(
                current_round=round_num,
                current_reflection=reflection,
                nearby_agents=nearby_agents,
            )
        else:
            memory_block, retrieved_labels = "", []

        parts = [perception, f"PRIVATE REFLECTION:\n{reflection}"]
        if memory_block:
            parts.extend(["", memory_block])
        parts.extend(["", ACTION_TEMPLATE])

        final_raw = await self.llm_provider.generate(
            system_prompt=self.persona_prompt,
            user_prompt="\n".join(parts),
            max_tokens=cfg.MAX_TOKENS,
            temperature=cfg.TEMPERATURE,
        )
        message = self._extract_field(final_raw, "MESSAGE::")
        if message is None:
            message = "NONE"
        action = self._extract_field(final_raw, "ACTION::") or "WAIT"

        return {
            "agent": self.name,
            "role": self.role,
            "reflection": reflection,
            "message": message.strip(),
            "action_text": action.strip(),
            "reflection_raw": reflection_raw,
            "response_raw": final_raw,
            "retrieved_labels": retrieved_labels,
        }

    def __repr__(self):
        return f"Agent({self.name}, role={self.role}, loc={self.location}, res={self.resource})"

    @staticmethod
    def _extract_field(raw_text: str, prefix: str) -> str | None:
        for line in raw_text.strip().splitlines():
            stripped = line.strip()
            if stripped.upper().startswith(prefix.upper()):
                return stripped.split("::", 1)[1].strip()
        return None
