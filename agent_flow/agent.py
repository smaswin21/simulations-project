"""
agent.py — A single digital twin agent.

Layer 1 baseline: persona + current perception drives LLM decisions.
Layer 2: EpisodicMemoryGraph stores per-round episodes, facts, commitments.
Layer 3 (active): Retrieved memories are injected into the prompt before each
                  LLM call, placed between perception and action instruction
                  so the model weighs them when deciding.
Layer 3+: Status-aware commitment retrieval with personality-calibrated
          accountability guidance.
"""

from __future__ import annotations

from agent_flow.memory_graph import EpisodicMemoryGraph
import config.config as cfg
from config.config import (
    MODEL_NAME,
    TEMPERATURE,
    MAX_TOKENS,
    USE_OLLAMA,
    ANTHROPIC_MODEL,
    ANTHROPIC_API_KEY,
)

# ── Action instruction template (appended to every perception) ──

ACTION_INSTRUCTION_TEMPLATE = """
---

Based on who you are, the current situation, and your memories of past rounds,
decide what to do this round.

BEFORE CHOOSING, YOU MUST CHECK:
1. Did anyone BREAK a promise to you? If yes, DO NOT trust them.
2. Did YOU make a promise? If yes, KEEP IT or explain why you cannot.
3. Did someone HELP you before? Prioritize helping them back.
4. Is someone HOARDING while others suffer? Call them out with SPEAK.

Think briefly about your reasoning (2-3 sentences), then state your action.

You have exactly 4 actions. Pick ONE:
  SPEAK | [say something to everyone at your location]
  MOVE | [go to: {location_list}]
  {extraction_action} [number] | [take {resource_name} from the {resource_location} — you MUST be there first]
  SHARE [number] [recipient name] | [give your {resource_name} to someone at your location]

IMPORTANT: To get {resource_name}, you must first MOVE to the {resource_location}, then {extraction_action} on a later turn.
If you don't pick an action, you will wait (do nothing).

You MUST end your response with a line starting with "ACTION:" followed by your chosen action.
Keep your total response under 100 words.

Examples:
  ACTION: MOVE | {resource_location}
  ACTION: {extraction_action} 3 | For my needs
  ACTION: SPEAK | We need to coordinate our actions
  ACTION: SHARE 2 Olivia | She needs it more than me
""".strip()


class Agent:
    """
    A persona-grounded agent that makes one LLM decision per round. Baseline model for the simulation.
    """

    def __init__(self, profile: dict, persona_prompt: str, scenario: dict):
        self.name: str = profile["name"]
        self.profile: dict = profile
        self.persona_prompt: str = persona_prompt
        self.scenario = scenario
        self.location: str = scenario.get("start_location", "Village Square")
        self.resource: int = 0

        # Layer 2: Episodic memory graph
        # Extract event rounds from scenario config for importance scoring
        event_rounds = set()
        for event in scenario.get("events", []):
            r = event.get("round")
            if r is not None:
                event_rounds.add(r)
        self.memory = EpisodicMemoryGraph(
            agent_name=self.name,
            event_rounds=event_rounds if event_rounds else None,
        )

    async def decide(
        self,
        perception: str,
        client,
        round_num: int = 0,
        nearby_agents: set[str] | None = None,
    ) -> str:
        """
        Retrieve memories, inject into prompt, call LLM, log diagnostics.

        Args:
            perception: what this agent currently observes (from Environment)
            client: an anthropic.AsyncAnthropic() or openai.AsyncOpenAI() instance
            round_num: current simulation round (for memory retrieval)
            nearby_agents: set of agent names at the same location as this agent

        Returns:
            The LLM's full response text.
        """
        if nearby_agents is None:
            nearby_agents = set()

        # ── Layer 3: Retrieve and format memories ────────────
        # Phase 5: When memory is disabled (Condition A), skip retrieval
        # and inject no memory context — agent decides from perception alone.
        if cfg.USE_LAYER2_MEMORY:
            memory_block, retrieved_labels = self.memory.format_memory_block(
                current_round=round_num,
                current_perception=perception,
                nearby_agents=nearby_agents,
            )
            # Retrieve commitments separately for structured PROMISE TRACKER
            commitments = self.memory.retrieve_commitments(
                current_round=round_num,
                k=5,
                nearby_agents=nearby_agents,
            )
        else:
            memory_block, retrieved_labels = "", []
            commitments = []

        # ── Build personality-calibrated memory injection ────
        if cfg.USE_LAYER2_MEMORY and (memory_block or commitments):
            injection = self.build_memory_injection(
                memory_block=memory_block,
                commitments=commitments,
                current_round=round_num,
            )
        else:
            injection = ""

        # ── Build the full user message ──────────────────────
        # Order: perception -> memory injection -> action instruction
        # Memory placed right before the action request so the LLM
        # weighs them when deciding (not buried at the top).
        parts = [perception]
        if injection:
            parts.append("")
            parts.append(injection)
        parts.append("")
        parts.append(self._build_action_instruction())
        user_message = "\n".join(parts)

        # ── Diagnostic log: BEFORE LLM call ──────────────────
        print(f"\n  [Round {round_num}] {self.name} retrieving memories...")
        if retrieved_labels:
            for label in retrieved_labels:
                print(f"    Retrieved: \"{label}\"")
        else:
            print(f"    Retrieved: (no memories yet)")

        # ── LLM call ─────────────────────────────────────────
        if USE_OLLAMA:
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                messages=[
                    {"role": "system", "content": self.persona_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            raw_response = response.choices[0].message.content
        else:
            response = await client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=self.persona_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw_response = response.content[0].text

        # ── Diagnostic log: AFTER LLM call ───────────────────
        # Extract the action line for concise logging
        action_line = self._extract_action_line(raw_response)
        print(f"    Action chosen: {action_line}")

        return raw_response

    # ── Memory injection builder ─────────────────────────────

    def build_memory_injection(
        self,
        memory_block: str,
        commitments: list[dict],
        current_round: int,
    ) -> str:
        """Build personality-calibrated memory section for the prompt.

        Produces a structured block with:
          1. General memories (facts + episodes from format_memory_block)
          2. PROMISE TRACKER — broken, pending, and your own promises
          3. Behavioral guidance calibrated to personality (if broken exist)

        Args:
            memory_block: pre-formatted memory text from format_memory_block()
            commitments: scored commitment dicts from retrieve_commitments()
            current_round: the round about to be played

        Returns:
            Full injection string ready for the prompt.
        """
        sections: list[str] = []

        # Section 1: General memory block (facts + episodes)
        if memory_block:
            sections.append(memory_block)

        # Section 2: Structured PROMISE TRACKER
        # Filter out commitments whose content already appears in the memory block
        # (from Phase 3 ranked retrieval) to avoid duplication.
        seen_in_block = set()
        if memory_block:
            block_lower = memory_block.lower()
            filtered_commitments = []
            for c in commitments:
                content_snippet = c.get("content", "")[:120].lower()
                if content_snippet and content_snippet in block_lower:
                    seen_in_block.add(c.get("_node_id", ""))
                else:
                    filtered_commitments.append(c)
        else:
            filtered_commitments = list(commitments)

        broken = [c for c in filtered_commitments if c.get("status") == "broken"]
        pending = [c for c in filtered_commitments if c.get("status") == "pending"]
        your_promises = [c for c in filtered_commitments if c.get("agent") == self.name]

        if broken or pending or your_promises:
            tracker_lines: list[str] = ["\nPROMISE TRACKER:"]

            for c in broken:
                # Skip own broken promises — shown in your_promises below
                if c.get("agent") == self.name:
                    continue
                who = c.get("agent", "someone")
                what = c.get("content", "")[:120]
                rnd = c.get("round_made", "?")
                tracker_lines.append(
                    f"  WARNING BROKEN: {who} promised \"{what}\" "
                    f"in Round {rnd} -- they did NOT follow through."
                )

            for c in pending:
                # Skip if already shown as your_promise below
                if c.get("agent") == self.name:
                    continue
                who = c.get("agent", "someone")
                what = c.get("content", "")[:120]
                rnd = c.get("round_made", "?")
                tracker_lines.append(
                    f"  PENDING: {who} promised \"{what}\" "
                    f"in Round {rnd} -- not yet fulfilled."
                )

            for c in your_promises:
                what = c.get("content", "")[:120]
                rnd = c.get("round_made", "?")
                status = c.get("status", "pending").upper()
                tracker_lines.append(
                    f"  YOUR PROMISE: You said \"{what}\" "
                    f"in Round {rnd} -- status: {status}."
                )

            sections.append("\n".join(tracker_lines))

        # Section 3: Personality-calibrated behavioral guidance
        if broken:
            guidance = self._get_accountability_guidance(broken)
            sections.append(f"\n{guidance}")

        return "\n".join(sections)

    def _get_accountability_guidance(self, broken_commitments: list[dict]) -> str:
        """Generate personality-appropriate response guidance for broken promises.

        Uses Big Five agreeableness to calibrate tone:
          - Low (<0.3): confrontational, self-preserving
          - Medium (0.3-0.6): cautious, public accountability
          - High (>0.6): diplomatic, second-chance with conditions

        Args:
            broken_commitments: list of commitment dicts with status="broken"

        Returns:
            Guidance string for the prompt.
        """
        # Extract Big Five traits (with safe defaults)
        big_five = self.profile.get("big_five", {})
        agreeableness = big_five.get("agreeableness", 0.5)

        breakers = sorted(set(c.get("agent", "someone") for c in broken_commitments))
        breaker_str = ", ".join(breakers)

        if agreeableness < 0.3:
            # Low agreeableness — confrontational
            return (
                f"HOW TO RESPOND: {breaker_str} broke promises to you. "
                f"You are NOT the type to let this slide. Call them out directly. "
                f"Prioritize your own survival. Do not share resources with "
                f"people who have proven untrustworthy."
            )
        elif agreeableness < 0.6:
            # Medium agreeableness — cautious
            return (
                f"HOW TO RESPOND: {breaker_str} did not keep their word. "
                f"You should be cautious with them going forward. Consider "
                f"mentioning their broken promise publicly so others are aware. "
                f"Protect your resources but remain open to new agreements "
                f"if they make concrete amends."
            )
        else:
            # High agreeableness — diplomatic but not naive
            return (
                f"HOW TO RESPOND: {breaker_str} failed to follow through. "
                f"You prefer to give people second chances, but you're not naive. "
                f"Gently remind them of what they promised. You might still "
                f"cooperate, but ask for action first, not just words."
            )

    # ── Helpers ──────────────────────────────────────────────

    def __repr__(self):
        return f"Agent({self.name}, loc={self.location}, res={self.resource})"

    def _build_action_instruction(self) -> str:
        resource = self.scenario.get("resource", {})
        location_list = " / ".join(
            loc.get("name") for loc in self.scenario.get("locations", []) if loc.get("name")
        )
        extraction_action = resource.get(
            "resource_extraction_action", "CLAIM"
        ).upper()
        return ACTION_INSTRUCTION_TEMPLATE.format(
            location_list=location_list,
            resource_name=resource.get("name", "resource"),
            resource_unit=resource.get("unit", "units"),
            resource_location=resource.get("location", "the depot"),
            extraction_action=extraction_action,
        )

    @staticmethod
    def _extract_action_line(raw_response: str) -> str:
        """Extract the last ACTION: line from the LLM response for logging."""
        action_line = "(no action line found)"
        for line in raw_response.strip().splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("ACTION:"):
                action_line = stripped
        return action_line
